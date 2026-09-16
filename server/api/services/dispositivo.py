"""Serviço do gravador de áudio (dispositivo físico do relato individual).

Responsabilidades:
  - gerar/validar códigos de pareamento (uso único, expiração curta);
  - emitir e autenticar tokens de dispositivo (guardados como hash);
  - registrar uploads de WAV de forma idempotente, com a identidade vinda
    SEMPRE do vínculo do dispositivo (nunca do payload).

O processamento do áudio (transcrição + extração + relato individual) roda
depois, sobre `AudioDispositivo` em status `recebido` — reusa `services/audio.py`.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import struct
import unicodedata
import uuid
from datetime import timedelta
from typing import NamedTuple

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from api.models import AudioDispositivo, CodigoPareamento, DispositivoGravador
from api.storage import upload_bytes_to_storage

logger = logging.getLogger(__name__)

# Pareamento: código curto o suficiente para ser digitado num portal cativo,
# com expiração curta e uso único (o rate-limit do endpoint fecha o resto).
CODIGO_TAMANHO = 6
CODIGO_ALFABETO = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'  # sem 0/O/1/I (confusão visual)
CODIGO_VALIDADE_MINUTOS = 10

# Limites do upload (WAV PCM 16 bits mono 16 kHz ≈ 32 KB/s → 25 MB ≈ 13 min).
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class DispositivoServiceError(Exception):
    """Erro de negócio do serviço; `http_status` orienta a view."""

    def __init__(self, mensagem: str, http_status: int = 400, codigo: str = ''):
        super().__init__(mensagem)
        self.http_status = http_status
        self.codigo = codigo or 'erro'


def instituicoes_divergem(id_a, id_b) -> bool:
    """True quando A e B são de instituições diferentes E o modo estrito está ligado.

    Enquanto o sistema for single-tenant por implantação (ver
    `settings.MULTI_TENANT_STRICT` e docs/PLANO_MULTI_TENANT.md), o
    `instituicao_id` dos registros pode divergir legitimamente nos dados
    legados — bloquear por isso geraria falsos "de outra instituição".
    """
    if not getattr(settings, 'MULTI_TENANT_STRICT', False):
        return False
    if not id_a or not id_b:
        return False
    return str(id_a) != str(id_b)


# ---------------------------------------------------------------------------
# Token do dispositivo
# ---------------------------------------------------------------------------

def _hash_segredo(segredo: str) -> str:
    return hashlib.sha256(segredo.encode('utf-8')).hexdigest()


def gerar_token(dispositivo_id) -> tuple[str, str]:
    """Gera `(token_claro, token_hash)`.

    Formato do token: ``<uuid-do-dispositivo>.<segredo>`` — o id localiza a
    linha (sem varrer a tabela) e o segredo é conferido contra o hash.
    O valor claro só é exibido uma vez, na resposta do pareamento.
    """
    segredo = secrets.token_urlsafe(32)
    return f"{dispositivo_id}.{segredo}", _hash_segredo(segredo)


def autenticar_dispositivo(token: str) -> DispositivoGravador:
    """Resolve o token num dispositivo ativo. Levanta erro 401 caso contrário."""
    invalido = DispositivoServiceError(
        'Token inválido ou revogado.', http_status=401, codigo='token_invalido',
    )
    if not token or '.' not in token:
        raise invalido

    dispositivo_id, _, segredo = token.partition('.')
    try:
        uuid.UUID(str(dispositivo_id))
    except (ValueError, AttributeError):
        raise invalido

    dispositivo = DispositivoGravador.objects.filter(
        id=dispositivo_id, ativo=True,
    ).select_related('professora', 'turma_ativa', 'instituicao').first()
    if not dispositivo:
        raise invalido

    # compare_digest evita timing attack na comparação do hash
    if not secrets.compare_digest(dispositivo.token_hash, _hash_segredo(segredo)):
        raise invalido

    return dispositivo


# ---------------------------------------------------------------------------
# Pareamento
# ---------------------------------------------------------------------------

def gerar_codigo_pareamento(professora, turmas=None) -> CodigoPareamento:
    """Cria um código de uso único vinculado à professora e às turmas dela.

    `turmas` é uma lista/queryset — uma professora pode atender mais de uma
    turma, e o gravador cobre todas as escolhidas.
    """
    instituicao_id = getattr(professora, 'instituicao_id', None)
    if not instituicao_id:
        raise DispositivoServiceError(
            'Usuário sem instituição vinculada.', http_status=400,
            codigo='sem_instituicao',
        )

    turmas = list(turmas or [])
    for turma in turmas:
        if instituicoes_divergem(turma.instituicao_id, instituicao_id):
            raise DispositivoServiceError(
                'Turma não pertence à instituição do usuário.', http_status=403,
                codigo='turma_de_outra_instituicao',
            )

    codigo = ''.join(secrets.choice(CODIGO_ALFABETO) for _ in range(CODIGO_TAMANHO))
    registro = CodigoPareamento.objects.create(
        codigo=codigo,
        professora=professora,
        instituicao_id=instituicao_id,
        expira_em=timezone.now() + timedelta(minutes=CODIGO_VALIDADE_MINUTOS),
    )
    if turmas:
        registro.turmas.set(turmas)
    return registro


@transaction.atomic
def parear_dispositivo(codigo: str, device_id: str, nome: str = '') -> tuple[DispositivoGravador, str]:
    """Consome o código e vincula o dispositivo à professora+turma dele.

    Retorna `(dispositivo, token_claro)`. Se o `device_id` já existir, o
    vínculo e o token são REGERADOS (re-pareamento: trocar de professora/turma
    ou recuperar um device que perdeu a configuração).
    """
    if not device_id:
        raise DispositivoServiceError(
            'device_id é obrigatório.', http_status=400, codigo='device_id_ausente',
        )

    registro = CodigoPareamento.objects.select_for_update().filter(
        codigo=(codigo or '').strip().upper(),
    ).order_by('-data_criacao').first()

    if not registro or not registro.valido:
        raise DispositivoServiceError(
            'Código inválido, expirado ou já utilizado.', http_status=400,
            codigo='codigo_invalido',
        )

    dispositivo = DispositivoGravador.objects.filter(device_id=device_id).first()
    if dispositivo is None:
        dispositivo = DispositivoGravador(device_id=device_id)

    dispositivo.professora = registro.professora
    dispositivo.instituicao = registro.instituicao
    dispositivo.ativo = True
    dispositivo.revogado_em = None
    if nome:
        dispositivo.nome = nome
    if not dispositivo.pk:
        dispositivo.pk = uuid.uuid4()

    token_claro, token_hash = gerar_token(dispositivo.pk)
    dispositivo.token_hash = token_hash
    dispositivo.save()
    dispositivo.turmas.set(registro.turmas.all())

    registro.usado_em = timezone.now()
    registro.dispositivo = dispositivo
    registro.save(update_fields=['usado_em', 'dispositivo'])

    logger.info(
        "[DISPOSITIVO] %s pareado com professora=%s turmas=%s",
        device_id, dispositivo.professora_id,
        list(dispositivo.turmas.values_list('id', flat=True)),
    )
    return dispositivo, token_claro


# O Whisper escreve números tanto em algarismo quanto por extenso ("Nível três
# A"), e nem sempre do mesmo jeito no mesmo áudio. Como o nome da turma no
# cadastro costuma usar algarismo, normalizamos os DOIS lados para algarismo.
_NUMEROS_POR_EXTENSO = {
    'zero': '0', 'um': '1', 'uma': '1', 'dois': '2', 'duas': '2', 'tres': '3',
    'quatro': '4', 'cinco': '5', 'seis': '6', 'sete': '7', 'oito': '8',
    'nove': '9', 'dez': '10',
    # ordinais, que aparecem em nomes de turma ("Terceiro A")
    'primeiro': '1', 'primeira': '1', 'segundo': '2', 'segunda': '2',
    'terceiro': '3', 'terceira': '3', 'quarto': '4', 'quarta': '4',
    'quinto': '5', 'quinta': '5', 'sexto': '6', 'sexta': '6',
    'setimo': '7', 'setima': '7', 'oitavo': '8', 'oitava': '8',
    'nono': '9', 'nona': '9', 'decimo': '10', 'decima': '10',
}


def _normalizar(texto: str) -> str:
    """minúsculo, sem acento, números por extenso viram algarismo, espaços colapsados."""
    texto = (texto or '').lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)
    )
    texto = re.sub(r'\s+', ' ', texto).strip()
    if not texto:
        return ''
    return ' '.join(_NUMEROS_POR_EXTENSO.get(p, p) for p in texto.split(' '))


def _padrao_do_nome(nome: str) -> str:
    """Regex que casa o nome da turma sem depender de espaçamento nem pontuação.

    A transcrição raramente reproduz o nome exatamente como está no cadastro:
    "Nível 3A" sai como "Nível 3 A", "nível 3-A", "nivel3a". Quebramos o nome em
    blocos de letras e de dígitos e deixamos os separadores opcionais entre eles,
    para as quatro grafias casarem com o mesmo padrão.
    """
    blocos = re.findall(r'[a-z]+|\d+', _normalizar(nome))
    if not blocos:
        return ''
    return r'[\s\.\-–_]*'.join(re.escape(b) for b in blocos)


def detectar_turma_na_fala(transcricao: str, turmas) -> object | None:
    """Encontra, na transcrição, qual das `turmas` a professora anunciou.

    A professora troca de sala falando no microfone ("estou na turma Nível 5",
    "agora com o Nível 3 B"). Casamos o NOME das turmas permitidas contra o
    texto — nomes mais longos primeiro, para "Nível 3 B" ganhar de "Nível 3".
    Retorna a turma ou None (nenhum anúncio reconhecido).
    """
    texto = _normalizar(transcricao)
    if not texto:
        return None

    candidatas = sorted(
        [t for t in turmas if getattr(t, 'nome', '')],
        key=lambda t: len(_normalizar(t.nome)), reverse=True,
    )
    for turma in candidatas:
        padrao = _padrao_do_nome(turma.nome)
        if padrao and re.search(rf'(?<![a-z0-9]){padrao}(?![a-z0-9])', texto):
            return turma
    return None


class ResolucaoTurma(NamedTuple):
    """Turma escolhida para um áudio + o PORQUÊ (o firmware precisa do porquê).

    `resultado` casa com `AudioDispositivo.TURMA_RESULTADO_CHOICES`.
    `anunciada_texto` guarda o nome reconhecido na fala, mesmo quando a turma
    não era autorizada — é o que a mensagem de feedback mostra à professora.
    """

    turma: object | None
    resultado: str
    anunciada_texto: str = ''


def resolver_turma_do_audio(
    dispositivo: DispositivoGravador,
    transcricao: str = '',
    turmas_instituicao=None,
) -> ResolucaoTurma:
    """Decide a turma deste áudio, na ordem:

    1. turma anunciada na fala **e autorizada** ao dispositivo → vira a turma
       ativa (`anunciada`);
    2. turma anunciada na fala **fora do escopo** do dispositivo →
       `nao_autorizada`, e nada é gravado: melhor não registrar do que registrar
       na sala errada;
    3. turma ativa corrente, a última anunciada (`ativa`);
    4. turma única do dispositivo (`unica`);
    5. nada (`indefinida`).

    `turmas_instituicao` é o universo usado para detectar o caso 2 (a professora
    falou uma turma que existe na escola, mas não é dela). Sem ele, uma turma não
    autorizada é simplesmente ignorada e cai nos casos 3–5.
    """
    turmas = list(dispositivo.turmas.all())

    anunciada = detectar_turma_na_fala(transcricao, turmas)
    if anunciada is not None:
        if dispositivo.turma_ativa_id != anunciada.id:
            dispositivo.turma_ativa = anunciada
            dispositivo.save(update_fields=['turma_ativa', 'data_atualizacao'])
            logger.info(
                "[DISPOSITIVO] %s trocou de turma por voz: %s",
                dispositivo.device_id, anunciada.nome,
            )
        return ResolucaoTurma(anunciada, 'anunciada', anunciada.nome)

    if turmas_instituicao is not None:
        permitidas = {t.id for t in turmas}
        alheia = detectar_turma_na_fala(
            transcricao, [t for t in turmas_instituicao if t.id not in permitidas],
        )
        if alheia is not None:
            logger.warning(
                "[DISPOSITIVO] %s anunciou turma não autorizada: %s",
                dispositivo.device_id, alheia.nome,
            )
            return ResolucaoTurma(None, 'nao_autorizada', alheia.nome)

    if dispositivo.turma_ativa_id and any(t.id == dispositivo.turma_ativa_id for t in turmas):
        return ResolucaoTurma(dispositivo.turma_ativa, 'ativa')
    if len(turmas) == 1:
        return ResolucaoTurma(turmas[0], 'unica')
    return ResolucaoTurma(None, 'indefinida')


def revogar_dispositivo(dispositivo: DispositivoGravador) -> DispositivoGravador:
    """Desativa o dispositivo — o token para de funcionar imediatamente."""
    dispositivo.ativo = False
    dispositivo.revogado_em = timezone.now()
    dispositivo.save(update_fields=['ativo', 'revogado_em', 'data_atualizacao'])
    return dispositivo


# ---------------------------------------------------------------------------
# Upload de áudio
# ---------------------------------------------------------------------------

def validar_wav(conteudo: bytes) -> None:
    """Valida cabeçalho RIFF/WAVE (evita salvar lixo e falhar só na transcrição)."""
    if len(conteudo) < 44:
        raise DispositivoServiceError(
            'Arquivo muito curto para ser um WAV válido.', http_status=400,
            codigo='wav_invalido',
        )
    if conteudo[0:4] != b'RIFF' or conteudo[8:12] != b'WAVE':
        raise DispositivoServiceError(
            'Arquivo não é um WAV (cabeçalho RIFF/WAVE ausente).', http_status=400,
            codigo='wav_invalido',
        )
    if len(conteudo) > MAX_AUDIO_BYTES:
        raise DispositivoServiceError(
            f'Arquivo excede o limite de {MAX_AUDIO_BYTES // (1024 * 1024)} MB.',
            http_status=413, codigo='arquivo_grande',
        )


def _duracao_estimada(conteudo: bytes) -> int | None:
    """Duração em segundos lida do cabeçalho fmt (best-effort)."""
    try:
        byte_rate = struct.unpack('<I', conteudo[28:32])[0]
        if byte_rate > 0:
            return max(1, int((len(conteudo) - 44) / byte_rate))
    except Exception:  # noqa: BLE001 — metadado opcional, nunca derruba upload
        pass
    return None


@transaction.atomic
def registrar_audio(
    dispositivo: DispositivoGravador,
    conteudo: bytes,
    upload_id: str,
    sha256_informado: str = '',
    duracao_seg: int | None = None,
) -> tuple[AudioDispositivo, bool]:
    """Salva o WAV e registra o upload. Retorna `(audio, criado)`.

    Idempotente por `(dispositivo, upload_id)`: o retry do firmware devolve o
    mesmo registro em vez de duplicar o relato. A identidade (professora,
    instituição) é um SNAPSHOT do vínculo atual do dispositivo, e a data é
    carimbada pelo servidor.

    A **turma** gravada aqui é apenas PROVISÓRIA: no upload ainda não existe
    transcrição, então o máximo que dá para saber é a turma ativa corrente. Se a
    professora anunciou outra sala nesta mesma gravação, quem corrige o registro
    é `services/dispositivo_processamento.py` — nunca confie neste valor antes
    de `status == 'processado'`.
    """
    try:
        upload_uuid = uuid.UUID(str(upload_id))
    except (ValueError, TypeError, AttributeError):
        raise DispositivoServiceError(
            'upload_id deve ser um UUID.', http_status=400, codigo='upload_id_invalido',
        )

    existente = AudioDispositivo.objects.filter(
        dispositivo=dispositivo, upload_id=upload_uuid,
    ).first()
    if existente:
        return existente, False

    validar_wav(conteudo)

    sha256_real = hashlib.sha256(conteudo).hexdigest()
    if sha256_informado and sha256_informado.lower() != sha256_real:
        raise DispositivoServiceError(
            'SHA-256 não confere com o arquivo recebido.', http_status=400,
            codigo='hash_divergente',
        )

    chave = (
        f"t/{dispositivo.instituicao_id}/audio/dispositivos/"
        f"{dispositivo.device_id}/{upload_uuid}.wav"
    )
    arquivo_path, _url = upload_bytes_to_storage(
        key=chave, content=conteudo, content_type='audio/wav',
    )

    try:
        audio = AudioDispositivo.objects.create(
            dispositivo=dispositivo,
            professora=dispositivo.professora,
            turma=resolver_turma_do_audio(dispositivo).turma,  # provisória (sem transcrição)
            instituicao=dispositivo.instituicao,
            upload_id=upload_uuid,
            sha256=sha256_real,
            tamanho_arquivo=len(conteudo),
            duracao_seg=duracao_seg or _duracao_estimada(conteudo),
            arquivo_path=arquivo_path,
            status='recebido',
        )
    except IntegrityError:
        # Corrida entre dois retries simultâneos: o outro venceu.
        audio = AudioDispositivo.objects.get(
            dispositivo=dispositivo, upload_id=upload_uuid,
        )
        return audio, False

    DispositivoGravador.objects.filter(pk=dispositivo.pk).update(
        last_seen=timezone.now(),
    )

    logger.info(
        "[DISPOSITIVO] Áudio %s recebido (%s bytes) de %s",
        audio.upload_id, audio.tamanho_arquivo, dispositivo.device_id,
    )
    return audio, True
