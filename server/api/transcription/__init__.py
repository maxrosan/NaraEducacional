"""Backends plugáveis de transcrição de áudio.

Expõe `get_transcription_backend()` para o resto do código. O backend
selecionado depende da variável de ambiente ``TRANSCRIPTION_PROVIDER``
(``openai`` ou ``faster_whisper``).
"""

from .factory import get_transcription_backend  # noqa: F401
from .base import (  # noqa: F401
    TranscriptionBackend,
    TranscriptionError,
    TranscriptionRecoverableError,
)