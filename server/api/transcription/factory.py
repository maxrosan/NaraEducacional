"""Seleção do backend de transcrição ativo via variável de ambiente."""

import logging
import os

from .base import TranscriptionBackend
from .fallback_backend import FallbackBackend
from .local_backend import FasterWhisperBackend
from .openai_backend import OpenAIBackend

logger = logging.getLogger(__name__)


# Aliases aceitos em TRANSCRIPTION_PROVIDER.
_PROVIDER_ALIASES = {
    "openai": "openai",
    "whisper-1": "openai",
    "gpt-transcribe": "openai",
    "faster_whisper": "faster_whisper",
    "faster-whisper": "faster_whisper",
    "fasterwhisper": "faster_whisper",
    "fastwhisper": "faster_whisper",
    "local": "faster_whisper",
    "openai_with_fallback": "openai_with_fallback",
    "openai-with-fallback": "openai_with_fallback",
    "openai+local": "openai_with_fallback",
    "fallback": "openai_with_fallback",
}

_DEFAULT_PROVIDER = "openai"


def _resolve_provider() -> str:
    raw = (os.getenv("TRANSCRIPTION_PROVIDER") or _DEFAULT_PROVIDER).strip().lower()
    provider = _PROVIDER_ALIASES.get(raw)
    if not provider:
        logger.warning(
            "TRANSCRIPTION_PROVIDER=%s desconhecido, caindo para %s",
            raw,
            _DEFAULT_PROVIDER,
        )
        return _DEFAULT_PROVIDER
    return provider


def get_transcription_backend() -> TranscriptionBackend:
    """Devolve a instância do backend configurado."""
    provider = _resolve_provider()
    if provider == "faster_whisper":
        return FasterWhisperBackend()
    if provider == "openai_with_fallback":
        return FallbackBackend(OpenAIBackend(), FasterWhisperBackend())
    return OpenAIBackend()