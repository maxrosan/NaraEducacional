"""Fila interna de transcrição.

Responsabilidades:
- Aceitar submissões e dar um job_id imediatamente.
- Permitir polling por status/resultado.
- Executar transcrições em threads de worker (respeitando MAX_CONCURRENT).
- Limpar jobs terminais e arquivos de áudio temporários após JOB_TTL_SECONDS.
"""

import logging
import os
import queue as stdlib_queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from .config import settings
from .schemas import JobResult, JobStatus
from .transcriber import InvalidAudioError, transcriber

logger = logging.getLogger(__name__)


class QueueFullError(Exception):
    """Levantado quando a fila interna atingiu QUEUE_MAX_SIZE."""


@dataclass
class Job:
    id: str
    audio_path: str
    language: Optional[str]
    include_segments: bool
    status: JobStatus = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Optional[JobResult] = None
    error: Optional[str] = None


class JobQueue:
    """Fila em memória + pool de workers."""

    def __init__(self) -> None:
        self._queue: "stdlib_queue.Queue[str]" = stdlib_queue.Queue(maxsize=settings.queue_max_size)
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.RLock()
        self._workers: list[threading.Thread] = []
        self._janitor: Optional[threading.Thread] = None
        self._started = False

    # -------- API pública --------

    def submit(self, audio_path: str, language: Optional[str], include_segments: bool) -> Job:
        """Enfileira um novo job. Levanta QueueFullError se a fila estiver cheia."""
        job = Job(
            id=uuid.uuid4().hex,
            audio_path=audio_path,
            language=language,
            include_segments=include_segments,
        )
        with self._lock:
            self._jobs[job.id] = job
        try:
            self._queue.put_nowait(job.id)
        except stdlib_queue.Full as exc:
            with self._lock:
                self._jobs.pop(job.id, None)
            raise QueueFullError("Transcription queue is full") from exc
        logger.info("Job enfileirado id=%s fila=%d", job.id, self._queue.qsize())
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def start(self) -> None:
        """Inicia workers e janitor. Idempotente."""
        if self._started:
            return
        self._started = True
        for i in range(max(1, settings.max_concurrent)):
            t = threading.Thread(target=self._worker_loop, name=f"whisper-worker-{i}", daemon=True)
            t.start()
            self._workers.append(t)
        self._janitor = threading.Thread(
            target=self._janitor_loop, name="whisper-janitor", daemon=True
        )
        self._janitor.start()
        logger.info(
            "JobQueue iniciado workers=%d queue_max=%d ttl=%ds",
            len(self._workers),
            settings.queue_max_size,
            settings.job_ttl_seconds,
        )

    # -------- Loops internos --------

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            job = self.get(job_id)
            if job is None:
                # Purged before execution — nothing to do.
                self._queue.task_done()
                continue
            self._run_job(job)
            self._queue.task_done()

    def _run_job(self, job: Job) -> None:
        with self._lock:
            job.status = "processing"
            job.started_at = time.time()
        try:
            text, info, segments = transcriber.transcribe(
                job.audio_path,
                language=job.language,
                include_segments=job.include_segments,
            )
            result = JobResult(
                text=text,
                language=info["language"],
                language_probability=info["language_probability"],
                duration_seconds=info["duration_seconds"],
                processing_ms=info["processing_ms"],
                model=settings.model_size,
                backend="faster-whisper",
                segments=segments,
            )
            with self._lock:
                job.result = result
                job.status = "succeeded"
                job.finished_at = time.time()
            logger.info(
                "Job ok id=%s duracao=%.1fs proc=%dms",
                job.id,
                info["duration_seconds"],
                info["processing_ms"],
            )
        except InvalidAudioError as exc:
            # Erro de dados do cliente (áudio corrompido / vazio / formato não suportado).
            # Não polui o log com traceback - apenas registra o motivo.
            logger.warning("Áudio inválido no job id=%s: %s", job.id, exc)
            with self._lock:
                job.status = "failed"
                job.error = str(exc) or exc.__class__.__name__
                job.finished_at = time.time()
        except Exception as exc:
            logger.exception("Falha no job id=%s", job.id)
            with self._lock:
                job.status = "failed"
                job.error = str(exc) or exc.__class__.__name__
                job.finished_at = time.time()
        finally:
            # Áudio temp só faz sentido enquanto o job está em voo ou recém-terminado.
            # O janitor cuida do caso em que o arquivo deve persistir até expirar,
            # mas aqui já podemos liberar — o texto resultante vive em `result`.
            self._safe_remove(job.audio_path)

    def _janitor_loop(self) -> None:
        interval = max(5, settings.janitor_interval_seconds)
        ttl = settings.job_ttl_seconds
        while True:
            time.sleep(interval)
            try:
                self._purge_expired(ttl)
            except Exception:
                logger.exception("Falha no janitor loop")

    def _purge_expired(self, ttl: float) -> None:
        now = time.time()
        expired: list[str] = []
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                terminal_at = job.finished_at
                if terminal_at is not None and (now - terminal_at) > ttl:
                    expired.append(job_id)
            for job_id in expired:
                job = self._jobs.pop(job_id, None)
                if job is not None:
                    self._safe_remove(job.audio_path)
        if expired:
            logger.info("Janitor removeu %d jobs expirados", len(expired))

    @staticmethod
    def _safe_remove(path: str) -> None:
        if not path:
            return
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            logger.warning("Falha ao remover arquivo temp: %s", path)


job_queue = JobQueue()
