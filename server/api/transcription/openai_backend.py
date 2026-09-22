"""Backend de transcrição da OpenAI."""

import logging
import os

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)

from api.openai_client import get_openai_client
from api.ia_utils import run_with_timeout, IA_AUDIO_TIMEOUT_SECONDS

from .base import TranscriptionBackend, TranscriptionError, TranscriptionRecoverableError

logger = logging.getLogger(__name__)


# O whisper-1 é o Whisper large-v2, o mais antigo do catálogo. O gpt-transcribe
# é o sucessor recomendado pela OpenAI: menor taxa de erro, e mais barato
# ($0,0045/min contra $0,006/min). Configurável porque a troca de modelo de
# transcrição é o tipo de coisa que se quer reverter sem redeploy.
#
# Ele também aceita um parâmetro `keywords`, feito para nomes próprios — é o que
# resolveria "Alícia" virando "A Lícia". Ainda não usamos: a lista de alunos da
# turma chega no request mas não é repassada até aqui.
_MODELO_PADRAO = "gpt-transcribe"


class OpenAIBackend(TranscriptionBackend):
    name = "openai"

    def __init__(self):
        self.model = (os.getenv("OPENAI_TRANSCRIPTION_MODEL") or _MODELO_PADRAO).strip()

    def transcribe(self, arquivo_path: str, language: str = "pt") -> str:
        client = get_openai_client()

        def _transcrever():
            with open(arquivo_path, "rb") as audio_file:
                return client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    # "json" e não "text": o gpt-transcribe não aceita text, e o
                    # whisper-1 aceita os dois. A extração abaixo lê .text nos
                    # dois casos.
                    response_format="json",
                    language=language,
                    timeout=IA_AUDIO_TIMEOUT_SECONDS,
                )

        try:
            transcription = run_with_timeout(_transcrever, IA_AUDIO_TIMEOUT_SECONDS)
        except APIConnectionError as e:
            logger.warning("[WHISPER:openai] Falha de conexão: %s", e)
            raise TranscriptionRecoverableError("openai_connection") from e
        except APITimeoutError as e:
            logger.warning("[WHISPER:openai] Timeout da API: %s", e)
            raise TranscriptionRecoverableError("openai_timeout") from e
        except RateLimitError as e:
            # 429 cobre rate-limit e "insufficient_quota" (créditos esgotados).
            logger.warning("[WHISPER:openai] Rate limit / quota: %s", e)
            raise TranscriptionRecoverableError("openai_rate_limit") from e
        except AuthenticationError as e:
            logger.error("[WHISPER:openai] Falha de autenticação: %s", e)
            raise TranscriptionRecoverableError("openai_auth") from e
        except InternalServerError as e:
            logger.warning("[WHISPER:openai] Erro 5xx do servidor: %s", e)
            raise TranscriptionRecoverableError("openai_5xx") from e
        except APIStatusError as e:
            # Outros 4xx (400, 413 etc.) tipicamente indicam problema com o
            # áudio ou requisição — não vale a pena tentar o fallback.
            status_code = getattr(e, "status_code", "?")
            logger.error("[WHISPER:openai] HTTP %s: %s", status_code, e)
            raise TranscriptionError(f"OpenAI HTTP {status_code}") from e

        text = transcription.text if hasattr(transcription, "text") else str(transcription)
        logger.info("[WHISPER:openai] (%s) Transcrição recebida: %s...", self.model, text[:100])
        return text