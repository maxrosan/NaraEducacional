"""Serviço de transcrição de áudio (FastAPI + faster-whisper).

Carrega o modelo Whisper no startup, sobe o pool de workers que consome a
fila interna, e expõe:
- POST /transcribe       -> enfileira e retorna job_id (202)
- GET  /jobs/{job_id}    -> status + resultado quando pronto
- GET  /healthz          -> liveness (processo vivo)
- GET  /readyz           -> readiness (modelo carregado)
"""

import logging
import threading

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import router
from app.config import settings
from app.queue import job_queue
from app.transcriber import transcriber

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("transcription_service")

# Sentry (opcional)
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    sentry_sdk.set_tag("service", "transcription_service")
    logger.info("Sentry habilitado (env=%s)", settings.sentry_environment)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Carrega o modelo em thread separada para não bloquear o startup do ASGI.
    /readyz devolve 503 até a thread concluir. O pool de workers só começa a
    consumir a fila depois que o modelo termina de carregar.
    """
    logger.info(
        "Iniciando transcription_service model=%s device=%s compute_type=%s",
        settings.model_size,
        settings.device,
        settings.compute_type,
    )

    def _load():
        try:
            transcriber.load()
        except Exception:
            logger.exception("Falha ao carregar o modelo Whisper")
            return
        # Só sobe os workers depois que o modelo está em memória. Antes disso
        # a API aceita requests mas o POST /transcribe responde 503.
        job_queue.start()

    threading.Thread(target=_load, name="whisper-loader", daemon=True).start()

    yield

    logger.info("Encerrando transcription_service")


app = FastAPI(
    title="Nara Transcription Service",
    description="Microserviço de transcrição de áudio usando faster-whisper.",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(router)
