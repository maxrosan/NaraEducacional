"""Cliente HTTP fino para o microserviço NaraNN.

O NaraNN classifica o estágio de leitura de uma criança a partir de um áudio
``.ogg`` e expõe uma API assíncrona via Redis (submit -> poll). Este módulo
isola o protocolo HTTP do resto do backend Nara — quem usar deve conhecer
apenas as funções públicas e as exceções abaixo.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return os.getenv("NARAONN_BASE_URL", "http://naraonn:8080").rstrip("/")


def _submit_timeout() -> int:
    return int(os.getenv("NARAONN_SUBMIT_TIMEOUT_SECONDS", "120"))


def _poll_timeout() -> int:
    return int(os.getenv("NARAONN_POLL_TIMEOUT_SECONDS", "30"))


class NaraonnError(Exception):
    """Erro genérico ao falar com o NaraNN."""


class NaraonnUnavailable(NaraonnError):
    """Falha de rede, timeout ou 5xx — o microserviço está fora do ar."""


class NaraonnInvalidResponse(NaraonnError):
    """O NaraNN respondeu mas o payload não bate com o contrato esperado."""


def submit_job(ogg_bytes: bytes, name_hint: str) -> str:
    """Envia o áudio para o NaraNN e devolve o ``job_id``.

    Levanta ``NaraonnUnavailable`` em problemas de rede/timeout/5xx e
    ``NaraonnInvalidResponse`` se o payload não trouxer ``job_id``.
    """
    url = f"{_base_url()}/jobs"
    files = {"file": (name_hint or "audio.ogg", ogg_bytes, "audio/ogg")}
    try:
        response = requests.post(url, files=files, timeout=_submit_timeout())
    except requests.RequestException as exc:
        logger.warning("[NARAONN] submit_job falhou (rede): %s", exc)
        raise NaraonnUnavailable(str(exc)) from exc

    if response.status_code >= 500:
        raise NaraonnUnavailable(f"HTTP {response.status_code}: {response.text[:200]}")
    if not response.ok:
        raise NaraonnInvalidResponse(f"HTTP {response.status_code}: {response.text[:200]}")

    try:
        data = response.json()
    except ValueError as exc:
        raise NaraonnInvalidResponse(f"resposta não-JSON: {response.text[:200]}") from exc

    job_id = data.get("job_id")
    if not job_id:
        raise NaraonnInvalidResponse(f"job_id ausente em {data}")
    return str(job_id)


def get_job(job_id: str) -> dict:
    """Consulta o estado de um job. Retorna o dicionário público da API do NaraNN."""
    url = f"{_base_url()}/jobs/{job_id}"
    try:
        response = requests.get(url, timeout=_poll_timeout())
    except requests.RequestException as exc:
        logger.warning("[NARAONN] get_job falhou (rede): %s", exc)
        raise NaraonnUnavailable(str(exc)) from exc

    if response.status_code == 404:
        raise NaraonnInvalidResponse("job não encontrado no NaraNN")
    if response.status_code >= 500:
        raise NaraonnUnavailable(f"HTTP {response.status_code}: {response.text[:200]}")
    if not response.ok:
        raise NaraonnInvalidResponse(f"HTTP {response.status_code}: {response.text[:200]}")

    try:
        return response.json()
    except ValueError as exc:
        raise NaraonnInvalidResponse(f"resposta não-JSON: {response.text[:200]}") from exc


def delete_job(job_id: str) -> bool:
    """Remove um job do NaraNN. Best-effort — nunca levanta, retorna False em falha."""
    if not job_id:
        return False
    url = f"{_base_url()}/jobs/{job_id}"
    try:
        response = requests.delete(url, timeout=_poll_timeout())
    except requests.RequestException as exc:
        logger.warning("[NARAONN] delete_job falhou: %s", exc)
        return False
    return response.ok


def health() -> Optional[dict]:
    """Heartbeat. Retorna o JSON ou None se o serviço estiver inacessível."""
    url = f"{_base_url()}/health"
    try:
        response = requests.get(url, timeout=_poll_timeout())
    except requests.RequestException:
        return None
    if not response.ok:
        return None
    try:
        return response.json()
    except ValueError:
        return None