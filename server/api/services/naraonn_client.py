"""Cliente HTTP fino para o microserviço NaraNN.

O NaraNN classifica o estágio de leitura de uma criança a partir de um áudio
``.ogg`` e expõe uma API assíncrona via Redis (submit -> poll). Este módulo
isola o protocolo HTTP do resto do backend Nara — quem usar deve conhecer
apenas as funções públicas e as exceções abaixo.
"""

from __future__ import annotations

import logging
import os

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


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _request(method: str, path: str, timeout: int, **kwargs) -> requests.Response:
    """Faz a requisição; converte qualquer falha de rede/timeout em ``NaraonnUnavailable``."""
    try:
        return requests.request(method, f"{_base_url()}{path}", timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        logger.warning("[NARAONN] %s %s falhou (rede): %s", method, path, exc)
        raise NaraonnUnavailable(str(exc)) from exc


def _json_ou_erro(response: requests.Response) -> dict:
    """Valida o status HTTP e devolve o corpo JSON, ou levanta a exceção adequada."""
    if response.status_code >= 500:
        raise NaraonnUnavailable(f"HTTP {response.status_code}: {response.text[:200]}")
    if not response.ok:
        raise NaraonnInvalidResponse(f"HTTP {response.status_code}: {response.text[:200]}")
    try:
        return response.json()
    except ValueError as exc:
        raise NaraonnInvalidResponse(f"resposta não-JSON: {response.text[:200]}") from exc


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def submit_job(ogg_bytes: bytes, name_hint: str) -> str:
    """Envia o áudio para o NaraNN e devolve o ``job_id``.

    Levanta ``NaraonnUnavailable`` em problemas de rede/timeout/5xx e
    ``NaraonnInvalidResponse`` se o payload não trouxer ``job_id``.
    """
    files = {"file": (name_hint or "audio.ogg", ogg_bytes, "audio/ogg")}
    data = _json_ou_erro(_request("POST", "/jobs", _submit_timeout(), files=files))

    job_id = data.get("job_id") if isinstance(data, dict) else None
    if not job_id:
        raise NaraonnInvalidResponse(f"job_id ausente em {data}")
    return str(job_id)


def get_job(job_id: str) -> dict:
    """Consulta o estado de um job. Retorna o dicionário público da API do NaraNN."""
    response = _request("GET", f"/jobs/{job_id}", _poll_timeout())
    if response.status_code == 404:
        raise NaraonnInvalidResponse("job não encontrado no NaraNN")
    return _json_ou_erro(response)


def delete_job(job_id: str) -> None:
    """Remove um job do NaraNN. Best-effort — nunca levanta; falhas são apenas logadas."""
    if not job_id:
        return
    try:
        response = _request("DELETE", f"/jobs/{job_id}", _poll_timeout())
    except NaraonnUnavailable:
        return  # já logado em _request
    if not response.ok:
        logger.warning("[NARAONN] delete_job %s retornou HTTP %s", job_id, response.status_code)