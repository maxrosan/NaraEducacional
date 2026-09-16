"""Celery application for the Nara scheduler."""

from __future__ import annotations

import os
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv


# Carrega scheduler/.env quando rodando localmente (fora do compose). Em
# Docker as variáveis já vêm do ambiente via `env_file`/`environment`, e
# `override=False` garante que essas tenham prioridade sobre o arquivo.
load_dotenv(Path(__file__).resolve().parent / '.env', override=False)


BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', BROKER_URL)
TIMEZONE = os.getenv('CELERY_TIMEZONE', 'America/Sao_Paulo')

# Horário do beat diário para refresh do cache da coordenação.
BEAT_HOUR = int(os.getenv('CACHE_REFRESH_HOUR', '2'))
BEAT_MINUTE = int(os.getenv('CACHE_REFRESH_MINUTE', '0'))


app = Celery(
    'nara_scheduler',
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=['tasks'],
)

app.conf.update(
    timezone=TIMEZONE,
    enable_utc=False,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=int(os.getenv('CELERY_TASK_TIME_LIMIT', '600')),
    task_soft_time_limit=int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '540')),
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

# O painel da coordenação passou a calcular seus agregados por período
# avaliativo a cada requisição — a janela virou um bimestre em vez da história
# inteira da escola, e o custo ficou estável. Com isso o snapshot diário deixou
# de ter função e o agendamento foi desligado.
#
# A tarefa `tasks.agendar_refresh_coordenacao` e a tabela `coordenacao_cache`
# continuam existindo de propósito: os snapshots já gravados são o único
# histórico diário que temos, e mantê-los foi decisão explícita. Para voltar a
# gravar, basta reativar a entrada abaixo.
app.conf.beat_schedule = {
    # 'refresh-coordenacao-cache-daily': {
    #     'task': 'tasks.agendar_refresh_coordenacao',
    #     'schedule': crontab(hour=BEAT_HOUR, minute=BEAT_MINUTE),
    # },
}


if __name__ == '__main__':
    app.start()
