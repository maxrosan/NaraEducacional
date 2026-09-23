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


def _get_int_env(var_name: str, default: int) -> int:
    try:
        return int(os.getenv(var_name, default))
    except (TypeError, ValueError):
        return int(default)


IA_REQUEST_TIMEOUT_SECONDS = _get_float_env("IA_REQUEST_TIMEOUT_SECONDS", 45)
IA_AUDIO_TIMEOUT_SECONDS = _get_float_env("IA_AUDIO_TIMEOUT_SECONDS", IA_REQUEST_TIMEOUT_SECONDS)

MAX_IMAGE_SIZE_BYTES = _get_int_env("MAX_IMAGE_UPLOAD_MB", 10) * 1024 * 1024
MAX_AUDIO_SIZE_BYTES = _get_int_env("MAX_AUDIO_UPLOAD_MB", 50) * 1024 * 1024

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/jpg", "image/heic", "image/heif",
}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

# Mapa extensão -> mime type canônico. Usado quando o navegador não envia um
# Content-Type confiável (vazio ou "application/octet-stream") — comum em
# arquivos HEIC/HEIF fora do Safari.
CANONICAL_MIME_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def resolve_mime_type(file_obj, allowed_types):
    """Retorna um mime type confiável para persistir e mandar ao storage.

    Prioriza o Content-Type do navegador quando já é um dos aceitos; caso
    contrário, infere pela extensão do nome do arquivo.
    """
    content_type = (file_obj.content_type or "").lower()
    if content_type in allowed_types:
        return content_type
    extension = os.path.splitext(file_obj.name)[1].lower()
    return CANONICAL_MIME_BY_EXTENSION.get(extension, content_type or "application/octet-stream")


ALLOWED_AUDIO_MIME_TYPES = {
    "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3",
    "audio/webm", "audio/ogg", "audio/m4a",
}
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".mpeg", ".webm", ".ogg", ".m4a"}

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