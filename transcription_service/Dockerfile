# Dockerfile — Transcription Service (faster-whisper + FastAPI)
#
# Imagem propositalmente fina: o modelo NÃO é baixado no build.
# O download acontece no primeiro startup e fica cacheado em /models
# (monte um volume persistente aí, senão baixa ~3GB a cada deploy).

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg: faster-whisper usa para decodificar formatos variados (webm, m4a, etc.)
# libgomp1: OpenMP runtime usado pelo CTranslate2
# patchelf: usado abaixo para limpar a flag de stack executável do .so do CTranslate2
#           (kernels endurecidos como os do EasyPanel recusam carregar a lib sem isso).
#           Em Debian trixie o pacote `execstack` foi removido; patchelf --clear-execstack
#           faz a mesma coisa.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgomp1 \
        curl \
        patchelf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Workaround CTranslate2 4.4.0: remove flag de stack executável de libctranslate2.so
# e de todos os .so do pacote. A lib nativa vive em ctranslate2.libs/ (auditwheel),
# não em ctranslate2/ — então precisamos varrer ambos. Sem isso, hosts endurecidos
# falham com "cannot enable executable stack as shared object requires: Invalid
# argument" no import do ctranslate2.
RUN find /usr/local/lib/python3.11/site-packages/ctranslate2 \
         /usr/local/lib/python3.11/site-packages/ctranslate2.libs \
         -name '*.so*' -type f -print \
         -exec patchelf --clear-execstack {} \; \
    && apt-get purge -y patchelf && apt-get autoremove -y

COPY . .

# O volume montado aqui guarda os pesos do modelo entre deploys.
RUN mkdir -p /models
ENV MODEL_CACHE=/models

EXPOSE 8000

# Healthcheck amigável para EasyPanel/K8s: /readyz vira 200 só depois que o
# modelo terminou de carregar.
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD curl -fsS http://localhost:8000/readyz || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
