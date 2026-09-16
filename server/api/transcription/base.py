"""Interface (Strategy) comum a todos os backends de transcrição."""

from abc import ABC, abstractmethod


class TranscriptionError(Exception):
    """Erro genérico de qualquer backend de transcrição."""


class TranscriptionRecoverableError(TranscriptionError):
    """Falha do backend que pode ter sucesso em outro backend.

    Usado para sinalizar erros transitórios (rate limit, quota esgotada,
    autenticação, 5xx, falha de rede) onde tentar um backend alternativo
    faz sentido. NÃO é levantado para erros de áudio inválido — esses
    falhariam igualmente em qualquer backend.
    """


class TranscriptionBackend(ABC):
    """Contrato que todo backend de transcrição deve implementar."""

    name: str = "base"

    @abstractmethod
    def transcribe(self, arquivo_path: str, language: str = "pt") -> str:
        """Transcreve um áudio local e devolve o texto puro."""
