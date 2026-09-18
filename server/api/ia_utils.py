"""
Utilitários genéricos usados pelos endpoints que envolvem IA e upload de
arquivo (planejamento, análise de produção, leitura, etc.).

Extraído do antigo views_legacy.py — são funções puras, sem dependência de
nenhum model específico, então não precisam de adaptação pro schema novo.
"""

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from rest_framework import status


def _get_float_env(var_name: str, default: float) -> float:
    try:
        return float(os.getenv(var_name, default))
    except (TypeError, ValueError):
        return float(default)


IA_REQUEST_TIMEOUT_SECONDS = _get_float_env("IA_REQUEST_TIMEOUT_SECONDS", 45)
IA_AUDIO_TIMEOUT_SECONDS = _get_float_env("IA_AUDIO_TIMEOUT_SECONDS", IA_REQUEST_TIMEOUT_SECONDS)

THREAD_POOL = ThreadPoolExecutor(max_workers=4)


def run_with_timeout(func, timeout_seconds, *args, **kwargs):
    """Executa uma função em thread pool com timeout."""
    future = THREAD_POOL.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        raise TimeoutError(f"Operação excedeu o limite de {timeout_seconds} segundos.")


def validate_uploaded_file(file_obj, allowed_types, allowed_extensions, max_size_bytes, contexto):
    """
    Valida tipo e tamanho do arquivo enviado, retornando uma tupla
    (mensagem, status) em caso de erro, ou None se estiver tudo certo.
    """
    if file_obj.size > max_size_bytes:
        limite_mb = max_size_bytes / (1024 * 1024)
        return (
            f"Arquivo de {contexto} excede o limite de {limite_mb:.0f}MB. Comprima o arquivo antes de enviar.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    content_type = (file_obj.content_type or "").lower()
    extension = os.path.splitext(file_obj.name)[1].lower()

    if content_type not in allowed_types and extension not in allowed_extensions:
        formatos_aceitos = sorted({*allowed_types, *{f'*{ext}' for ext in allowed_extensions}})
        return (
            f"Formato não permitido para {contexto}. Utilize formatos aceitos: {', '.join(formatos_aceitos)}.",
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    return None