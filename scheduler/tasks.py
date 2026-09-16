"""Celery tasks for the Nara scheduler."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
from celery import shared_task

from celery_app import app  # noqa: F401 — garante registro das tasks
from config import load_escolas


logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = float(os.getenv('REFRESH_REQUEST_TIMEOUT', '60'))


@shared_task(name='tasks.agendar_refresh_coordenacao')
def agendar_refresh_coordenacao() -> dict[str, Any]:
    """
    Periodic entry-point invoked by Celery beat. Itera o registry de escolas e
    enfileira uma subtask por escola para recomputar o cache da coordenação.
    """
    escolas = load_escolas()
    if not escolas:
        logger.warning('Nenhuma escola registrada em escolas.yaml.')
        return {'enqueued': 0}

    for escola in escolas:
        refresh_coordenacao_cache.delay(escola.id)

    logger.info('Refresh de cache enfileirado para %d escola(s).', len(escolas))
    return {'enqueued': len(escolas)}


def _chamar_refresh(escola) -> dict[str, Any]:
    """Faz o POST no endpoint interno do backend da escola.

    Pode levantar `requests.RequestException` (conexão/5xx) — quem chama via
    task tem `autoretry_for` para reagendar.
    """
    if not escola.internal_token:
        logger.error(
            'Escola %s sem token interno configurado; pulando.', escola.id
        )
        return {'escola_id': escola.id, 'status': 'missing_token'}

    # Cada backend resolve seu próprio NARA_INSTITUICAO_ID; só mandamos no
    # body se o registry trouxer um override explícito (multi-tenant).
    payload: dict[str, Any] = {}
    if escola.instituicao_id:
        payload['instituicao_id'] = escola.instituicao_id
    headers = {
        'X-Internal-Token': escola.internal_token,
        'Content-Type': 'application/json',
    }

    logger.info(
        'Refresh de cache para escola=%s instituicao=%s',
        escola.id,
        escola.instituicao_id or '<env do backend>',
    )
    response = requests.post(
        escola.refresh_url,
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code >= 500:
        response.raise_for_status()
    if response.status_code in (401, 403):
        logger.error(
            'Token interno REJEITADO pelo backend da escola=%s (status=%s). '
            'Confira que o internal_token do registry casa com o '
            'NARA_INTERNAL_TOKEN do backend. body=%s',
            escola.id,
            response.status_code,
            response.text[:500],
        )
        return {
            'escola_id': escola.id,
            'status': 'invalid_token',
            'http_status': response.status_code,
        }
    if response.status_code >= 400:
        logger.error(
            'Refresh falhou para escola=%s status=%s body=%s',
            escola.id,
            response.status_code,
            response.text[:500],
        )
        return {
            'escola_id': escola.id,
            'status': 'error',
            'http_status': response.status_code,
        }

    body = response.json() if response.content else {}
    logger.info(
        'Cache atualizado escola=%s data_ref=%s',
        escola.id,
        body.get('data_referencia'),
    )
    return {
        'escola_id': escola.id,
        'status': 'ok',
        'http_status': response.status_code,
        'data_referencia': body.get('data_referencia'),
    }


@shared_task(
    name='tasks.refresh_coordenacao_cache',
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def refresh_coordenacao_cache(self, escola_id: str) -> dict[str, Any]:
    """Regenera o cache de uma escola identificada pelo id do registry."""
    escolas = {e.id: e for e in load_escolas()}
    escola = escolas.get(str(escola_id))
    if escola is None:
        logger.error('Escola %s não encontrada no registry.', escola_id)
        return {'escola_id': str(escola_id), 'status': 'not_found'}
    return _chamar_refresh(escola)


@shared_task(
    name='tasks.refresh_coordenacao_cache_por_instituicao',
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def refresh_coordenacao_cache_por_instituicao(self, instituicao_id: str) -> dict[str, Any]:
    """Regenera o cache resolvendo a escola pelo `instituicao_id` do registry.

    Usada pelo botão "Atualizar" do painel: o backend só conhece o próprio
    `NARA_INSTITUICAO_ID`, então o registry da escola precisa ter o
    `instituicao_id` preenchido para o worker descobrir backend_url + token.
    """
    escola = next(
        (e for e in load_escolas() if e.instituicao_id == str(instituicao_id)),
        None,
    )
    if escola is None:
        logger.error(
            'Nenhuma escola no registry com instituicao_id=%s. '
            'Preencha o campo instituicao_id no ESCOLAS_JSON/escolas.yaml.',
            instituicao_id,
        )
        return {'instituicao_id': str(instituicao_id), 'status': 'not_found'}
    return _chamar_refresh(escola)
