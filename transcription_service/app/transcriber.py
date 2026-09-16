"""Wrapper em torno do WhisperModel do faster-whisper."""

import logging
import os
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

from faster_whisper import WhisperModel

from .config import settings
from .schemas import TranscriptionSegment

logger = logging.getLogger(__name__)

try:
    from av.error import InvalidDataError as _AVInvalidDataError
except Exception:  # pragma: no cover - av is a transitive dep; defensive only
    _AVInvalidDataError = None


class InvalidAudioError(ValueError):
    """Áudio recebido não é decodificável (vazio, corrompido ou formato inválido)."""


class Transcriber:
    """
    Wrapper stateful: mantém o WhisperModel carregado em memória.
    A concorrência agora é controlada pelo pool de workers em JobQueue,
    não mais por semáforo aqui dentro.
    """

    def __init__(self) -> None:
        self._model: Optional[WhisperModel] = None
        self._model_lock = threading.Lock()

    def load(self) -> None:
        """Carrega o modelo Whisper em memória. Chamar no startup."""
        with self._model_lock:
            if self._model is not None:
                return
            Path(settings.model_cache).mkdir(parents=True, exist_ok=True)
            logger.info(
                "Carregando Whisper model=%s device=%s compute_type=%s cache=%s",
                settings.model_size,
                settings.device,
                settings.compute_type,
                settings.model_cache,
            )
            started = time.time()
            self._model = WhisperModel(
                settings.model_size,
                device=settings.device,
                compute_type=settings.compute_type,
                cpu_threads=settings.cpu_threads,
                num_workers=settings.num_workers,
                download_root=settings.model_cache,
            )
            logger.info("Modelo carregado em %.1fs", time.time() - started)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        include_segments: bool = False,
    ) -> Tuple[str, dict, Optional[List[TranscriptionSegment]]]:
        """
        Transcreve um arquivo de áudio.

        Returns:
            (texto_concatenado, info_dict, lista_segmentos|None)
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        self._validate_audio_file(audio_path)

        started = time.time()
        try:
            segments_iter, info = self._model.transcribe(
                audio_path,
                language=language,
                beam_size=settings.beam_size,
                vad_filter=settings.vad_filter,
            )

            collected: List[TranscriptionSegment] = []
            parts: List[str] = []
            for seg in segments_iter:
                parts.append(seg.text)
                if include_segments:
                    collected.append(
                        TranscriptionSegment(start=seg.start, end=seg.end, text=seg.text.strip())
                    )
        except Exception as exc:
            if self._is_invalid_audio_error(exc):
                logger.warning(
                    "Áudio inválido/corrompido em %s: %s", audio_path, exc
                )
                raise InvalidAudioError(
                    "Audio file is invalid, corrupt, or in an unsupported format"
                ) from exc
            raise

        elapsed_ms = int((time.time() - started) * 1000)
        text = "".join(parts).strip()
        info_dict = {
            "language": info.language,
            "language_probability": float(info.language_probability),
            "duration_seconds": float(info.duration),
            "processing_ms": elapsed_ms,
        }
        logger.info(
            "Transcrição ok lang=%s duracao=%.1fs proc=%dms chars=%d",
            info.language,
            info.duration,
            elapsed_ms,
            len(text),
        )
        return text, info_dict, (collected if include_segments else None)

    @staticmethod
    def _validate_audio_file(audio_path: str) -> None:
        try:
            size = os.path.getsize(audio_path)
        except OSError as exc:
            raise InvalidAudioError(f"Audio file is not accessible: {audio_path}") from exc
        if size == 0:
            raise InvalidAudioError("Audio file is empty")

    @staticmethod
    def _is_invalid_audio_error(exc: BaseException) -> bool:
        if _AVInvalidDataError is not None and isinstance(exc, _AVInvalidDataError):
            return True
        # Fallback: identifica pelo errno do FFmpeg (AVERROR_INVALIDDATA = 1094995529)
        # caso a classe não esteja disponível por motivo de versão.
        return getattr(exc, "errno", None) == 1094995529


transcriber = Transcriber()
