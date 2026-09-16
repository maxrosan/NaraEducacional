"""Modelos Pydantic de request/response."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


JobStatus = Literal["queued", "processing", "succeeded", "failed"]


class TranscriptionSegment(BaseModel):
    start: float = Field(..., description="Início do segmento em segundos")
    end: float = Field(..., description="Fim do segmento em segundos")
    text: str = Field(..., description="Texto do segmento")


class JobResult(BaseModel):
    text: str = Field(..., description="Texto completo concatenado dos segmentos")
    language: str = Field(..., description="Idioma detectado (código ISO-639-1)")
    language_probability: float = Field(..., description="Confiança da detecção de idioma (0-1)")
    duration_seconds: float = Field(..., description="Duração do áudio em segundos")
    processing_ms: int = Field(..., description="Tempo de processamento em ms")
    model: str = Field(..., description="Modelo utilizado (ex: 'large-v3')")
    backend: str = Field(default="faster-whisper", description="Backend usado")
    segments: Optional[List[TranscriptionSegment]] = Field(
        default=None, description="Segmentos com timestamps (se solicitados)"
    )


class JobSubmitResponse(BaseModel):
    job_id: str = Field(..., description="Identificador opaco para polling")
    status: JobStatus = Field(..., description="Estado inicial do job (normalmente 'queued')")


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: float = Field(..., description="Epoch seconds")
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Optional[JobResult] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    compute_type: str
    model_loaded: bool


class ErrorResponse(BaseModel):
    detail: str
