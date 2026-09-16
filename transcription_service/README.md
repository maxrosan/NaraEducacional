# Nara Transcription Service

Microserviço HTTP de transcrição de áudio usando [**faster-whisper**](https://github.com/SYSTRAN/faster-whisper) + **FastAPI**.

É acionado pelo backend Django quando `TRANSCRIPTION_PROVIDER=faster_whisper`. Serve como alternativa local/privada à OpenAI Whisper API, com qualidade equivalente ou superior (usa por padrão `Whisper Large v3`) e zero custo por minuto transcrito.

---

## Visão geral

- **Stack**: FastAPI, uvicorn, faster-whisper, CTranslate2, ffmpeg
- **Execução**: CPU (padrão) ou GPU/CUDA (opcional)
- **Modelo padrão**: `large-v3` — melhor qualidade disponível para PT-BR
- **Autenticação**: token compartilhado via header `X-Internal-Token`
- **Modelo de execução**: fila interna com pool de workers. `POST /transcribe` retorna um `job_id` imediatamente; o cliente faz polling em `GET /jobs/{id}` até o job ficar `succeeded` ou `failed`.

Endpoints expostos:

| Método | Rota | Uso |
|---|---|---|
| `POST` | `/transcribe` | Enfileira um áudio e devolve `job_id` (HTTP 202). Retorna 429 + `Retry-After` se a fila estiver cheia. |
| `GET`  | `/jobs/{job_id}` | Status + resultado do job. `404` se o job não existe ou expirou. |
| `GET`  | `/healthz` | Liveness (sempre 200 enquanto o processo está vivo) |
| `GET`  | `/readyz`  | Readiness (503 até o modelo terminar de carregar) |

---

## Como rodar

### Rodando com Docker Compose (recomendado)

A partir da raiz do repositório, o serviço `transcription` já está declarado no `docker-compose.yml`:

```bash
# Dev: usa modelo "small" por padrão para ficar leve
docker compose up -d transcription
docker compose logs -f transcription
```

Para forçar o uso de um modelo diferente em dev:

```bash
TRANSCRIPTION_MODEL_SIZE=large-v3 docker compose up -d transcription
```

Em produção (`docker-compose.prod.yml`), o padrão já é `large-v3` com volume `whisper_models` montado em `/models`.

Testando localmente (porta `8003` é exposta em dev):

```bash
curl -sS http://localhost:8003/healthz
curl -sS http://localhost:8003/readyz   # retorna 503 enquanto o modelo carrega

# 1) Enfileira o áudio — resposta imediata com job_id (HTTP 202)
curl -X POST http://localhost:8003/transcribe \
  -H "X-Internal-Token: $TRANSCRIPTION_SERVICE_TOKEN" \
  -F "file=@exemplo.wav" \
  -F "language=pt"
# {"job_id":"3f2c...","status":"queued"}

# 2) Faz polling até status == "succeeded" (ou "failed")
curl -sS http://localhost:8003/jobs/3f2c... \
  -H "X-Internal-Token: $TRANSCRIPTION_SERVICE_TOKEN"
```

Resposta do `GET /jobs/{id}` quando pronto:

```json
{
  "job_id": "3f2c...",
  "status": "succeeded",
  "created_at": 1729800001.23,
  "started_at": 1729800001.41,
  "finished_at": 1729800049.53,
  "result": {
    "text": "Oi pessoal, hoje observei que a Ana...",
    "language": "pt",
    "language_probability": 0.998,
    "duration_seconds": 42.3,
    "processing_ms": 48120,
    "model": "large-v3",
    "backend": "faster-whisper",
    "segments": null
  },
  "error": null
}
```

Enquanto o job ainda está em execução, `status` é `queued` ou `processing` e `result` é `null`. Em caso de erro, `status == "failed"` e `error` traz a mensagem.

### Rodando direto com Python (sem Docker)

Exige `ffmpeg` instalado localmente.

```bash
cd transcription_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edite .env com MODEL_SIZE, INTERNAL_TOKEN, etc.

python run.py
# ou
uvicorn main:app --host 0.0.0.0 --port 8000
```

Na primeira vez, o download do modelo (~3GB para `large-v3`) acontece automaticamente e fica cacheado em `MODEL_CACHE` (default `/models`; em dev local aponte para algo como `./models`).

---

## Configuração

Variáveis de ambiente (também disponíveis em `.env.example`):

| Variável | Default | Descrição |
|---|---|---|
| `MODEL_SIZE` | `large-v3` | Tamanho do modelo Whisper (`tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`) |
| `DEVICE` | `cpu` | `cpu` ou `cuda` |
| `COMPUTE_TYPE` | `int8` | CPU: `int8`. GPU: `float16` ou `int8_float16` |
| `CPU_THREADS` | `0` | `0` = usa todos os núcleos |
| `NUM_WORKERS` | `1` | Quantos segmentos processar em paralelo |
| `MODEL_CACHE` | `/models` | Diretório onde os pesos ficam armazenados (volume persistente) |
| `MAX_CONCURRENT` | `2` | Número de workers que consomem a fila em paralelo |
| `QUEUE_MAX_SIZE` | `50` | Capacidade da fila interna. Excedendo, `POST /transcribe` retorna 429 + `Retry-After` |
| `JOB_TTL_SECONDS` | `3600` | Tempo que um job terminal fica disponível em `GET /jobs/{id}` antes de ser purgado |
| `JANITOR_INTERVAL_SECONDS` | `60` | Frequência com que o janitor remove jobs expirados |
| `DEFAULT_LANGUAGE` | `pt` | Idioma ISO-639-1 padrão quando o cliente não informa |
| `VAD_FILTER` | `true` | Ativa Voice Activity Detection |
| `BEAM_SIZE` | `5` | Qualidade vs velocidade (1 = greedy, 5 = padrão) |
| `INTERNAL_TOKEN` | *(vazio)* | Se definido, exige `X-Internal-Token` bater. Vazio = aceita qualquer chamada (use só em dev) |
| `MAX_UPLOAD_MB` | `100` | Limite de tamanho do upload |
| `PORT` | `8000` | Porta HTTP |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SENTRY_DSN` | *(vazio)* | Ativa Sentry quando preenchido |
| `SENTRY_ENVIRONMENT` | `development` | Tag de ambiente no Sentry |

---

## Como o backend Django chama este serviço

No backend, `api/services/audio.py` chama `transcrever_audio()` sem saber qual backend está ativo. A seleção acontece em `api/transcription/factory.py` lendo `TRANSCRIPTION_PROVIDER`:

- `TRANSCRIPTION_PROVIDER=openai` (padrão) → usa `OpenAIBackend`, chamando a API da OpenAI.
- `TRANSCRIPTION_PROVIDER=faster_whisper` → usa `FasterWhisperBackend`, que faz `POST /transcribe` neste serviço.

Para ativar o backend local em qualquer ambiente:

```bash
# .env (raiz ou server/)
TRANSCRIPTION_PROVIDER=faster_whisper
TRANSCRIPTION_SERVICE_URL=http://transcription:8000   # nome do serviço no compose
TRANSCRIPTION_SERVICE_TOKEN=<mesmo valor de INTERNAL_TOKEN>
```

Aliases aceitos (todos equivalentes a `faster_whisper`): `faster-whisper`, `fasterwhisper`, `fastwhisper`, `local`.

---

## Sobre o download do modelo

- O modelo **NÃO** é embutido na imagem Docker (que fica com ~500MB).
- No primeiro startup, `WhisperModel(...)` baixa os pesos do HuggingFace para o diretório `MODEL_CACHE`.
- Em produção o volume `whisper_models` é montado em `/models`, então o download acontece uma única vez — restarts e redeploys reutilizam o cache.
- `/readyz` só devolve 200 depois que o modelo terminou de carregar; até lá, o backend detecta 503 e responde ao usuário com mensagem apropriada (ou cai para OpenAI se você preferir manter `TRANSCRIPTION_PROVIDER=openai` como default).
- Primeira subida consome ~3GB de download + ~1min de carga. Restarts subsequentes: 30-60s.

### Trocar de modelo

Basta alterar `MODEL_SIZE` no ambiente e reiniciar o container. Se o novo modelo ainda não estiver em cache, ele é baixado na próxima inicialização.

---

## Rodando em GPU (opcional)

Para máquinas com NVIDIA + drivers + `nvidia-container-toolkit`:

```yaml
# docker-compose.gpu.yml (exemplo)
transcription:
  environment:
    DEVICE: cuda
    COMPUTE_TYPE: float16
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

Transcrição de 1min de áudio cai de ~40-90s (CPU int8) para ~3-10s (GPU float16).

---

## Testes

```bash
cd transcription_service
pip install pytest httpx
pytest -q
```

Os smoke tests em `tests/test_api.py` **não carregam o modelo real** — validam apenas contrato de endpoints, 503 adequado quando o modelo ainda não está pronto, etc.

---

## Deploy na EasyPanel

1. Criar app chamado `transcription`.
2. **Source**: mesmo repositório Git do Nara.
3. **Build Path**: `/transcription_service`.
4. **Dockerfile**: `Dockerfile`.
5. **Port**: `8000` (mantenha sem domínio público — rede interna apenas).
6. **Volumes**: mount persistente em `/models` com pelo menos 10GB.
7. **Environment variables**: preencher `MODEL_SIZE`, `INTERNAL_TOKEN`, `LOG_LEVEL`, etc.
8. **Resources**: 4 vCPU / 6GB RAM recomendado para `large-v3` em CPU.
9. **Health check**:
   - Path: `/readyz`
   - Initial delay: `300s` (para cobrir primeiro download do modelo)
   - Interval: `30s`

No app do backend (`backend`), apontar:

```
TRANSCRIPTION_PROVIDER=faster_whisper
TRANSCRIPTION_SERVICE_URL=http://<projeto>_transcription:8000
TRANSCRIPTION_SERVICE_TOKEN=<mesmo valor de INTERNAL_TOKEN>
```

---

## Troubleshooting

**503 "Model is still loading"** — o modelo ainda está sendo carregado. Normal nos primeiros minutos do primeiro deploy (download) ou após um restart (carregamento em RAM).

**"Serviço de transcrição indisponível"** (no backend) — verifique `TRANSCRIPTION_SERVICE_URL` e se o container `transcription` está saudável (`docker compose ps`).

**401 "Invalid or missing X-Internal-Token"** — o valor de `TRANSCRIPTION_SERVICE_TOKEN` (backend) precisa bater com `INTERNAL_TOKEN` (serviço).

**429 "Transcription queue is full"** — o serviço está recebendo mais submissões do que consegue processar. Cliente deve respeitar o header `Retry-After` e tentar de novo. Se acontecer com frequência: aumentar `MAX_CONCURRENT` (se houver CPU/RAM disponível), subir uma segunda réplica, ou aumentar `QUEUE_MAX_SIZE` (só esconde o problema, não resolve).

**404 no `GET /jobs/{id}`** — o job foi purgado após `JOB_TTL_SECONDS` (default 1h) ou o id é inválido. Cliente deve considerar uma falha terminal e refazer o upload se ainda precisar do resultado.

**Transcrição muito lenta** — em CPU com `large-v3`, é normal 1× realtime (áudio de 1min leva ~1min). Opções para acelerar:
- Reduzir `MODEL_SIZE` para `large-v3-turbo` ou `medium`.
- Baixar `BEAM_SIZE` para `1`.
- Aumentar `CPU_THREADS` se houver núcleos disponíveis.
- Mover para GPU.

**OOM ao subir** — `large-v3` em `int8` usa ~4-5GB. Se não tiver essa RAM disponível, use `medium` (~2GB) ou `small` (~1GB).
