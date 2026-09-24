"""
Utilitários genéricos usados pelos endpoints que envolvem IA e upload de
arquivo (planejamento, análise de produção, leitura, etc.).

Fonte única destas funções: a cópia antiga em views_legacy.py foi removida.
Esta versão corrige a legada em três pontos — não reintroduzir aquelas:
  * run_with_timeout propaga o ContextVar do tenant para a thread (sem isso
    as queries feitas dentro dela saíam sem filtro de escola/instituição);
  * gerar_nome_arquivo_seguro não põe o nome da criança na chave do storage
    (LGPD) e usa `secrets`, não md5 de dados previsíveis;
  * check_rate_limit conta por usuário, não por IP compartilhado da escola.
"""

import contextvars
import os
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from django.core.cache import cache
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

UPLOAD_RATE_LIMIT = _get_int_env("UPLOAD_RATE_LIMIT_PER_MINUTE", 10)
UPLOAD_RATE_WINDOW_SECONDS = _get_int_env("UPLOAD_RATE_LIMIT_WINDOW_SECONDS", 60)

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
    """Executa uma função em thread pool com timeout.

    A função roda numa CÓPIA do contexto atual: ContextVars (em especial o
    escopo de tenant de `api.tenancy`) não são herdados por threads do pool, e
    qualquer query feita lá dentro sairia sem filtro de tenant.
    """
    ctx = contextvars.copy_context()
    future = THREAD_POOL.submit(ctx.run, func, *args, **kwargs)
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

def check_rate_limit(request, prefix: str):
    """Rate limiting por usuário (ou IP, se anônimo), com janela fixa.

    Retorna ``(permitido, retry_after_segundos)``.
    """
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        identidade = f"u:{user.pk}"
    else:
        identidade = f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"
    key = f"rl:{prefix}:{identidade}"
    now = time.time()

    stored = cache.get(key)
    if stored and now <= stored[1]:
        count, expires_at = stored
    else:
        count, expires_at = 0, now + UPLOAD_RATE_WINDOW_SECONDS

    count += 1
    cache.set(key, (count, expires_at), timeout=max(int(expires_at - now), 1))

    if count > UPLOAD_RATE_LIMIT:
        return False, max(int(expires_at - now), 1)
    return True, None


def gerar_nome_arquivo_seguro(nome_aluno, arquivo_original):
    """Gera ``(nome_do_arquivo, hash)`` para armazenar uma produção.

    O nome NÃO leva o nome da criança (dado pessoal de menor em chave de
    storage/URL); ``nome_aluno`` é mantido na assinatura por compatibilidade.
    O hash vem de ``secrets`` — é usado como ``arquivo_hash`` (único) e aparece
    em URL pública, então não pode ser previsível.
    """
    del nome_aluno  # intencionalmente não usado (LGPD)
    file_hash = secrets.token_hex(8)  # 16 caracteres

    extensao = os.path.splitext(arquivo_original or "")[1].lower()
    if extensao not in ALLOWED_IMAGE_EXTENSIONS:
        extensao = ".jpg"
    extensao = re.sub(r"[^a-z.]", "", extensao)

    return f"{file_hash}_{int(time.time())}{extensao}", file_hash