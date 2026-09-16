import asyncio
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

# Playwright requires subprocess support, which on Windows is only available via
# the Proactor event loop. Uvicorn installs the Selector policy on Windows, so we
# override it here before anything else touches the loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from playwright.async_api import Browser, async_playwright

LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("report_generator")
# Silencia ruído excessivo do Playwright mesmo em DEBUG do nosso app.
logging.getLogger("playwright").setLevel(logging.INFO)

MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "100"))
RENDER_TIMEOUT_SECONDS = int(os.getenv("RENDER_TIMEOUT_SECONDS", "60"))
SHARED_SECRET = os.getenv("RENDERER_SHARED_SECRET", "").strip()


SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    import sentry_sdk

    def _sentry_before_send(event, hint):
        # O HTML recebido em /render pode conter nomes de crianças. Starlette
        # não captura body por padrão, mas sanitizamos defensivamente caso
        # alguma integração futura passe a incluir.
        request = event.get("request") or {}
        if "data" in request:
            request["data"] = "[redacted]"
            event["request"] = request
        return event

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        release=os.getenv("SENTRY_RELEASE") or None,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,
        before_send=_sentry_before_send,
    )
    sentry_sdk.set_tag("service", "report_generator")
    logger.info(
        "Sentry habilitado (env=%s, traces=%.2f)",
        os.getenv("SENTRY_ENVIRONMENT", "development"),
        float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
    )
else:
    sentry_sdk = None  # type: ignore[assignment]
    logger.info("Sentry desabilitado (SENTRY_DSN vazio)")


class RenderRequest(BaseModel):
    html: str = Field(..., description="Documento HTML completo a ser renderizado.")
    format: str = Field("A4", description="Formato da página (A4, Letter, ...).")
    print_background: bool = Field(True, description="Imprimir cores/backgrounds.")
    wait_until: str = Field(
        "networkidle",
        description="Evento a aguardar antes de gerar o PDF (load, domcontentloaded, networkidle).",
    )


class RenderJob:
    __slots__ = ("payload", "future", "job_id", "enqueued_at")

    def __init__(self, payload: RenderRequest, loop: asyncio.AbstractEventLoop, job_id: str):
        self.payload = payload
        self.future: asyncio.Future[bytes] = loop.create_future()
        self.job_id = job_id
        self.enqueued_at = time.monotonic()


state: dict = {}


async def _render_one(browser: Browser, payload: RenderRequest, job_id: str = "-") -> bytes:
    """Renderiza um único HTML, com logs por etapa para facilitar diagnóstico."""
    step_start = time.monotonic()
    logger.debug("[job=%s] abrindo novo contexto do Chromium", job_id)
    context = await browser.new_context()
    t_context = time.monotonic()
    logger.debug(
        "[job=%s] contexto aberto em %.0f ms; criando nova página",
        job_id,
        (t_context - step_start) * 1000,
    )
    try:
        page = await context.new_page()

        def _on_console(msg):
            logger.debug("[job=%s] console.%s: %s", job_id, msg.type, msg.text)

        def _on_pageerror(err):
            logger.warning("[job=%s] erro na página: %s", job_id, err)

        def _on_requestfailed(request):
            logger.warning(
                "[job=%s] request falhou: %s %s (%s)",
                job_id,
                request.method,
                request.url,
                request.failure,
            )

        page.on("console", _on_console)
        page.on("pageerror", _on_pageerror)
        page.on("requestfailed", _on_requestfailed)

        t_page = time.monotonic()
        logger.debug(
            "[job=%s] página pronta em %.0f ms; set_content html=%s bytes wait_until=%s",
            job_id,
            (t_page - t_context) * 1000,
            len(payload.html),
            payload.wait_until,
        )

        await page.set_content(payload.html, wait_until=payload.wait_until)
        t_loaded = time.monotonic()
        logger.debug(
            "[job=%s] set_content concluído em %.0f ms (wait_until=%s); gerando PDF",
            job_id,
            (t_loaded - t_page) * 1000,
            payload.wait_until,
        )

        pdf_bytes = await page.pdf(
            format=payload.format,
            print_background=payload.print_background,
        )
        t_pdf = time.monotonic()
        logger.info(
            "[job=%s] PDF gerado: format=%s size=%s bytes (set_content=%.0f ms, pdf=%.0f ms, total=%.0f ms)",
            job_id,
            payload.format,
            len(pdf_bytes),
            (t_loaded - t_page) * 1000,
            (t_pdf - t_loaded) * 1000,
            (t_pdf - step_start) * 1000,
        )
        return pdf_bytes
    finally:
        try:
            await context.close()
            logger.debug("[job=%s] contexto fechado", job_id)
        except Exception:
            logger.exception("[job=%s] falha ao fechar contexto do Chromium", job_id)


async def render_worker():
    """Processa os jobs um por vez, reutilizando a mesma instância do Chromium."""
    queue: asyncio.Queue[RenderJob] = state["queue"]
    logger.info("Worker do renderer iniciado e aguardando jobs.")
    processed = 0
    while True:
        job = await queue.get()
        processed += 1
        wait_ms = (time.monotonic() - job.enqueued_at) * 1000
        remaining = queue.qsize()
        logger.info(
            "[job=%s] iniciando render #%s (espera na fila=%.0f ms, restantes=%s)",
            job.job_id,
            processed,
            wait_ms,
            remaining,
        )
        render_start = time.monotonic()
        try:
            pdf_bytes = await _render_one(state["browser"], job.payload, job_id=job.job_id)
            if not job.future.done():
                job.future.set_result(pdf_bytes)
            logger.info(
                "[job=%s] render concluído em %.0f ms (tamanho=%s bytes)",
                job.job_id,
                (time.monotonic() - render_start) * 1000,
                len(pdf_bytes),
            )
        except Exception as exc:  # noqa: BLE001 — o erro é propagado via future
            logger.exception(
                "[job=%s] falha ao renderizar PDF após %.0f ms",
                job.job_id,
                (time.monotonic() - render_start) * 1000,
            )
            if sentry_sdk is not None:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("component", "render_worker")
                    scope.set_tag("job_id", job.job_id)
                    scope.set_context(
                        "render_job",
                        {
                            "format": job.payload.format,
                            "wait_until": job.payload.wait_until,
                            "html_bytes": len(job.payload.html),
                        },
                    )
                    sentry_sdk.capture_exception(exc)
            if not job.future.done():
                job.future.set_exception(exc)
        finally:
            queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    logger.info(
        "Inicializando report_generator (queue_max=%s, render_timeout=%ss, secret=%s, log_level=%s)",
        MAX_QUEUE_SIZE,
        RENDER_TIMEOUT_SECONDS,
        "definido" if SHARED_SECRET else "ausente (aberto)",
        LOG_LEVEL,
    )
    start = time.monotonic()

    loop = asyncio.get_running_loop()
    state["queue"] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
    state["loop"] = loop

    logger.info("Iniciando Playwright...")
    playwright = await async_playwright().start()
    state["playwright"] = playwright
    logger.info("Playwright iniciado em %.0f ms; subindo Chromium...", (time.monotonic() - start) * 1000)

    browser_start = time.monotonic()
    state["browser"] = await playwright.chromium.launch(
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    browser_version = None
    try:
        browser_version = state["browser"].version
    except Exception:
        pass
    logger.info(
        "Chromium pronto em %.0f ms (versão=%s)",
        (time.monotonic() - browser_start) * 1000,
        browser_version,
    )

    state["worker_task"] = asyncio.create_task(render_worker())
    logger.info(
        "Report generator pronto (queue=%s, timeout=%ss) — boot total %.0f ms",
        MAX_QUEUE_SIZE,
        RENDER_TIMEOUT_SECONDS,
        (time.monotonic() - start) * 1000,
    )

    try:
        yield
    finally:
        logger.info("Encerrando report_generator...")
        task = state.get("worker_task")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("Worker cancelado.")
        browser = state.get("browser")
        if browser:
            await browser.close()
            logger.info("Chromium fechado.")
        pw = state.get("playwright")
        if pw:
            await pw.stop()
            logger.info("Playwright parado.")
        logger.info("Shutdown completo.")


app = FastAPI(lifespan=lifespan, title="Nara Report Generator")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log básico de cada requisição HTTP + tempo de resposta."""
    started = time.monotonic()
    client = f"{request.client.host}:{request.client.port}" if request.client else "-"
    logger.debug(">> %s %s from %s", request.method, request.url.path, client)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("<< %s %s ERRO não tratado", request.method, request.url.path)
        raise
    elapsed_ms = (time.monotonic() - started) * 1000
    logger.info(
        "<< %s %s -> %s em %.0f ms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


def _check_secret(header_value: Optional[str]) -> None:
    if SHARED_SECRET and header_value != SHARED_SECRET:
        logger.warning("Acesso rejeitado: segredo inválido ou ausente no header X-Renderer-Secret")
        raise HTTPException(status_code=401, detail="Invalid shared secret")


@app.get("/health")
async def health():
    queue = state.get("queue")
    qsize = queue.qsize() if queue else None
    logger.debug("/health queue=%s/%s", qsize, MAX_QUEUE_SIZE)
    return {
        "status": "ok",
        "queue_size": qsize,
        "queue_max": MAX_QUEUE_SIZE,
    }


@app.post("/render")
async def render_endpoint(
    req: RenderRequest,
    x_renderer_secret: Optional[str] = Header(default=None),
):
    _check_secret(x_renderer_secret)

    job_id = uuid.uuid4().hex[:8]
    queue: asyncio.Queue[RenderJob] = state["queue"]
    current_size = queue.qsize()

    logger.info(
        "[job=%s] /render recebido: html=%s bytes format=%s wait_until=%s queue=%s/%s",
        job_id,
        len(req.html),
        req.format,
        req.wait_until,
        current_size,
        MAX_QUEUE_SIZE,
    )

    if queue.full():
        logger.warning(
            "[job=%s] fila cheia (%s/%s), devolvendo 503",
            job_id,
            current_size,
            MAX_QUEUE_SIZE,
        )
        raise HTTPException(status_code=503, detail="Render queue is full")

    job = RenderJob(req, state["loop"], job_id=job_id)
    await queue.put(job)
    logger.debug(
        "[job=%s] job enfileirado (posição=%s)",
        job_id,
        queue.qsize(),
    )

    if sentry_sdk is not None:
        sentry_sdk.set_tag("job_id", job_id)

    try:
        pdf_bytes = await asyncio.wait_for(job.future, timeout=RENDER_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - job.enqueued_at
        logger.error(
            "[job=%s] timeout após %.0f ms (limite=%ss); devolvendo 504",
            job_id,
            elapsed * 1000,
            RENDER_TIMEOUT_SECONDS,
        )
        if sentry_sdk is not None:
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("component", "render_timeout")
                scope.set_tag("job_id", job_id)
                scope.set_context(
                    "render_timeout",
                    {
                        "elapsed_ms": round(elapsed * 1000),
                        "limit_seconds": RENDER_TIMEOUT_SECONDS,
                        "queue_size_on_enqueue": current_size,
                    },
                )
                sentry_sdk.capture_message(
                    f"Render timeout após {elapsed:.1f}s", level="error"
                )
        raise HTTPException(status_code=504, detail="Render timed out")

    total_ms = (time.monotonic() - job.enqueued_at) * 1000
    logger.info(
        "[job=%s] /render devolvendo PDF (%s bytes, total=%.0f ms fila+render)",
        job_id,
        len(pdf_bytes),
        total_ms,
    )
    return Response(content=pdf_bytes, media_type="application/pdf")


SAMPLE_HTML = """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Amostra Nara</title>
  <style>
    @page { size: A4; margin: 0; }
    body { font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 40px; color: #2d2d3a; }
    h1 { color: #6b5db0; margin: 0 0 8px; }
    .box { border: 1.5px solid #e2dcf5; border-radius: 12px; padding: 16px; margin-top: 16px; background: #f4f1fc; }
    .tag { display: inline-block; padding: 2px 10px; border-radius: 20px; background: #e8f5e9; color: #2e7d32; font-size: 11px; font-weight: 700; }
  </style>
</head>
<body>
  <h1>Amostra de renderização</h1>
  <p>Este PDF foi gerado pelo serviço <strong>report_generator</strong>.</p>
  <div class="box">
    <span class="tag">OK</span>
    <p>Se você está vendo este texto bem formatado, o Chromium headless está funcionando.</p>
  </div>
</body>
</html>
"""


@app.get("/sample")
async def sample_pdf():
    logger.info("/sample solicitado — renderizando amostra embutida")
    start = time.monotonic()
    pdf_bytes = await _render_one(state["browser"], RenderRequest(html=SAMPLE_HTML), job_id="sample")
    logger.info(
        "/sample concluído em %.0f ms (%s bytes)",
        (time.monotonic() - start) * 1000,
        len(pdf_bytes),
    )
    return Response(content=pdf_bytes, media_type="application/pdf")
