"""Cliente HTTP para o microserviço transcription_service (faster-whisper).

O serviço agora é assíncrono: um POST /transcribe enfileira o áudio e devolve
um job_id; o cliente faz polling em GET /jobs/{id} até o job ficar terminal.
"""

import logging
import os
import time
from typing import Optional

import httpx

from api.views_legacy import IA_AUDIO_TIMEOUT_SECONDS

from .base import TranscriptionBackend, TranscriptionError

logger = logging.getLogger(__name__)

# Polling: começa rápido (áudio curto fica pronto logo), cresce até 5s.
_POLL_INITIAL_SECONDS = 1.0
_POLL_MAX_SECONDS = 5.0
_POLL_BACKOFF_FACTOR = 1.4

# Quantas retentativas fazer em 429 (fila cheia) antes de desistir.
_SUBMIT_MAX_RETRIES = 3

# Margem deixada antes do timeout do worker do gunicorn. Sem essa folga, o
# loop de polling chega ao final exatamente quando o gunicorn manda SIGABRT
# no worker, o que aborta o time.sleep() com SystemExit(1) e cai no Sentry
# (issue NARA-8A). Com a folga, conseguimos disparar nosso próprio
# TimeoutError e devolver HTTP 504 para o cliente.
_GUNICORN_TIMEOUT_BUFFER_SECONDS = 15.0
_DEFAULT_GUNICORN_TIMEOUT = 120.0

# Marcadores no erro do job indicando áudio corrompido enviado pelo cliente.
# Quando aparecem, logamos em WARNING para não poluir Sentry com bugs do
# usuário (gravação truncada, webm sem cabeçalho, etc.) — a view já converte
# isso em HTTP 422 para o cliente.
_INVALID_AUDIO_MARKERS = (
    "invalid data found when processing input",
    "1094995529",
    "moov atom not found",
    "could not find codec parameters",
    "end of file",
)


def _is_invalid_audio_error(message: str) -> bool:
    lowered = (message or "").lower()
    return any(marker in lowered for marker in _INVALID_AUDIO_MARKERS)


def _base_url() -> str:
    return os.getenv("TRANSCRIPTION_SERVICE_URL", "http://transcription:8000").rstrip("/")


def _internal_token() -> Optional[str]:
    value = os.getenv("TRANSCRIPTION_SERVICE_TOKEN", "").strip()
    return value or None


def _gunicorn_worker_timeout() -> float:
    raw = os.getenv("GUNICORN_TIMEOUT", "").strip()
    if not raw:
        return _DEFAULT_GUNICORN_TIMEOUT
    try:
        return max(30.0, float(raw))
    except ValueError:
        return _DEFAULT_GUNICORN_TIMEOUT


def _total_deadline_seconds() -> float:
    """
    Deadline total (upload + fila + processamento). Large v3 em CPU processa
    ~1x realtime, então um áudio de 1 minuto pode levar 40-90s. Usamos o
    mesmo limite do IA_AUDIO_TIMEOUT, com piso de 120s para evitar cortar
    transcrições legítimas — mas sempre abaixo do timeout do worker do
    gunicorn para não sermos mortos com SIGABRT no meio do polling.
    """
    requested = max(float(IA_AUDIO_TIMEOUT_SECONDS), 120.0)
    worker_cap = max(_gunicorn_worker_timeout() - _GUNICORN_TIMEOUT_BUFFER_SECONDS, 30.0)
    return min(requested, worker_cap)


def _auth_headers() -> dict:
    headers = {}
    token = _internal_token()
    if token:
        headers["X-Internal-Token"] = token
    return headers


class FasterWhisperBackend(TranscriptionBackend):
    """Delega a transcrição para o microserviço interno transcription_service."""

    name = "faster_whisper"

    def transcribe(self, arquivo_path: str, language: str = "pt") -> str:
        deadline = time.monotonic() + _total_deadline_seconds()
        base = _base_url()
        headers = _auth_headers()

        # httpx.Client com timeouts curtos por request — o deadline total é
        # respeitado pelo nosso loop de polling, não pelo timeout do socket.
        client_timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0)

        with httpx.Client(timeout=client_timeout) as client:
            job_id = self._submit(client, base, headers, arquivo_path, language, deadline)
            return self._poll_until_done(client, base, headers, job_id, deadline)

    # -------- submit --------

    def _submit(
        self,
        client: httpx.Client,
        base: str,
        headers: dict,
        arquivo_path: str,
        language: str,
        deadline: float,
    ) -> str:
        url = f"{base}/transcribe"
        attempt = 0
        while True:
            attempt += 1
            try:
                with open(arquivo_path, "rb") as audio_file:
                    files = {
                        "file": (
                            os.path.basename(arquivo_path),
                            audio_file,
                            "application/octet-stream",
                        )
                    }
                    data = {"language": language or "", "include_segments": "false"}
                    response = client.post(url, files=files, data=data, headers=headers)
            except httpx.ConnectError as e:
                logger.error("[WHISPER:faster_whisper] Não foi possível conectar em %s: %s", url, e)
                raise ConnectionError("Serviço de transcrição indisponível.") from e

            if response.status_code == 202:
                payload = response.json()
                job_id = payload.get("job_id")
                if not job_id:
                    raise TranscriptionError("Resposta inválida do serviço de transcrição")
                logger.info("[WHISPER:faster_whisper] Job enfileirado id=%s", job_id)
                return job_id

            if response.status_code == 503:
                logger.warning("[WHISPER:faster_whisper] Modelo ainda carregando no serviço")
                raise ConnectionError("Serviço de transcrição ainda não está pronto.")

            if response.status_code == 429 and attempt <= _SUBMIT_MAX_RETRIES:
                retry_after = self._parse_retry_after(response, default=5.0)
                if time.monotonic() + retry_after > deadline:
                    raise TimeoutError("Fila do serviço de transcrição saturada.")
                logger.warning(
                    "[WHISPER:faster_whisper] Fila cheia, retry em %.1fs (tentativa %d/%d)",
                    retry_after,
                    attempt,
                    _SUBMIT_MAX_RETRIES,
                )
                time.sleep(retry_after)
                continue

            logger.error(
                "[WHISPER:faster_whisper] Erro %s ao submeter: %s",
                response.status_code,
                response.text[:200],
            )
            raise TranscriptionError(
                f"Serviço de transcrição retornou HTTP {response.status_code}"
            )

    # -------- poll --------

    def _poll_until_done(
        self,
        client: httpx.Client,
        base: str,
        headers: dict,
        job_id: str,
        deadline: float,
    ) -> str:
        url = f"{base}/jobs/{job_id}"
        delay = _POLL_INITIAL_SECONDS

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.error("[WHISPER:faster_whisper] Deadline atingido aguardando job %s", job_id)
                raise TimeoutError("Transcrição demorou mais que o permitido.")

            try:
                response = client.get(url, headers=headers)
            except httpx.ConnectError as e:
                logger.error("[WHISPER:faster_whisper] Erro de conexão no poll: %s", e)
                raise ConnectionError("Serviço de transcrição indisponível.") from e

            if response.status_code == 404:
                # Job foi purgado antes de terminar (raro): tratar como falha.
                raise TranscriptionError("Job de transcrição expirou antes de completar.")

            if response.status_code >= 400:
                logger.error(
                    "[WHISPER:faster_whisper] Erro %s no poll: %s",
                    response.status_code,
                    response.text[:200],
                )
                raise TranscriptionError(
                    f"Serviço de transcrição retornou HTTP {response.status_code}"
                )

            payload = response.json()
            status_value = payload.get("status")

            if status_value == "succeeded":
                result = payload.get("result") or {}
                text = (result.get("text") or "").strip()
                logger.info(
                    "[WHISPER:faster_whisper] Transcrição pronta job=%s lang=%s duracao=%.1fs proc=%sms: %s...",
                    job_id,
                    result.get("language"),
                    result.get("duration_seconds", 0.0),
                    result.get("processing_ms"),
                    text[:100],
                )
                return text

            if status_value == "failed":
                erro = payload.get("error") or "unknown error"
                if _is_invalid_audio_error(erro):
                    logger.warning(
                        "[WHISPER:faster_whisper] Job %s recebeu áudio inválido do cliente: %s",
                        job_id,
                        erro,
                    )
                else:
                    logger.error("[WHISPER:faster_whisper] Job %s falhou: %s", job_id, erro)
                raise TranscriptionError(f"Transcrição falhou: {erro}")

            # status: queued | processing -> espera e tenta de novo
            sleep_for = min(delay, remaining)
            time.sleep(sleep_for)
            delay = min(delay * _POLL_BACKOFF_FACTOR, _POLL_MAX_SECONDS)

    # -------- helpers --------

    @staticmethod
    def _parse_retry_after(response: httpx.Response, default: float) -> float:
        value = response.headers.get("Retry-After", "").strip()
        if not value:
            return default
        try:
            return max(1.0, float(value))
        except ValueError:
            return default
