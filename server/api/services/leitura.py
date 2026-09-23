"""Serviço de Análise de Leitura: orquestra o fluxo entre o frontend, o
microserviço NaraNN e o S3.

Fluxo:
  1. ``iniciar_analise``  recebe o áudio gravado pela professora, converte
     para ``.ogg``, envia ao NaraNN, sobe os bytes para a área temporária
     ``audio/leitura/_pendentes/`` do S3 e cria um ``RegistroLeitura`` com
     status ``pendente`` (``arquivo_path`` aponta para o temporário).
  2. ``consultar_status``  consulta o NaraNN via ``naraonn_client.get_job``
     e atualiza o registro com a classe predita / probabilidades.
  3. ``confirmar``  recebe a classe escolhida pela professora, copia o
     objeto (server-side copy) para ``audio/leitura/<classe>/<hash>.ogg``,
     apaga o temporário e fecha o registro.
  4. ``cancelar``  apaga o temporário, pede ``DELETE`` ao NaraNN e marca o
     registro como ``cancelado``.

O áudio pendente vive em ``_pendentes/`` entre o "analisar" e o "confirmar".
Isso substitui o cache em memória (LocMemCache), que era por processo e
fazia a confirmação falhar com "áudio expirou" quando o request caía em
outro worker do Gunicorn. Órfãos em ``_pendentes/`` (professora fechou a
aba, falha, etc.) devem ser limpos por uma lifecycle rule do bucket S3
(sugestão: expirar o prefixo ``audio/leitura/_pendentes/`` em 1 dia).

Mudanças de schema em relação ao legado:
  - ``Crianca`` → ``Aluno``; ``crianca_id`` → ``aluno_id``.
  - ``turma``/``escola``/``instituicao`` são obrigatórios em
    ``RegistroLeitura`` no schema novo (o legado permitia turma nula). Se
    o chamador não informar turma, usa a do próprio aluno — que é sempre
    obrigatória em ``Aluno``, então sempre há uma turma disponível.
    ``escola``/``instituicao`` vêm do aluno também (denormalizados).
  - ``data_criacao``/``data_atualizacao`` → ``criado_em``/``atualizado_em``.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import subprocess
import tempfile
from typing import Optional

from rest_framework import status as drf_status

from api.models import Aluno, RegistroLeitura, Turma, Usuario
from api.services import naraonn_client
from api.storage import (
    copy_within_storage,
    delete_from_storage,
    generate_presigned_url,
    upload_bytes_to_storage,
)
from api.ia_utils import (
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_AUDIO_MIME_TYPES,
    MAX_AUDIO_SIZE_BYTES,
    validate_uploaded_file,
)

logger = logging.getLogger(__name__)


PENDENTES_PREFIX = "audio/leitura/_pendentes/"


class LeituraServiceError(Exception):
    """Erro de domínio do fluxo de Análise de Leitura."""

    def __init__(self, message: str, http_status: int = drf_status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.http_status = http_status


_PEAK_TARGET_DBFS = -0.5


def _detectar_pico_db(arquivo_path: str) -> Optional[float]:
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", arquivo_path,
        "-af", "volumedetect",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("[LEITURA] volumedetect falhou: %s", exc)
        return None
    stderr = result.stderr.decode(errors="replace")
    match = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", stderr)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _converter_para_ogg(arquivo_path: str) -> str:
    base, _ = os.path.splitext(arquivo_path)
    arquivo_ogg = f"{base}_naraonn.ogg"

    pico_db = _detectar_pico_db(arquivo_path)
    if pico_db is not None and pico_db < _PEAK_TARGET_DBFS:
        gain_db = _PEAK_TARGET_DBFS - pico_db
    else:
        gain_db = 0.0

    af_chain = (
        f"volume={gain_db:.2f}dB,"
        "silenceremove=start_periods=1:start_duration=0.2:start_threshold=-45dB,"
        "areverse,"
        "silenceremove=start_periods=1:start_duration=0.2:start_threshold=-45dB,"
        "areverse"
    )

    cmd = [
        "ffmpeg", "-y", "-i", arquivo_path,
        "-vn", "-map_metadata", "-1",
        "-af", af_chain,
        "-ar", "48000", "-ac", "1",
        "-c:a", "libopus", "-application", "voip",
        "-b:a", "18k", "-vbr", "on",
        arquivo_ogg,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.error("[LEITURA] ffmpeg indisponível ou estourou timeout: %s", exc)
        raise LeituraServiceError(
            "Não foi possível converter o áudio. Tente novamente em alguns instantes.",
            http_status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    if result.returncode != 0:
        logger.warning("[LEITURA] ffmpeg falhou: %s", result.stderr.decode(errors="replace")[:200])
        raise LeituraServiceError(
            "Áudio inválido — não foi possível processar o arquivo enviado.",
            http_status=drf_status.HTTP_400_BAD_REQUEST,
        )
    logger.info(
        "[LEITURA] ffmpeg encode ok (48 kHz mono 18 kbit/s voip, gain=%+.2f dB): %s",
        gain_db, arquivo_ogg,
    )
    return arquivo_ogg


def _gerar_hash(*partes: str) -> str:
    seed = "|".join(partes) + "|" + secrets.token_hex(8)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _descartar_audio_pendente(registro: RegistroLeitura) -> bool:
    if registro.arquivo_path and registro.arquivo_path.startswith(PENDENTES_PREFIX):
        delete_from_storage(registro.arquivo_path)
        registro.arquivo_path = ''
        return True
    return False


def _normalizar_probabilidades(
    raw: Optional[dict],
    predicted_name: str,
    model_kind: str = '',
) -> dict:
    if not raw and not predicted_name and not model_kind:
        return {}
    saida: dict = {}
    if raw:
        for chave, valor in raw.items():
            try:
                saida[str(int(chave))] = float(valor)
            except (TypeError, ValueError):
                continue
    if predicted_name:
        saida["__predita__"] = predicted_name
    if model_kind:
        saida["__model_kind__"] = model_kind
    return saida


def _to_int_or_none(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def iniciar_analise(
    *,
    arquivo,
    aluno: Aluno,
    turma: Optional[Turma],
    professor: Usuario,
) -> RegistroLeitura:
    """Recebe o ``UploadedFile`` da professora e dispara a análise no NaraNN."""
    erro = validate_uploaded_file(
        arquivo, ALLOWED_AUDIO_MIME_TYPES, ALLOWED_AUDIO_EXTENSIONS,
        MAX_AUDIO_SIZE_BYTES, "áudio de leitura",
    )
    if erro:
        mensagem, http_status = erro
        raise LeituraServiceError(mensagem, http_status=http_status)

    turma = turma or aluno.turma

    extensao_original = os.path.splitext(arquivo.name or "")[1].lower() or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=extensao_original) as temp_in:
        for chunk in arquivo.chunks():
            temp_in.write(chunk)
        caminho_origem = temp_in.name

    caminho_ogg: Optional[str] = None
    try:
        caminho_ogg = _converter_para_ogg(caminho_origem)
        with open(caminho_ogg, "rb") as fh:
            ogg_bytes = fh.read()

        if not ogg_bytes:
            raise LeituraServiceError("Áudio convertido ficou vazio. Tente gravar novamente.")

        try:
            job_id = naraonn_client.submit_job(ogg_bytes, name_hint=f"leitura_{aluno.id}.ogg")
        except naraonn_client.NaraonnUnavailable as exc:
            logger.error("[LEITURA] NaraNN indisponível no submit: %s", exc)
            raise LeituraServiceError(
                "Serviço de análise de leitura está temporariamente indisponível. Tente novamente em alguns minutos.",
                http_status=drf_status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc
        except naraonn_client.NaraonnError as exc:
            logger.error("[LEITURA] NaraNN respondeu inválido no submit: %s", exc)
            raise LeituraServiceError(
                "Falha ao iniciar a análise de leitura. Tente novamente.",
                http_status=drf_status.HTTP_502_BAD_GATEWAY,
            ) from exc

        arquivo_hash = _gerar_hash(str(aluno.id), arquivo.name or "audio")
        arquivo_nome = f"{arquivo_hash}.ogg"

        try:
            temp_key, _url = upload_bytes_to_storage(
                f"{PENDENTES_PREFIX}{arquivo_nome}", ogg_bytes, content_type='audio/ogg',
            )
        except RuntimeError as exc:
            logger.error("[LEITURA] Falha ao subir áudio pendente para o S3: %s", exc)
            naraonn_client.delete_job(job_id)
            raise LeituraServiceError(
                "Falha ao guardar o áudio para análise. Tente novamente.",
                http_status=drf_status.HTTP_502_BAD_GATEWAY,
            ) from exc

        registro = RegistroLeitura.objects.create(
            aluno=aluno,
            turma=turma,
            professor=professor,
            escola_id=aluno.escola_id,
            instituicao_id=aluno.instituicao_id,
            nara_job_id=job_id,
            status='pendente',
            arquivo_path=temp_key,
            arquivo_nome=arquivo_nome,
            arquivo_hash=arquivo_hash,
            tamanho_arquivo=len(ogg_bytes),
            tipo_arquivo='audio/ogg',
        )

        logger.info(
            "[LEITURA] Análise iniciada: registro_id=%s job=%s aluno=%s temp=%s",
            registro.id, job_id, aluno.id, temp_key,
        )
        return registro

    finally:
        for caminho in (caminho_origem, caminho_ogg):
            if caminho and os.path.exists(caminho):
                try:
                    os.remove(caminho)
                except OSError:
                    pass


def consultar_status(registro: RegistroLeitura) -> RegistroLeitura:
    """Atualiza o ``RegistroLeitura`` consultando o NaraNN. Retorna o registro."""
    if registro.status != 'pendente':
        return registro

    if not registro.nara_job_id:
        registro.status = 'falhou'
        campos = ['status', 'atualizado_em']
        if _descartar_audio_pendente(registro):
            campos.append('arquivo_path')
        registro.save(update_fields=campos)
        return registro

    try:
        job = naraonn_client.get_job(registro.nara_job_id)
    except naraonn_client.NaraonnUnavailable as exc:
        logger.warning("[LEITURA] NaraNN indisponível ao consultar %s: %s", registro.nara_job_id, exc)
        raise LeituraServiceError(
            "Serviço de análise está temporariamente indisponível. Tente novamente em alguns segundos.",
            http_status=drf_status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    except naraonn_client.NaraonnError as exc:
        logger.error("[LEITURA] Resposta inválida do NaraNN para %s: %s", registro.nara_job_id, exc)
        registro.status = 'falhou'
        campos = ['status', 'atualizado_em']
        if _descartar_audio_pendente(registro):
            campos.append('arquivo_path')
        registro.save(update_fields=campos)
        return registro

    job_status = job.get('status')
    update_fields = ['atualizado_em']

    if job_status == 'done':
        predicted_name = job.get('predicted_class_name') or ''
        model_kind = job.get('model_kind') or ''
        registro.classe_predita = predicted_name
        registro.probabilidades = _normalizar_probabilidades(
            job.get('per_class_probability'), predicted_name, model_kind,
        )
        registro.pieces = _to_int_or_none(job.get('pieces'))
        registro.feat_dim = _to_int_or_none(job.get('feat_dim'))
        try:
            elapsed = job.get('elapsed_seconds')
            registro.duracao_seg = float(elapsed) if elapsed is not None else None
        except (TypeError, ValueError):
            registro.duracao_seg = None
        registro.status = 'analisado'
        update_fields += [
            'classe_predita', 'probabilidades', 'pieces', 'feat_dim', 'duracao_seg', 'status',
        ]
    elif job_status == 'error':
        registro.status = 'falhou'
        update_fields.append('status')
        if _descartar_audio_pendente(registro):
            update_fields.append('arquivo_path')

    registro.save(update_fields=update_fields)
    return registro


def confirmar(
    registro: RegistroLeitura,
    *,
    classe_escolhida: str,
    anotacoes: str = '',
) -> RegistroLeitura:
    """Copia o áudio temporário para a pasta da classe escolhida e finaliza o registro."""
    if registro.status == 'confirmado':
        return registro
    if registro.status != 'analisado':
        raise LeituraServiceError(
            f"Registro está em status '{registro.status}' e não pode ser confirmado.",
        )

    classe_escolhida = (classe_escolhida or '').strip()
    if not classe_escolhida:
        raise LeituraServiceError("Selecione a classe antes de salvar.")

    temp_key = registro.arquivo_path or ''

    classe_safe = ''.join(
        c for c in classe_escolhida.lower().replace(' ', '-') if c.isalnum() or c in ('-', '_')
    ) or 'desconhecida'
    s3_key = f"audio/leitura/{classe_safe}/{registro.arquivo_nome}"

    try:
        if not temp_key.startswith(PENDENTES_PREFIX):
            raise FileNotFoundError(temp_key)
        normalized_key = copy_within_storage(temp_key, s3_key, content_type='audio/ogg')
    except FileNotFoundError:
        registro.status = 'falhou'
        registro.save(update_fields=['status', 'atualizado_em'])
        raise LeituraServiceError(
            "O áudio expirou antes da confirmação. Por favor, grave novamente.",
            http_status=drf_status.HTTP_410_GONE,
        )
    except RuntimeError as exc:
        logger.error("[LEITURA] Falha ao mover áudio no S3 para registro %s: %s", registro.id, exc)
        raise LeituraServiceError(
            "Falha ao enviar o áudio para o armazenamento. Tente novamente.",
            http_status=drf_status.HTTP_502_BAD_GATEWAY,
        ) from exc

    registro.arquivo_path = normalized_key
    registro.classe_escolhida = classe_escolhida
    registro.anotacoes_professora = anotacoes or ''
    registro.status = 'confirmado'
    registro.save(update_fields=[
        'arquivo_path', 'classe_escolhida', 'anotacoes_professora',
        'status', 'atualizado_em',
    ])

    delete_from_storage(temp_key)
    if registro.nara_job_id:
        naraonn_client.delete_job(registro.nara_job_id)

    logger.info("[LEITURA] Registro %s confirmado como '%s'", registro.id, classe_escolhida)
    return registro


def cancelar(registro: RegistroLeitura) -> RegistroLeitura:
    """Cancela um registro pendente (apaga o áudio temporário + job no NaraNN)."""
    if registro.status not in ('pendente', 'analisado', 'falhou'):
        raise LeituraServiceError(
            f"Registro está em status '{registro.status}' e não pode ser cancelado.",
        )

    if registro.nara_job_id:
        naraonn_client.delete_job(registro.nara_job_id)

    registro.status = 'cancelado'
    campos = ['status', 'atualizado_em']
    if _descartar_audio_pendente(registro):
        campos.append('arquivo_path')
    registro.save(update_fields=campos)
    return registro


def excluir(registro: RegistroLeitura) -> None:
    """Exclusão definitiva de um registro de leitura (qualquer status)."""
    if registro.nara_job_id:
        try:
            naraonn_client.delete_job(registro.nara_job_id)
        except Exception:
            logger.warning(
                "[LEITURA] Falha ao apagar job %s no NaraNN ao excluir registro %s (seguindo mesmo assim)",
                registro.nara_job_id, registro.id,
            )
    if registro.arquivo_path:
        try:
            delete_from_storage(registro.arquivo_path)
        except Exception:
            logger.warning(
                "[LEITURA] Falha ao apagar áudio %s ao excluir registro %s (seguindo mesmo assim)",
                registro.arquivo_path, registro.id,
            )
    registro_id = registro.id
    registro.delete()
    logger.info("[LEITURA] Registro %s excluído definitivamente", registro_id)


def listar_confirmados(
    *,
    aluno_id,
    data_inicio=None,
    data_fim=None,
):
    """Lista os registros confirmados de um aluno no período informado."""
    qs = RegistroLeitura.objects.filter(
        aluno_id=aluno_id,
        status='confirmado',
    )
    if data_inicio:
        qs = qs.filter(criado_em__date__gte=data_inicio)
    if data_fim:
        qs = qs.filter(criado_em__date__lte=data_fim)

    saida = []
    for registro in qs.order_by('-criado_em'):
        audio_url = generate_presigned_url(registro.arquivo_path) if registro.arquivo_path else None
        saida.append({
            'id': registro.id,
            'classe_escolhida': registro.classe_escolhida,
            'classe_predita': registro.classe_predita or None,
            'probabilidades': registro.probabilidades or {},
            'duracao_seg': registro.duracao_seg,
            'anotacoes_professora': registro.anotacoes_professora or '',
            'criado_em': registro.criado_em.isoformat() if registro.criado_em else None,
            'audio_url': audio_url,
            'arquivo_path': registro.arquivo_path or None,
            'tipo_arquivo': registro.tipo_arquivo,
        })
    return saida