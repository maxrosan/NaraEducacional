"""View para upload e processamento de áudio de observações pedagógicas."""

import hashlib
import json
import logging
import os
import random
import time

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.throttles import UploadRateThrottle
from api.views_legacy import (
    validate_uploaded_file,
    ALLOWED_AUDIO_MIME_TYPES,
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_AUDIO_SIZE_BYTES,
)
from api.services.audio import (
    InvalidAudioError,
    MODELO_EXTRACAO,
    converter_para_wav,
    descartar_derivados,
    modelo_transcricao_ativo,
    transcrever_audio,
    extrair_observacoes,
    parear_alunos_com_turma,
)
from api.transcription import TranscriptionError

logger = logging.getLogger(__name__)


def _guess_audio_extension(uploaded_file) -> str:
    """Deriva a extensão mais fiel possível ao arquivo enviado."""
    content_type = (uploaded_file.content_type or "").lower().split(";")[0].strip()
    original_ext = os.path.splitext(uploaded_file.name or "")[1].lower()

    mime_to_ext = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/m4a": ".m4a",
        "audio/mp4": ".m4a",
    }

    if content_type in mime_to_ext:
        return mime_to_ext[content_type]

    if original_ext in ALLOWED_AUDIO_EXTENSIONS:
        return original_ext

    return ".wav"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_audio(request):
    """Endpoint para upload e análise de áudio. Requer autenticação. Rate limit: 10 req/min."""
    arquivo_path = None
    try:
        # --- Validação do arquivo ---
        if "audio" not in request.FILES:
            return Response(
                {"error": "Nenhum arquivo de áudio foi enviado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        arquivo_audio = request.FILES["audio"]
        turma_id = request.POST.get("turmaId", "")
        professora = request.POST.get("professora", "Sistema")
        tipo = request.POST.get("tipo", "observacao_livre")
        alunos_turma_json = request.POST.get("alunosTurma", "[]")

        validation_error = validate_uploaded_file(
            arquivo_audio, ALLOWED_AUDIO_MIME_TYPES, ALLOWED_AUDIO_EXTENSIONS, MAX_AUDIO_SIZE_BYTES, "áudio"
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({"error": mensagem}, status=status_code)

        if not turma_id:
            return Response(
                {"error": "ID da turma é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            alunos_turma = json.loads(alunos_turma_json)
            logger.info("[ALUNOS TURMA] Recebidos %d alunos do frontend", len(alunos_turma))
        except json.JSONDecodeError:
            return Response(
                {"error": "Lista de alunos inválida"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Salvar arquivo ---
        upload_dir = "uploads/audio"
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = str(int(time.time()))
        random_value = str(random.randint(1000, 9999))
        hash_input = f"audio_{turma_id}_{timestamp}_{random_value}".encode("utf-8")
        file_hash = hashlib.md5(hash_input).hexdigest()[:12]

        audio_ext = _guess_audio_extension(arquivo_audio)
        arquivo_nome = f"{file_hash}_observacao_{timestamp}{audio_ext}"
        arquivo_path = os.path.join(upload_dir, arquivo_nome)

        with open(arquivo_path, "wb+") as destination:
            for chunk in arquivo_audio.chunks():
                destination.write(chunk)

        logger.info("[UPLOAD AUDIO] Arquivo salvo: %s", arquivo_nome)
        logger.info("[UPLOAD AUDIO] Hash: %s | Turma: %s | Professora: %s | Tamanho: %d bytes",
                     file_hash, turma_id, professora, arquivo_audio.size)

        # --- Normalização para WAV 16 kHz mono ---
        try:
            arquivo_processado = converter_para_wav(arquivo_path)
        except InvalidAudioError as e:
            logger.warning("[UPLOAD AUDIO] Áudio inválido recebido (%s): %s", arquivo_nome, e)
            return Response(
                {
                    "error": "O áudio enviado está corrompido ou em um formato não suportado. "
                             "Por favor, grave novamente.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # --- Transcrição via Whisper ---
        try:
            transcribed = transcrever_audio(arquivo_processado, usuario=request.user)
        except RuntimeError as e:
            return Response(
                {"error": f"Configuração da OpenAI ausente: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except ConnectionError:
            return Response(
                {"error": "Serviço de transcrição indisponível no momento. Tente novamente em instantes."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except TimeoutError:
            return Response(
                {"error": "Tempo limite excedido ao transcrever o áudio. Tente novamente."},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except TranscriptionError as e:
            mensagem = str(e)
            logger.error("[UPLOAD AUDIO] Falha na transcrição (%s): %s", arquivo_nome, mensagem)
            if "Invalid data" in mensagem or "1094995529" in mensagem:
                return Response(
                    {
                        "error": "O áudio enviado está corrompido ou em um formato não suportado. "
                                 "Por favor, grave novamente.",
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            return Response(
                {"error": "Não foi possível transcrever o áudio. Tente novamente."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # --- Extração de observações via GPT-4 ---
        # cliente_id resolve o prompt da categoria "Voz" do banco para a instituição do usuário
        cliente_id = str(request.user.instituicao_id) if getattr(request.user, 'instituicao_id', None) else None
        try:
            dados_extraidos = extrair_observacoes(transcribed, cliente_id=cliente_id)
        except ValueError as e:
            logger.warning("[EXTRAÇÃO FALHOU] %s", e)
            mensagem_servico = str(e).strip()
            if mensagem_servico == "Não foi possível identificar alunos no áudio.":
                mensagem_usuario = (
                    "Não foi possível identificar alunos no áudio. Por favor, tente gravar "
                    "novamente falando o nome do aluno de forma clara."
                )
            else:
                mensagem_usuario = mensagem_servico or (
                    "Não foi possível processar o áudio. Tente gravar novamente."
                )
            return Response(
                {
                    "success": False,
                    "error": mensagem_usuario,
                    "transcricao": {"texto_completo": transcribed},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except ConnectionError:
            return Response(
                {"error": "Serviço de análise indisponível no momento. Tente novamente em instantes."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except TimeoutError:
            return Response(
                {"error": "Tempo limite excedido ao extrair observações do áudio. Tente novamente."},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )

        # --- Pareamento com alunos da turma ---
        resultado_pareamento = parear_alunos_com_turma(
            dados_extraidos["nomes_alunos"], dados_extraidos["observacoes"], alunos_turma
        )

        pareados = resultado_pareamento["pareados"]
        nao_pareados = resultado_pareamento["nao_pareados"]

        # --- Montar resposta ---
        avisos = []
        parcial = len(nao_pareados) > 0

        if not pareados:
            nomes_detectados = [np["nome_original_detectado"] for np in nao_pareados]
            avisos.append(
                f"Nenhum nome foi identificado automaticamente. Nomes detectados: {', '.join(nomes_detectados)}. Selecione os alunos manualmente."
            )
        elif parcial:
            nomes_nao_pareados = [np["nome_original_detectado"] for np in nao_pareados]
            avisos.append(
                f"Os seguintes nomes não foram encontrados na turma: {', '.join(nomes_nao_pareados)}"
            )

        alunos_detectados = []
        for p in pareados:
            alunos_detectados.append({
                "aluno_nome": p["aluno_nome"],
                "observacao": p["observacao"],
                "confianca": p["confianca"],
                "nome_original_detectado": p["nome_original_detectado"],
                "score_similaridade": p["score_similaridade"],
                "metodo_match": p["metodo_match"],
            })

        resultado = {
            "success": True,
            "parcial": parcial,
            "arquivo_salvo": arquivo_path,
            "arquivo_nome": arquivo_nome,
            "arquivo_hash": file_hash,
            "turma_id": turma_id,
            "professora": professora,
            "tipo": tipo,
            "transcricao": {
                "texto_completo": transcribed,
                "alunos_detectados": alunos_detectados,
                "total_alunos": len(alunos_detectados),
                "confianca_geral": round(
                    sum(a["confianca"] for a in alunos_detectados) / len(alunos_detectados), 2
                ) if alunos_detectados else 0,
                "status": "Processado pela IA",
                "duracao_audio": f"{round(arquivo_audio.size / 16000, 1)} segundos",
                "qualidade_audio": "Boa",
            },
            "nao_identificados": nao_pareados if parcial else [],
            "avisos": avisos,
            "metadados": {
                "arquivo_id": file_hash,
                "tamanho_arquivo": arquivo_audio.size,
                "tipo_arquivo": arquivo_audio.content_type,
                "data_processamento": time.strftime("%Y-%m-%d %H:%M:%S"),
                "modelo_ia_usado": f"{modelo_transcricao_ativo()} + {MODELO_EXTRACAO}",
                "linguagem_detectada": "pt-BR",
                "modo_deteccao": "multiplos_alunos",
            },
            "acoes_sugeridas": {
                "pode_editar": True,
                "pode_confirmar_alunos": True,
                "pode_editar_observacoes": True,
                "salvar_automatico": False,
                "requer_confirmacao_multipla": len(alunos_detectados) > 1,
                "tem_busca_similaridade": True,
            },
        }

        return Response(resultado, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("[ERRO UPLOAD AUDIO] %s", str(e), exc_info=True)
        return Response(
            {"error": "Erro interno no servidor", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        # O WAV intermediário é PCM 16 kHz — vários múltiplos do upload
        # comprimido — e nada o referencia depois da transcrição. Ficava
        # acumulando em uploads/audio a cada gravação. O upload original é
        # preservado: ele volta na resposta como "arquivo_salvo".
        if arquivo_path:
            descartar_derivados(arquivo_path)