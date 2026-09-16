"""Autenticação via token compartilhado (header X-Internal-Token)."""

import hmac

from fastapi import Header, HTTPException, status

from .config import settings


async def verify_internal_token(
    x_internal_token: str = Header(default="", alias="X-Internal-Token"),
) -> None:
    """
    Valida o token compartilhado. Se INTERNAL_TOKEN estiver vazio na config,
    o serviço aceita qualquer chamada (útil apenas para dev local).
    Em produção, o token é obrigatório.
    """
    expected = settings.internal_token
    if not expected:
        return

    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token",
        )
