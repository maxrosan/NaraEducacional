"""Cliente HTTP para o microserviço `report_generator` (Playwright + Chromium)."""

import logging
import os
import time
import uuid
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class RendererError(Exception):
    """Erro genérico ao comunicar com o serviço de geração de PDF."""


class RendererUnavailable(RendererError):
    """Não foi possível alcançar o serviço (rede/timeout de conexão)."""


class RendererBusy(RendererError):
    """Fila do renderer está cheia (HTTP 503)."""


class RendererTimeout(RendererError):
    """Renderização excedeu o tempo limite (HTTP 504 ou timeout local)."""


def _base_url() -> str:
    return os.getenv("REPORT_GENERATOR_URL", "http://report_generator:8000").rstrip("/")


def _shared_secret() -> Optional[str]:
    value = os.getenv("REPORT_GENERATOR_SECRET", "").strip()
    return value or None


def _timeout_seconds() -> float:
    try:
        return float(os.getenv("REPORT_GENERATOR_TIMEOUT", "60"))
    except ValueError:
        return 60.0


def render_html_to_pdf(
    html: str,
    *,
    page_format: str = "A4",
    print_background: bool = True,
    wait_until: str = "networkidle",
) -> bytes:
    """Envia HTML para o renderer e devolve os bytes do PDF.

    Levanta `RendererBusy` (503), `RendererTimeout` (504), `RendererUnavailable`
    (conexão) ou `RendererError` (outros) para que a view chame possa mapear.
    """
    call_id = uuid.uuid4().hex[:8]
    url = f"{_base_url()}/render"
    payload = {
        "html": html,
        "format": page_format,
        "print_background": print_background,
        "wait_until": wait_until,
    }
    headers = {}
    secret = _shared_secret()
    if secret:
        headers["X-Renderer-Secret"] = secret

    # Dá uma margem acima do timeout do serviço para deixar a camada do serviço
    # responder com 504 em vez de cair em timeout local.
    client_timeout = _timeout_seconds() + 10

    logger.info(
        "[render=%s] POST %s html=%s bytes format=%s wait_until=%s timeout=%.1fs secret=%s",
        call_id,
        url,
        len(html),
        page_format,
        wait_until,
        client_timeout,
        "sim" if secret else "não",
    )

    start = time.monotonic()
    try:
        with httpx.Client(timeout=client_timeout) as client:
            response = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        elapsed = (time.monotonic() - start) * 1000
        logger.warning(
            "[render=%s] timeout local após %.0f ms ao chamar %s: %s",
            call_id,
            elapsed,
            url,
            exc,
        )
        raise RendererTimeout("Tempo limite atingido ao renderizar PDF.") from exc
    except httpx.HTTPError as exc:
        elapsed = (time.monotonic() - start) * 1000
        logger.exception(
            "[render=%s] falha de rede após %.0f ms ao chamar %s",
            call_id,
            elapsed,
            url,
        )
        raise RendererUnavailable("Serviço de geração de PDF indisponível.") from exc

    elapsed_ms = (time.monotonic() - start) * 1000

    if response.status_code == 200:
        logger.info(
            "[render=%s] resposta 200 em %.0f ms (PDF=%s bytes)",
            call_id,
            elapsed_ms,
            len(response.content),
        )
        return response.content

    body_preview = response.text[:500] if response.text else ""
    logger.warning(
        "[render=%s] resposta %s em %.0f ms body=%s",
        call_id,
        response.status_code,
        elapsed_ms,
        body_preview,
    )

    if response.status_code == 503:
        raise RendererBusy("Fila do serviço de geração de PDF está cheia.")
    if response.status_code == 504:
        raise RendererTimeout("Renderização excedeu o tempo limite.")
    if response.status_code == 401:
        raise RendererError("Segredo de renderer inválido. Verifique REPORT_GENERATOR_SECRET.")

    raise RendererError(f"Resposta inesperada do renderer (HTTP {response.status_code}).")
