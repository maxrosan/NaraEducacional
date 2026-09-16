FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY celery_app.py config.py tasks.py ./

# Imagem do Celery worker. O beat roda em processo separado: via
# docker-compose o `command` é sobrescrito; no Easypanel (que não permite
# sobrescrever o comando por serviço) use o `Dockerfile.beat`.
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=INFO"]
