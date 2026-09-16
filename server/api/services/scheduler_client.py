"""Producer Celery: enfileira tasks no broker do scheduler externo.

O backend não roda worker nem beat — ele apenas *publica* a task
`tasks.refresh_coordenacao_cache` no mesmo Redis que o scheduler consome.
O worker do scheduler resolve `backend_url`/`internal_token` da escola no
seu registry e chama de volta `POST /api/internal/cache/coordenacao/`.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

# Nome registrado pela task no scheduler (`@shared_task(name=...)`).
REFRESH_TASK_NAME = 'tasks.refresh_coordenacao_cache_por_instituicao'


class SchedulerNaoConfigurado(RuntimeError):
    """Levantada quando falta CELERY_BROKER_URL ou NARA_SCHEDULER_ESCOLA_ID."""


@lru_cache(maxsize=1)
def _get_celery_app():
    broker = getattr(settings, 'CELERY_BROKER_URL', '')
    if not broker:
        raise SchedulerNaoConfigurado('CELERY_BROKER_URL não definido.')
    # Import tardio: celery só é necessário quando o enfileiramento é usado.
    from celery import Celery

    return Celery('nara_backend_producer', broker=broker)


def enfileirar_refresh_coordenacao() -> str:
    """Publica a task de refresh para a instituição deste backend.

    Usa o `NARA_INSTITUICAO_ID` (já configurado no backend) como chave; o
    worker resolve backend_url + token a partir do registry do scheduler.
    Retorna o id da task enfileirada. Levanta `SchedulerNaoConfigurado` se
    faltar configuração, ou propaga erro de conexão se o broker estiver
    inacessível.
    """
    instituicao_id = getattr(settings, 'NARA_INSTITUICAO_ID', '')
    if not instituicao_id:
        raise SchedulerNaoConfigurado('NARA_INSTITUICAO_ID não definido.')

    app = _get_celery_app()
    result = app.send_task(REFRESH_TASK_NAME, args=[instituicao_id])
    logger.info(
        'Refresh da coordenação enfileirado no scheduler: instituicao=%s task_id=%s',
        instituicao_id,
        result.id,
    )
    return result.id
