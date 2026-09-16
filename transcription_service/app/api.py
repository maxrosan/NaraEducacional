"""Endpoints HTTP do serviço de transcrição."""

import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from .config import settings
from .queue import QueueFullError, job_queue
from .schemas import HealthResponse, JobStatusResponse, JobSubmitResponse
from .security import verify_internal_token
from .transcriber import transcriber

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse, tags=["health"])
async def healthz() -> HealthResponse:
    """Liveness probe - sempre 200 enquanto o processo está vivo."""
    return HealthResponse(
        status="ok",
        model=settings.model_size,
        device=settings.device,
        compute_type=settings.compute_type,
        model_loaded=transcriber.is_loaded,
    )


@router.get("/readyz", tags=["health"])
async def readyz():
    """Readiness probe - retorna 503 até o modelo terminar de carregar."""
    if not transcriber.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is still loading",
        )
    return {"status": "ready"}


@router.post(
    "/transcribe",
    response_model=JobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_internal_token)],
    tags=["transcription"],
)
async def submit_transcription(
    file: UploadFile = File(..., description="Arquivo de áudio (wav, mp3, m4a, webm, ogg, ...)"),
    language: Optional[str] = Form(
        default=None,
        description="Código ISO-639-1 (ex: 'pt'). Vazio = detecção automática.",
    ),
    include_segments: bool = Form(
        default=False,
        description="Se true, o resultado incluirá os segmentos com timestamps.",
    ),
) -> JobSubmitResponse:
    """Enfileira um áudio para transcrição e retorna um job_id para polling."""
    if not transcriber.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is still loading, try again shortly",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds limit of {settings.max_upload_mb} MB",
        )

    suffix = os.path.splitext(file.filename or "")[1] or ".bin"
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            chunk_size = 1024 * 1024  # 1MB
            written = 0
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds limit of {settings.max_upload_mb} MB",
                    )
                tmp.write(chunk)
            tmp_path = tmp.name

        chosen_language = language or settings.default_language or None
        try:
            job = job_queue.submit(
                audio_path=tmp_path,
                language=chosen_language,
                include_segments=include_segments,
            )
        except QueueFullError as exc:
            # Fila cheia: peça para o cliente tentar de novo em breve.
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Transcription queue is full",
                headers={"Retry-After": "5"},
            ) from exc

        # A partir daqui o arquivo é responsabilidade do worker / janitor.
        tmp_path = None
        return JobSubmitResponse(job_id=job.id, status=job.status)
    except HTTPException:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                logger.warning("Falha ao remover arquivo temporário: %s", tmp_path)
        raise
    except Exception:
        logger.exception("Erro inesperado ao enfileirar transcrição")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue transcription",
        )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    dependencies=[Depends(verify_internal_token)],
    tags=["transcription"],
)
async def get_job(job_id: str) -> JobStatusResponse:
    """Retorna o estado atual de um job enfileirado."""
    job = job_queue.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or expired",
        )
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result=job.result,
        error=job.error,
    )
