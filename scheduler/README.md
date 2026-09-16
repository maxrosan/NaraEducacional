# Nara Scheduler

Scheduler central (Celery beat + worker + Redis) que, diariamente às 02:00,
aciona cada backend de escola para regenerar o snapshot D-1 do painel da
coordenação (`CoordenacaoCache`). Isso evita a consulta pesada de 30 dias de
`registros_observacao` no carregamento da página.

## Arquitetura

```
  ┌──────────┐  cron  ┌──────────┐  tasks  ┌──────────┐  HTTP   ┌──────────────┐
  │  beat    │───────▶│  redis   │────────▶│  worker  │────────▶│ backend de N │
  └──────────┘        └──────────┘         └──────────┘         │    escolas   │
                                                                 └──────────────┘
```

- O scheduler **não** acessa bancos das escolas. Ele apenas chama
  `POST /api/internal/cache/coordenacao/` em cada backend, autenticando com
  header `X-Internal-Token`.
- Cada backend conhece seu próprio `instituicao_id` via `NARA_INSTITUICAO_ID`
  no `.env` — é a fonte de verdade. Por isso o scheduler não precisa saber
  o UUID da instituição (campo opcional em `escolas.yaml`).
- Cada backend de escola calcula o agregado e persiste em
  `coordenacao_cache` no seu próprio DB.
- O frontend da escola lê o cache por `GET /api/coordenacao/cache/`.

> ⚠️ **O beat é um processo obrigatório e separado do worker.** O cron diário
> só dispara se houver um processo `celery beat` rodando — o worker sozinho
> **não** agenda nada. Por isso há dois Dockerfiles:
>
> - `Dockerfile` → `CMD` roda o **worker** (`celery -A celery_app worker`).
> - `Dockerfile.beat` → `CMD` roda o **beat** (`celery -A celery_app beat`).
>
> Você precisa subir **os dois** como serviços distintos (mesma config/env,
> mesmo Redis). Com `docker-compose` isso é feito sobrescrevendo o `command`
> (ver `docker-compose.yml`); no **Easypanel**, que não permite sobrescrever
> o comando de start por serviço, crie um serviço a partir de cada Dockerfile
> (ver seção "Deploy no Easypanel" abaixo).
>
> Se só o worker estiver no ar, o refresh das 02:00 nunca roda e o cache da
> coordenação fica permanentemente desatualizado (sem erro visível).

## Configuração

O registry de escolas pode vir de **três fontes** (avaliadas nesta ordem):

1. `ESCOLAS_JSON` — array JSON em uma única variável de ambiente. **Recomendado
   para Easypanel / Kubernetes**, porque sobrevive a redeploys.
2. `ESCOLAS_YAML` — mesmo conteúdo em YAML (se a UI aceitar multilinha).
3. Arquivo `escolas.yaml` (via `ESCOLAS_REGISTRY_PATH`). Útil em dev local.

### Opção recomendada (Easypanel): `ESCOLAS_JSON`

Cole em uma única variável de ambiente do serviço:

```json
[
  {
    "id": "escola-abc",
    "nome": "Escola ABC",
    "backend_url": "https://abc.nara.example",
    "internal_token": "env:NARA_TOKEN_ABC"
  },
  {
    "id": "escola-xyz",
    "nome": "Escola XYZ",
    "backend_url": "https://xyz.nara.example",
    "internal_token": "env:NARA_TOKEN_XYZ"
  }
]
```

Declare os tokens como env vars separadas (`NARA_TOKEN_ABC`, `NARA_TOKEN_XYZ`
etc.) para não colocar segredos no JSON — o prefixo `env:` é resolvido em
runtime. Se preferir, também é válido passar o token literal no próprio JSON.

No backend de cada escola, defina:

- `NARA_INTERNAL_TOKEN` com o mesmo valor do token enviado pelo scheduler.
- `NARA_INSTITUICAO_ID` com o UUID da instituição servida por aquele backend.

`instituicao_id` é opcional no registry — só preencha em backends
multi-tenant que servem mais de uma instituição.

### Opção local (dev): arquivo YAML

```bash
cp .env.example .env
cp escolas.example.yaml escolas.yaml
docker compose up -d --build
```

`escolas.yaml` está no `.gitignore`. O arquivo só é lido quando nem
`ESCOLAS_JSON` nem `ESCOLAS_YAML` estiverem definidos.

## Broker Redis

O Celery precisa de um broker (e result backend). A URL vem da variável
`CELERY_BROKER_URL`.

- **Usando o `docker-compose.yml` deste diretório**: o serviço `redis` sobe
  junto e o default `redis://redis:6379/0` já resolve. Nada a fazer.
- **Easypanel / Kubernetes / Redis gerenciado**: crie o Redis como serviço
  no mesmo projeto e aponte `CELERY_BROKER_URL` para ele, por exemplo:

  ```
  CELERY_BROKER_URL=redis://<nome-do-servico-redis>:6379/0
  # com senha:
  CELERY_BROKER_URL=redis://:<senha>@<host>:6379/0
  ```

  Nesse caso, os serviços `worker` e `beat` podem ser deployados sem o
  `redis` do compose (ou em stacks separados). **Crie os dois serviços** —
  worker a partir do `Dockerfile` e beat a partir do `Dockerfile.beat` (ver
  "Deploy no Easypanel"); não basta subir só o worker, senão o beat fica de
  fora. `CELERY_RESULT_BACKEND` é opcional — se não definir, usa o mesmo
  valor do broker.

## Deploy no Easypanel

O Easypanel não permite sobrescrever o comando de start por serviço, então
cada papel (worker e beat) tem **seu próprio Dockerfile** apontando para o
mesmo código. Crie **três serviços** no mesmo projeto:

1. **Redis** — serviço de banco/Redis gerenciado do Easypanel (ou imagem
   `redis:7-alpine`). Anote o host interno (ex.: `nara-scheduler_redis`).
2. **worker** — App do tipo Dockerfile, apontando para `scheduler/Dockerfile`
   (o `CMD` já roda o worker). Defina as env vars (ver abaixo).
3. **beat** — App do tipo Dockerfile, apontando para `scheduler/Dockerfile.beat`
   (o `CMD` já roda o beat). **Mesmas env vars do worker.**

Ambos (worker e beat) precisam das mesmas variáveis:

```
CELERY_BROKER_URL=redis://<host-do-redis>:6379/0
CELERY_TIMEZONE=America/Sao_Paulo
ESCOLAS_JSON=[...]            # registry das escolas (ver "Configuração")
NARA_TOKEN_<ESCOLA>=...       # tokens referenciados via env: no JSON
CACHE_REFRESH_HOUR=2          # opcional (default 2) — só o beat usa, mas
CACHE_REFRESH_MINUTE=0        # opcional — não custa definir nos dois
```

Os dois apontam para o **mesmo Redis**. O beat publica a tarefa na fila e o
worker a executa, então ambos precisam do mesmo `CELERY_BROKER_URL`. Não
exponha portas — é tudo tráfego interno do projeto.

> Mantenha **apenas uma réplica do beat**. Duas instâncias de beat
> agendariam o refresh em duplicado. O worker pode escalar à vontade.

## Rodando localmente (dev)

O objetivo é ligar o scheduler ao backend Django que você já usa em dev
(subido via `docker-compose up` no diretório raiz do Nara). O scheduler
roda em um compose separado, então o worker precisa saber onde está o
backend do host.

### 1. Preparar o backend

Pegue o UUID da instituição da sua conta de coordenador:

```bash
cd server
python manage.py shell -c "from api.models import Usuario; u=Usuario.objects.filter(perfil='coordenador').first(); print(u.instituicao_id)"
```

No `.env` da raiz, defina o token interno e o UUID:

```bash
# na raiz do repo
openssl rand -hex 32  # copie a saída do token
cat <<EOF >> .env
NARA_INTERNAL_TOKEN=<token-acima>
NARA_INSTITUICAO_ID=<uuid-da-instituicao>
EOF
docker compose up -d --build backend   # ou: cd server && python manage.py runserver
```

Confira que a rota interna está protegida:

```bash
curl -i -X POST http://localhost:8001/api/internal/cache/coordenacao/ \
  -H 'Content-Type: application/json' -d '{}'
# => HTTP/1.1 401 Unauthorized
```

### 2. Preparar o scheduler

```bash
cd scheduler
cp .env.example .env
cp escolas.example.yaml escolas.yaml
```

Edite `escolas.yaml` apontando para o backend do host. O worker roda em
container, então `localhost` nele seria o próprio container; use
`host.docker.internal` (o compose do scheduler já declara o
`extra_hosts` necessário no Linux):

```yaml
escolas:
  - id: dev-local
    nome: Dev Local
    backend_url: http://host.docker.internal:8001
    internal_token: env:NARA_TOKEN_DEV
    # instituicao_id: <uuid>   # só se o backend não tiver NARA_INSTITUICAO_ID
```

Em `scheduler/.env`, defina o token com o mesmo valor do backend:

```bash
echo "NARA_TOKEN_DEV=<mesmo-valor-do-NARA_INTERNAL_TOKEN>" >> .env
```

### 3. Subir worker + beat + redis

```bash
docker compose up -d --build
docker compose logs -f worker     # acompanhe
```

### 4. Disparar um refresh sem esperar as 02:00

```bash
docker compose exec worker \
  celery -A celery_app call tasks.refresh_coordenacao_cache --args='["dev-local"]'
```

Você deve ver nos logs do worker algo como
`Cache atualizado escola=dev-local data_ref=YYYY-MM-DD`.

### 5. Conferir o cache no backend

```bash
# listar direto no DB do backend
docker compose -f ../docker-compose.yml exec backend python manage.py shell -c "
from api.models import CoordenacaoCache
for c in CoordenacaoCache.objects.all()[:5]:
    print(c.instituicao_id, c.data_referencia, c.gerado_em)
"

# ou, logado como coordenador no frontend, acesse o painel — o banner
# 'Indicadores atualizados em ...' deve mostrar a hora do refresh.
```

### Alternativa: rodar o worker fora do Docker

Se preferir iteração mais rápida (sem rebuild), rode o worker direto em
um venv apontando pra um Redis local. O `scheduler/.env` é carregado
automaticamente pelo `celery_app.py` (via `python-dotenv`), então basta
preencher o arquivo:

```bash
cd scheduler
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Suba só o redis do compose (ou use um já existente na máquina)
docker compose up -d redis
```

Em `scheduler/.env`:

```
CELERY_BROKER_URL=redis://localhost:6379/0
NARA_TOKEN_DEV=<token>
```

E em `escolas.yaml` troque `host.docker.internal` por `localhost`
(o worker agora roda no host).

```bash
celery -A celery_app worker --loglevel=INFO
# em outro terminal:
celery -A celery_app beat --loglevel=INFO
```

Variáveis exportadas no shell ainda têm prioridade — útil para
sobrescrever pontualmente sem editar o `.env`.

#### Windows: use `--pool=solo` ou `--pool=threads`

O pool padrão do Celery (`prefork`) depende de `fork()` do Unix e quebra
no Windows com erros como
`ValueError: not enough values to unpack (expected 3, got 0)` em
`fast_trace_task`. Para rodar em Windows nativo (fora do WSL/Docker)
escolha um pool compatível:

```powershell
celery -A celery_app worker --loglevel=INFO --pool=solo
# ou, se quiser concorrência:
celery -A celery_app worker --loglevel=INFO --pool=threads --concurrency=4
```

`solo` é single-thread síncrono — suficiente pra desenvolvimento. Em
produção use Linux/Docker, onde o `prefork` continua sendo o melhor.

## Forçar um refresh manual

```bash
docker compose exec worker \
  celery -A celery_app call tasks.refresh_coordenacao_cache --args='["escola-demo"]'
```

Ou chame o endpoint diretamente:

```bash
curl -X POST https://<backend-da-escola>/api/internal/cache/coordenacao/ \
  -H "X-Internal-Token: <token>" \
  -H "Content-Type: application/json" \
  -d '{"instituicao_id":"<uuid>"}'
```

## Observações

- Retenção: cada backend mantém no máximo 30 dias de snapshots por
  instituição (limpeza automática).
- Segurança: a rota `/api/internal/*` só responde com o token correto;
  recomenda-se também restringir por IP no proxy reverso do backend.
