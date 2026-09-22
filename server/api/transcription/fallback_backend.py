"""Backend composto: tenta um primário e cai para um secundário em falhas recuperáveis."""

import logging

from .base import TranscriptionBackend, TranscriptionRecoverableError

logger = logging.getLogger(__name__)


class FallbackBackend(TranscriptionBackend):
    """Tenta `primary.transcribe`; se ele levantar TranscriptionRecoverableError,
    reexecuta no `secondary`. Outras exceções (TimeoutError, TranscriptionError
    não recuperável, áudio inválido) propagam direto — não vale a pena tentar
    o fallback nesses casos.
    """

    name = "openai_with_fallback"

    def __init__(self, primary: TranscriptionBackend, secondary: TranscriptionBackend):
        self.primary = primary
        self.secondary = secondary
        # Modelo de quem de fato transcreveu a última chamada. Quem contabiliza
        # o custo lê isto: cobrar o preço do primário quando o áudio acabou indo
        # para o secundário (self-hosted, custo zero) inflaria a despesa.
        self.model = getattr(primary, "model", "")

    def transcribe(self, arquivo_path: str, language: str = "pt") -> str:
        try:
            self.model = getattr(self.primary, "model", "")
            return self.primary.transcribe(arquivo_path, language)
        except TranscriptionRecoverableError as e:
            logger.warning(
                "[WHISPER:fallback] primário '%s' falhou (%s); tentando '%s'",
                self.primary.name,
                e,
                self.secondary.name,
            )
            self.model = getattr(self.secondary, "model", "")
            return self.secondary.transcribe(arquivo_path, language)