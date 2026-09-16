# NARA

Plataforma de apoio pedagógico com geração de relatórios BNCC assistida por IA.

## Funcionalidades principais

- **Registros pedagógicos**: observações guiadas por perguntas BNCC, registros livres, transcrição de áudio (Whisper OpenAI ou faster-whisper local + redução de ruído) e análise de escrita/desenho por visão computacional.
- **Portfólio da criança**: upload de mídia com compressão no cliente (`browser-image-compression`) e armazenamento em S3.
- **Planejamento semanal por turma**: sugestões de habilidades BNCC via IA.
- **Relatórios BNCC assistidos por IA**: geração, edição rica (TipTap) e exportação PDF. Download individual ou em lote (ZIP com streaming de progresso). Coordenadores podem editar relatórios diretamente pela aba "Acompanhamento de Relatórios" — edições invalidam o PDF cacheado para garantir que o próximo download reflita o conteúdo atual.
- **Painel do coordenador**: dashboard consolidado (alimentado por snapshot D-1 pré-computado, ver [Scheduler](#scheduler-cache-da-coordenação)), alertas de frequência de registro, indicadores de participação docente e linguagem, listagem paginada de relatórios.
- **Perfis e permissões**: `admin`, `coordenador`, `professor`, `professor_especialista`, `especialista`.

## Estrutura do repositório

- `server/`: API Django (PostgreSQL, OpenAI e armazenamento S3).
- `client/`: SPA React/Vite que consome a API.
- `report_generator/`: microserviço FastAPI + Playwright que renderiza HTML em PDF. Roda em container próprio e é consumido internamente pelo backend.
- `transcription_service/`: microserviço FastAPI + faster-whisper para transcrição local de áudio (Whisper Large v3). Alternativa à OpenAI Whisper API, selecionada via `TRANSCRIPTION_PROVIDER`. Veja [transcription_service/README.md](transcription_service/README.md).
- `scheduler/`: Celery beat + worker centralizado que gera diariamente (D-1) o snapshot agregado do painel da coordenação em cada escola. Veja [scheduler/README.md](scheduler/README.md).
- `docker/`: artefatos de infraestrutura (Nginx, templates e scripts de entrypoint).
- `scripts/`: rotinas auxiliares de automação e testes locais.

## Documentação

- Guia de implantação no Easypanel: [docs/easypanel-deploy.md](docs/easypanel-deploy.md)

## Requisitos

- Docker + Docker Compose (recomendado para desenvolvimento e produção).
- Python 3.11+ e Node.js 18+ para execução local sem Docker.
- PostgreSQL 14+ quando executar o backend localmente sem Docker.

## Configuração de ambiente

Este projeto não fornece credenciais de desenvolvimento. Todas as chaves e credenciais devem ser provisionadas fora do repositório.

### Com Docker (recomendado)

```bash
cp .env.example .env
```

Edite `.env` com as credenciais reais de banco, OpenAI e AWS S3.

### Sem Docker

```bash
cp server/.env.example server/.env
cp client/.env.example client/.env
```

- O backend prioriza `server/.env` e, caso não exista, lê `.env` na raiz.
- O frontend (Vite) só expõe variáveis com prefixo `VITE_`.

## Desenvolvimento com Docker

```bash
docker-compose up -d --build
```

Serviços padrão:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8001`
- Report Generator (PDF): `http://localhost:8002` (exposto apenas para dev; em produção permanece interno à rede do compose)
- Transcription Service (faster-whisper): `http://localhost:8003` (exposto apenas para dev; em produção permanece interno)
- PostgreSQL local (somente com perfil `local-db`): porta definida em `POSTGRES_PORT` no `.env`

Para iniciar o PostgreSQL local do Docker, habilite o perfil `local-db`:

```bash
docker-compose --profile local-db up -d --build
```

### Usar PostgreSQL externo (VPS)

Se o banco estiver fora do Docker, basta apontar as variáveis no `.env`:

```bash
POSTGRES_HOST=ip-ou-host-do-vps
POSTGRES_PORT=5432
POSTGRES_DB=nara_production
POSTGRES_USER=nara_user
POSTGRES_PASSWORD=senha-forte
```

Dicas operacionais:

- Garanta que o VPS permita conexões a partir do servidor onde o backend está rodando.
- Crie o banco e o usuário no PostgreSQL externo antes de subir a aplicação.
- Para não iniciar o PostgreSQL local do Docker, suba apenas backend e frontend:

```bash
docker-compose up -d --build backend frontend
```

Comandos úteis:

```bash
# Logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Migrations
docker-compose exec backend python manage.py migrate

# Shell no backend
docker-compose exec backend bash
```

## Desenvolvimento sem Docker

### Backend (Django)

```bash
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8001
```

### Frontend (React/Vite)

```bash
cd client
npm install
npm run dev
```

### Report Generator (FastAPI + Playwright)

```bash
cd report_generator
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium --with-deps   # no Windows: playwright install chromium
cp .env.example .env                      # opcional; ajuste PORT/timeouts/secret
```

Linux/macOS:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Windows:

```bash
python run.py
```

Por que no Windows? O Playwright precisa criar subprocessos via asyncio, o que só funciona com a policy `WindowsProactorEventLoopPolicy`. O uvicorn força a policy `Selector` no seu setup, então usamos o `run.py` como launcher — ele configura Proactor antes e instrui o uvicorn a pular seu próprio setup de loop (`loop="none"`). Dentro do container Docker o serviço roda em Linux e não passa por esse problema.

O `playwright install chromium --with-deps` baixa o Chromium e as bibliotecas nativas exigidas (flag `--with-deps` é apenas Linux). No Docker isso já vem pronto na imagem `mcr.microsoft.com/playwright/python`.

## Report Generator (PDF via Playwright)

Microserviço isolado responsável pela geração de PDFs dos relatórios. Recebe HTML completo, renderiza em um Chromium headless e devolve os bytes do PDF. Processa **um job por vez** a partir de uma fila interna (`asyncio.Queue`), evitando picos de memória — requisições acima do limite recebem `503`.

### Endpoints

- `POST /render` — body `{ "html": "...", "format": "A4", "print_background": true, "wait_until": "networkidle" }` devolve `application/pdf`. Se `RENDERER_SHARED_SECRET` estiver definido, exige o header `X-Renderer-Secret`.
- `GET /health` — status e ocupação da fila. Usado pelo healthcheck do compose.
- `GET /sample` — renderiza uma página HTML de exemplo. Útil para verificar visualmente que o serviço está funcionando sem precisar montar um payload.

### Smoke test

Com o serviço de pé (via Docker ou local):

```bash
curl -o sample.pdf http://localhost:8002/sample   # Docker (porta de dev)
curl -o sample.pdf http://localhost:8000/sample   # local (sem Docker)
```

Abra `sample.pdf` — se o conteúdo estiver legível, o Chromium está renderizando corretamente.

### Variáveis de ambiente

Lidas pelo próprio serviço (ver `report_generator/.env.example`):

| Variável | Default | Descrição |
|---|---|---|
| `PORT` | `8000` | Porta HTTP do FastAPI. |
| `MAX_QUEUE_SIZE` | `100` | Tamanho máximo da fila de jobs. Estourou, responde `503`. |
| `RENDER_TIMEOUT_SECONDS` | `60` | Timeout total (fila + render) de um job. Estourou, responde `504`. |
| `RENDERER_SHARED_SECRET` | vazio | Segredo exigido no header `X-Renderer-Secret`. Vazio desabilita a checagem. |
| `SENTRY_DSN` | vazio | DSN do projeto Sentry. Vazio desabilita integração. |
| `SENTRY_ENVIRONMENT` | `development` | Tag de ambiente (ex.: `production`, `staging`). |
| `SENTRY_RELEASE` | vazio | Identificador do release (SHA/tag). Opcional. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Fração de requisições amostradas para tracing. |
| `SENTRY_PROFILES_SAMPLE_RATE` | `0.0` | Fração de profiles coletados. `0.0` desabilita profiling. |

O HTML enviado ao `/render` pode conter nomes de crianças; `send_default_pii=False` e `before_send` redige o body antes de qualquer envio ao Sentry. Erros do worker são capturados com tags `component=render_worker` e `job_id=...`; timeouts chegam como `capture_message` com tag `component=render_timeout`.

O backend Django aponta para o serviço pelas variáveis abaixo (ver `server/.env.example`):

| Variável | Default | Descrição |
|---|---|---|
| `REPORT_GENERATOR_URL` | `http://report_generator:8000` | URL interna na rede do compose. |
| `REPORT_GENERATOR_SECRET` | vazio | Precisa bater com `RENDERER_SHARED_SECRET` do serviço. |
| `REPORT_GENERATOR_MAX_QUEUE_SIZE` | `100` | Encaminhado ao container como `MAX_QUEUE_SIZE`. |
| `REPORT_GENERATOR_TIMEOUT` | `60` | Encaminhado como `RENDER_TIMEOUT_SECONDS`. |

### Observações de produção

- A porta `8002` publicada em dev serve apenas para inspeção local. No `docker-compose.prod.yml` o serviço permanece acessível somente via rede interna do compose; remova o mapeamento de portas em deploys públicos.
- Em produção recomenda-se definir `REPORT_GENERATOR_SECRET` para que apenas o backend possa acionar renderizações.
- A imagem do Playwright carrega o Chromium inteiro (~1.5 GB). Dimensione memória do host considerando ~300–500 MB por página ativa.

### Deploy no Easypanel

O `report_generator` sobe como um serviço **separado** no Easypanel, um por instância (ex.: `demo-report-generator`, `unifan-report-generator`, `unica-report-generator`). O backend Django conversa com ele via rede interna do Easypanel — **não exponha domínio público**.

#### 1. Criar o serviço

- Tipo: **Aplicativo (App)**.
- Origem: mesmo repositório Nara, branch `master`.
- Build:
  - **Build Context:** `report_generator`
  - **Dockerfile Path:** `report_generator/Dockerfile`
- Porta do container: `8000`.
- **Domínio:** deixe em branco. O serviço é acessado apenas por outros serviços do mesmo projeto pela hostname interna (ex.: `demo-report-generator`).

#### 2. Variáveis de ambiente

No serviço do renderer:

| Variável | Valor recomendado |
|---|---|
| `PORT` | `8000` |
| `MAX_QUEUE_SIZE` | `100` (ajuste conforme carga) |
| `RENDER_TIMEOUT_SECONDS` | `60` |
| `RENDERER_SHARED_SECRET` | gere um valor aleatório forte — o mesmo precisa constar no backend |
| `LOG_LEVEL` | `INFO` em produção; use `DEBUG` se estiver investigando problemas de renderização |
| `SENTRY_DSN` | DSN do projeto (opcional — vazio desabilita) |
| `SENTRY_ENVIRONMENT` | `production` (ou `staging`) |
| `SENTRY_RELEASE` | SHA do commit ou tag da release |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` em produção; `1.0` apenas em staging/debug |

No serviço do **backend** correspondente, adicione/ajuste:

| Variável | Valor |
|---|---|
| `REPORT_GENERATOR_URL` | `http://<nome-do-servico-renderer>:8000` (ex.: `http://demo-report-generator:8000`) |
| `REPORT_GENERATOR_SECRET` | **mesmo valor** do `RENDERER_SHARED_SECRET` |
| `REPORT_GENERATOR_MAX_QUEUE_SIZE` | (opcional) mesmo valor do `MAX_QUEUE_SIZE` |
| `REPORT_GENERATOR_TIMEOUT` | (opcional) mesmo valor do `RENDER_TIMEOUT_SECONDS` |

> O Easypanel cria automaticamente DNS interno para cada serviço do mesmo projeto, então `http://<nome-do-servico>:8000` resolve sem configuração extra.

#### 3. Recursos

- **Memória:** reserve ao menos **1 GB** para o container. Cada página ativa consome ~300–500 MB de Chromium; com `MAX_QUEUE_SIZE=100` os jobs são sequenciais (um por vez), então 1–1,5 GB costuma ser suficiente. Suba se notar OOMKilled nos logs.
- **CPU:** 1 vCPU é adequado para a carga típica; Chromium usa CPU em picos durante o render.
- **Disco:** não precisa de volume persistente — o serviço é stateless. Qualquer arquivo temporário vive apenas na vida útil do container.

#### 4. Healthcheck

O `Dockerfile` já declara um healthcheck batendo em `/health`. No Easypanel não é necessário configurar manualmente, mas se quiser forçar:

- Path: `/health`
- Porta: `8000`
- Intervalo: 30s

#### 5. Validação após deploy

1. No painel do renderer, confirme nos logs a linha `Report generator pronto (queue=..., timeout=...s)`.
2. A partir do container do backend, rode um teste rápido para confirmar a conectividade interna:

   ```bash
   curl -f http://<nome-do-servico-renderer>:8000/health
   # Se RENDERER_SHARED_SECRET estiver definido, o /render exige o header;
   # /health continua aberto e é suficiente para provar que a rede está ok.
   ```

3. Faça o download de um relatório pelo frontend. No primeiro download o header de resposta deve mostrar `X-Pdf-Cached: false`; em downloads subsequentes, `true` (cache S3).

#### 6. Atualizações

- Commits em `master` que alterem `report_generator/` disparam o rebuild do serviço.
- Alterações apenas no backend Django **não** exigem rebuild do renderer (são serviços independentes).
- Se mudar `RENDERER_SHARED_SECRET`, atualize `REPORT_GENERATOR_SECRET` em todos os backends correspondentes antes de reiniciar — segredos desalinhados geram `401` silencioso no backend.

## Transcription Service (faster-whisper)

Microserviço opcional que substitui a OpenAI Whisper API por um Whisper local (`Whisper Large v3` via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)). Roda em container próprio e é selecionado via variável de ambiente — a função `transcrever_audio` do backend não muda.

### Selecionando o provedor

Defina `TRANSCRIPTION_PROVIDER` no `.env` (ou no ambiente do backend):

```bash
# OpenAI Whisper-1 (padrão, usa OPENAI_API_KEY)
TRANSCRIPTION_PROVIDER=openai

# faster-whisper local (usa o serviço `transcription`)
TRANSCRIPTION_PROVIDER=faster_whisper
TRANSCRIPTION_SERVICE_URL=http://transcription:8000
TRANSCRIPTION_SERVICE_TOKEN=<mesmo valor de INTERNAL_TOKEN no serviço>
```

Aliases aceitos para `faster_whisper`: `faster-whisper`, `fasterwhisper`, `fastwhisper`, `local`.

### Subindo o serviço em dev

```bash
docker compose up -d transcription
docker compose logs -f transcription    # acompanhe o carregamento do modelo
curl http://localhost:8003/readyz       # 200 quando o modelo terminou de carregar
```

Em dev o `MODEL_SIZE` padrão é `small` para não baixar 3GB a cada pessoa. Em produção (`docker-compose.prod.yml`) é `large-v3`.

### Documentação completa

Veja [`transcription_service/README.md`](transcription_service/README.md) para:

- Lista completa de variáveis de ambiente
- Endpoints (`/transcribe`, `/healthz`, `/readyz`)
- Deploy na EasyPanel (app próprio, volume `whisper_models`, healthcheck em `/readyz`)
- Execução em GPU
- Troubleshooting

### Observações de produção

- Primeiro deploy faz download de ~3GB do HuggingFace e leva ~5min para ficar pronto. Os próximos restarts levam 30-60s porque o modelo fica cacheado no volume `whisper_models`.
- Enquanto o modelo carrega, `/readyz` retorna 503 e o backend recebe `ConnectionError` — mantenha `TRANSCRIPTION_PROVIDER=openai` como fallback se precisar de 100% de uptime na primeira subida.
- Em CPU (`int8`), a transcrição roda a ~1× realtime (1min de áudio ≈ 1min de processamento). Ajuste `IA_AUDIO_TIMEOUT_SECONDS` com folga.
- `TRANSCRIPTION_SERVICE_TOKEN` no backend precisa bater com `INTERNAL_TOKEN` no serviço (evita chamadas externas).

## Scheduler (cache da coordenação)

Stack centralizado (Celery beat + worker + Redis) que, diariamente às 02:00 (timezone configurável), chama o endpoint interno de cada escola para regenerar o snapshot D-1 consumido pelo painel da coordenação (`CoordenacaoCache`). Sem o cache, o carregamento da página disparava uma consulta de 30 dias de `registros_observacao` que chegava a ~850 KB por instituição.

### Arquitetura

```
  ┌──────────┐  cron  ┌──────────┐  tasks  ┌──────────┐  HTTP   ┌──────────────┐
  │  beat    │───────▶│  redis   │────────▶│  worker  │────────▶│ backend de N │
  └──────────┘        └──────────┘         └──────────┘         │    escolas   │
                                                                 └──────────────┘
```

- O scheduler **não** acessa os bancos de dados das escolas. Ele apenas faz `POST /api/internal/cache/coordenacao/` em cada backend, autenticado com `X-Internal-Token`.
- Cada backend calcula os agregados (`bncc_usage`, crianças com registro nos últimos 15 dias, professor mais recente por criança) e persiste em `coordenacao_cache` no seu próprio DB, mantendo no máximo 30 dias de snapshots por instituição.
- O frontend consome o snapshot via `GET /api/coordenacao/cache/` (sessão do coordenador) e mostra um banner com a data da última atualização.

### Endpoints do backend

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| `POST` | `/api/internal/cache/coordenacao/` | header `X-Internal-Token` | Recomputa o cache para `{instituicao_id, data_referencia?, janela_dias?}`. |
| `GET`  | `/api/coordenacao/cache/` | sessão autenticada | Retorna `{data_referencia, gerado_em, payload}` do snapshot mais recente. |

### Variáveis de ambiente (backend)

| Variável | Default | Descrição |
|---|---|---|
| `NARA_INTERNAL_TOKEN` | vazio | Token compartilhado com o scheduler. Vazio desabilita o endpoint interno. |
| `NARA_INSTITUICAO_ID` | vazio | UUID da instituição servida por este backend. Fonte de verdade — o backend não infere de `Usuario.instituicao` quando esta variável está setada. |

### Configuração do scheduler

O registry de escolas é avaliado nesta ordem:

1. `ESCOLAS_JSON` — JSON em uma única env var. **Recomendado em Easypanel/Kubernetes**, sobrevive a redeploys.
2. `ESCOLAS_YAML` — mesmo conteúdo em YAML (para UIs que aceitam multilinha).
3. Arquivo `scheduler/escolas.yaml` apontado por `ESCOLAS_REGISTRY_PATH` — útil em dev local.

Cada entrada precisa de `id`, `backend_url`, `instituicao_id` e `internal_token`. O token aceita o prefixo `env:NOME_DA_VAR` para ser resolvido em runtime a partir de outra env var (evita colocar segredos no JSON/YAML).

Exemplo de `ESCOLAS_JSON` (uma linha só na UI do Easypanel):

```json
[{"id":"escola-abc","nome":"Escola ABC","backend_url":"https://abc.nara.example","instituicao_id":"<uuid>","internal_token":"env:NARA_TOKEN_ABC"}]
```

Em dev local:

```bash
cd scheduler
cp .env.example .env
cp escolas.example.yaml escolas.yaml
docker compose up -d --build
```

### Variáveis de ambiente (scheduler)

| Variável | Default | Descrição |
|---|---|---|
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Redis usado como broker. Default aponta para o serviço `redis` do `scheduler/docker-compose.yml`. Em Easypanel/K8s aponte para o Redis gerenciado (ex.: `redis://<servico>:6379/0` ou `redis://:<senha>@host:6379/0`). |
| `CELERY_RESULT_BACKEND` | vazio (usa broker) | Opcional; separa o backend de resultado do broker. |
| `CELERY_TIMEZONE` | `America/Sao_Paulo` | Timezone do crontab do beat. |
| `CACHE_REFRESH_HOUR` | `2` | Hora local do refresh diário. |
| `CACHE_REFRESH_MINUTE` | `0` | Minuto do refresh diário. |
| `ESCOLAS_JSON` | vazio | Registry em JSON (fonte preferida). |
| `ESCOLAS_YAML` | vazio | Registry em YAML (alternativa). |
| `ESCOLAS_REGISTRY_PATH` | `./escolas.yaml` | Arquivo YAML usado se nem JSON nem YAML em env var estiverem setados. |
| `REFRESH_REQUEST_TIMEOUT` | `60` | Timeout (s) da requisição HTTP ao backend de cada escola. |

### Forçar um refresh manual

```bash
# Via Celery (dentro do container worker)
docker compose exec worker \
  celery -A celery_app call tasks.refresh_coordenacao_cache --args='["escola-demo"]'

# Ou via HTTP direto (útil para o primeiro seed antes do beat)
curl -X POST https://<backend-da-escola>/api/internal/cache/coordenacao/ \
  -H "X-Internal-Token: <token>" \
  -H "Content-Type: application/json" \
  -d '{"instituicao_id":"<uuid>"}'
```

### Observações de produção

- O endpoint `/api/internal/*` só responde quando o `X-Internal-Token` bate com `NARA_INTERNAL_TOKEN`. Recomenda-se também restringir o prefixo por IP no proxy reverso.
- O refresh é idempotente: rodar duas vezes no mesmo dia apenas sobrescreve o row de `(instituicao_id, data_referencia)`.
- Falhas em uma escola não impactam as outras — cada subtask tem retry exponencial independente.
- Se o cache ainda não existir, o frontend faz fallback silencioso (o painel carrega com os agregados zerados até o próximo tick do beat).

## Gravador de áudio (dispositivo físico do relato individual)

Microfone dedicado (ESP32, sem tela nem teclado) que a professora usa para gravar
o relato individual. O aparelho é **pareado a uma professora e às turmas dela
pela plataforma** e depois envia **apenas o áudio**: professora, turma e
instituição são resolvidas no servidor a partir do vínculo do dispositivo —
nada de identidade no payload.

**Professora com mais de uma turma:** o gravador é vinculado a todas as turmas
que ela atende (escopo de permissão) e ela **troca de turma falando no próprio
microfone** — "estou na turma Nível 5" —, sem tocar em nada no aparelho nem na
plataforma. O servidor reconhece o nome da turma na transcrição, marca-a como
turma ativa e é nela que os alunos citados serão procurados; a turma ativa
permanece nas gravações seguintes até ela anunciar outra.

### Visão geral do fluxo

```
1. PAREAMENTO (uma vez, por aparelho)
   Admin/professora na plataforma → gera código de 6 caracteres (validade 10 min, uso único)
   Aparelho (portal cativo no WiFi dele) recebe: rede da escola + código
   Aparelho conecta na rede e chama POST /api/dispositivos/parear/ → recebe TOKEN permanente

2. ENVIO (cada gravação)
   POST /api/dispositivos/audio/  (Authorization: Bearer <token>)
   multipart: arquivo.wav + upload_id + sha256 (opcional) + duracao_seg (opcional)
   → 201 confirmando o recebimento (LED verde)

3. PROCESSAMENTO (assíncrono, no servidor — worker processar_audios_dispositivo)
   Transcrição → turma anunciada na fala (e conferida contra as turmas do
   aparelho) → extração dos nomes → pareamento com as crianças da turma →
   relato individual

4. FEEDBACK (o aparelho não tem tela)
   GET /api/dispositivos/audio/<upload_id>/ → feedback.sinal = ok | atencao | erro
   → LED verde / amarelo / vermelho
```

> **Kit de testes prontos:** `docs/gravador/` tem scripts que exercitam todos os
> endpoints abaixo sem instalar nenhuma biblioteca (Python stdlib, `curl` e um
> sketch de ESP32) — é o material para enviar à equipe do firmware. Veja
> [`docs/gravador/README.md`](docs/gravador/README.md).

### Como cadastrar um dispositivo para testes

1. Entre na plataforma como **admin** → menu **Cadastros → Dispositivos**.
2. Clique em **"Gerar código de pareamento"**, escolha a professora e marque
   **todas as turmas** que ela atende.
3. O código aparece na tela (ex.: `RHFF89`), válido por 10 minutos e de uso único.
4. Use o código na chamada de pareamento abaixo — o `device_id` é escolhido pelo
   firmware (MAC ou serial do chip). O dispositivo passa a aparecer na lista.

### 1. Pareamento — `POST /api/dispositivos/parear/`

Único endpoint **sem token** (o aparelho ainda não tem um). Protegido por
rate-limit de 5 req/min por IP.

```bash
curl -X POST https://SEU_HOST/api/dispositivos/parear/ \
  -H "Content-Type: application/json" \
  -d '{
        "codigo": "RHFF89",
        "device_id": "AA:BB:CC:11:22:33",
        "nome": "Gravador Sala 5C"
      }'
```

Resposta `201`:

```json
{
  "success": true,
  "token": "0d1f...-uuid-do-dispositivo.SEGREDO_LONGO",
  "dispositivo": {
    "id": "0d1f...",
    "device_id": "AA:BB:CC:11:22:33",
    "nome": "Gravador Sala 5C",
    "professora_nome": "Myrna",
    "turmas": [
      { "id": "…", "nome": "Nível 4 A" },
      { "id": "…", "nome": "Nível 5 C" }
    ],
    "turma_ativa_nome": "",
    "ativo": true
  }
}
```

> **O `token` só aparece nesta resposta** — o firmware precisa gravá-lo em
> memória não volátil (NVS/flash). Perdeu o token = novo pareamento.

Erros: `400 codigo_invalido` (inexistente, expirado ou já usado),
`400 device_id_ausente`, `429` (rate-limit).

Repetir o pareamento com o mesmo `device_id` **regenera** o token e atualiza o
vínculo — é o caminho para trocar o aparelho de professora ou recuperá-lo.

### 2. Envio do áudio — `POST /api/dispositivos/audio/`

```bash
curl -X POST https://SEU_HOST/api/dispositivos/audio/ \
  -H "Authorization: Bearer <TOKEN>" \
  -F "arquivo=@gravacao.wav;type=audio/wav" \
  -F "upload_id=3f2b9c1e-...-uuid-gerado-pelo-firmware" \
  -F "sha256=<sha256-hex-do-arquivo>" \
  -F "duracao_seg=95"
```

Campos:

| Campo | Obrigatório | Observação |
|---|---|---|
| `arquivo` | sim | WAV com cabeçalho RIFF/WAVE. Recomendado: **PCM 16 bits, mono, 16 kHz** (ideal para a transcrição e ~10× menor que 44.1 kHz estéreo). Limite: **25 MB** (≈13 min nesse formato) |
| `upload_id` | sim | UUID **gerado pelo firmware** e reutilizado em todos os retries do mesmo áudio |
| `sha256` | não | Hex do arquivo; se enviado, o servidor confere e rejeita divergência |
| `duracao_seg` | não | Inteiro; se ausente, o servidor estima pelo cabeçalho do WAV |

Resposta `201` (primeiro envio) ou `200` (retry do mesmo `upload_id`):

```json
{
  "recebido": true,
  "duplicado": false,
  "audio_id": "…",
  "upload_id": "3f2b9c1e-…",
  "sha256": "…",
  "status": "recebido",
  "data_recebimento": "2026-08-03T14:20:31.512Z"
}
```

**Regra de retry:** em timeout ou erro `5xx`, reenviar **com o mesmo
`upload_id`** — o servidor devolve `200` com `"duplicado": true` e não duplica o
relato. Nos demais erros, não adianta repetir sem corrigir a causa:

| Status | `codigo` | Significado |
|---|---|---|
| `401` | `token_invalido` | Token errado ou dispositivo revogado → reparear |
| `400` | `wav_invalido` | Sem cabeçalho RIFF/WAVE ou arquivo curto demais |
| `400` | `hash_divergente` | O `sha256` informado não bate com o arquivo recebido |
| `400` | `upload_id_invalido` | `upload_id` não é um UUID |
| `400` | `arquivo_ausente` | Faltou o campo `arquivo` |
| `413` | `arquivo_grande` | Acima de 25 MB |
| `429` | — | Rate-limit de upload (10/min) |

### 3. Feedback da gravação — `GET /api/dispositivos/audio/<upload_id>/`

O `201` do upload significa **"o arquivo chegou"**, não "o relato foi
registrado": turma e criança só são conhecidas depois da transcrição. Como o
aparelho não tem tela, é este endpoint que fecha o ciclo — o firmware consulta a
cada ~3 s até `feedback.sinal` sair de `aguardando`.

```bash
curl https://SEU_HOST/api/dispositivos/audio/<upload_id>/ -H "Authorization: Bearer <TOKEN>"
```

```json
{
  "status": "processado",
  "feedback": { "sinal": "ok", "mensagem": "Nível 3A · 1 criança registrada" },
  "turma": { "id": "…", "nome": "Nível 3A" },
  "turma_resultado": "anunciada",
  "turma_anunciada": "Nível 3A",
  "alunos_identificados": ["Alice Marreiro"],
  "nomes_nao_identificados": [],
  "total_observacoes": 1,
  "erro_codigo": ""
}
```

`sinal` é o único campo que o firmware precisa interpretar:

| `sinal` | Quando | Hardware |
|---|---|---|
| `aguardando` | Ainda na fila / processando | LED azul, consultar de novo |
| `ok` | Turma resolvida e criança(s) registrada(s) | LED verde |
| `atencao` | Entrou, mas incompleto | LED amarelo |
| `erro` | Falha, nada registrado | LED vermelho |

Os casos de `atencao` (nada é gravado — registrar na sala errada é pior que não
registrar):

| `turma_resultado` / `erro_codigo` | Situação |
|---|---|
| `nao_autorizada` | A turma anunciada existe na escola, mas não está liberada para este gravador |
| `indefinida` | O gravador atende várias turmas e nenhuma foi anunciada na fala |
| `nenhum_aluno` | Turma resolvida, mas nenhum nome bateu com as crianças dela |

### 4. Sanity check — `GET /api/dispositivos/status/`

Útil no boot do firmware para saber se o token ainda vale e a quem o aparelho
está vinculado. Traz também o último áudio, para dar retorno mesmo se o
`upload_id` tiver se perdido num reboot:

```bash
curl https://SEU_HOST/api/dispositivos/status/ -H "Authorization: Bearer <TOKEN>"
```

```json
{
  "ok": true,
  "dispositivo": {
    "professora_nome": "Myrna",
    "turmas": [{ "id": "…", "nome": "Nível 4 A" }],
    "turma_ativa_nome": "Nível 4 A",
    "ativo": true
  },
  "ultimo_audio": { "upload_id": "…", "status": "processado", "feedback": { "sinal": "ok" } }
}
```

### Processamento no servidor (worker)

Os áudios entram como `recebido` e são convertidos em relato individual pelo
worker — **sem ele nada é transcrito nem registrado**:

```bash
# uma passada (cron)
conda run -n nara_server python server/manage.py processar_audios_dispositivo

# daemon, para dev (ou start_worker_gravador.bat no Windows)
conda run -n nara_server python server/manage.py processar_audios_dispositivo --loop

# reprocessar depois de corrigir o vínculo de turma
conda run -n nara_server python server/manage.py processar_audios_dispositivo --refazer-falhas
```

O worker transcreve, resolve a turma pela fala, busca as crianças dessa turma no
banco, pareia os nomes citados e grava uma `ObservacaoTranscricao` por criança
(`api/services/dispositivo_processamento.py`).

### Notas de implementação para o firmware

- **A data é carimbada pelo servidor** — não é preciso RTC nem sincronizar relógio.
- **Só o áudio viaja**: não envie professora, turma ou escola; esses campos são
  ignorados e a identidade vem do vínculo do dispositivo.
- **Trocar a professora/turmas do aparelho** é feito na plataforma (Cadastros →
  Dispositivos → editar) e **não exige mexer no dispositivo**: o token continua
  valendo e os próximos áudios já saem com o vínculo novo.
- **Troca de sala no dia a dia é por voz, na mesma gravação do relato** — a
  professora fala "estou na turma Nível 3A. Alice Marreiro brincou muito hoje".
  Nada muda no protocolo: o firmware continua enviando só o WAV, **não
  transcreve nada e não consulta nada antes de gravar**; o servidor identifica a
  turma na transcrição e confere se ela é permitida ao aparelho. Não existe (nem
  é necessário) um endpoint de "trocar de sala".
- **O upload confirma o arquivo, não o relato** — para saber se a turma foi
  reconhecida e a criança registrada, consulte o feedback (seção 3).
- **Revogação** na plataforma invalida o token na hora (respostas `401`).
- Endpoints da plataforma (exigem sessão de usuário, não servem ao firmware):
  `POST /api/dispositivos/codigo/`, `GET /api/dispositivos/`,
  `PATCH /api/dispositivos/<id>/`, `DELETE /api/dispositivos/<id>/revogar/`,
  `POST /api/dispositivos/<id>/reativar/`.

## Testes

```bash
# Backend
cd server
python manage.py test

# Frontend (verificação de build)
cd client
npm run build
```

## Produção com Docker + Nginx

```bash
cp .env.prod.example .env.prod
# Edite .env.prod com valores reais

docker compose -f docker-compose.prod.yml up -d --build
```

Notas:

- `NARA_DOMAIN` e `CERTBOT_EMAIL` são obrigatórios para emissão automática de certificado.
- O Nginx publica 80/443; garanta que as portas estão livres no servidor.

## Observações

- Uploads locais são mantidos em `server/uploads/` apenas para desenvolvimento; em produção o armazenamento é feito via S3.
- Não versionar arquivos `.env`, credenciais ou dados sensíveis.
