# Plano de migração: single-tenant → multi-tenant

> Documento de análise e planejamento. Nenhuma mudança de código foi feita.
> Cada fase traz o **prompt sugerido para o Claude** executá-la.

---

## 1. Diagnóstico do estado atual

### 1.1 Arquitetura de implantação: single-tenant por deploy

Hoje **cada escola roda sua própria instância** (backend + banco + env próprios).
As evidências no código:

- `server/api/services/coordenacao_cache.py` (linhas 11–12, 70–72) documenta
  explicitamente: *"o banco é dedicado a uma escola, então a agregação **não
  filtra por `instituicao_id`**"* — e de fato agrega `Crianca.objects` inteiro.
- `NARA_INSTITUICAO_ID` vem do `.env` (`settings`), usado como *chave do
  snapshot* do cache e default em `views/coordenacao_cache.py` — um identificador
  de tenant **por implantação**, não por request.
- `AWS_S3_BUCKET_NAME` é um env único por deploy (`api/storage.py`).

Ou seja: o `instituicao_id` presente em vários modelos é herança de um desenho
lógico multi-tenant, mas **o isolamento real hoje é a separação física dos
bancos**. Consolidar tudo numa instância exige transformar esse isolamento
físico em isolamento lógico *enforçado*.

### 1.2 Inventário de modelos (o detalhe que não pode passar)

**Com `instituicao_id` (ou FK):** `Usuario`, `Turma`, `Crianca`, `Relatorio`
(+ unique `id_crianca+periodo+instituicao_id`), `CampoExperienciaCustomizado`
(unique `instituicao_id+nome`), `PerguntaEspecialista`, `ProducaoCrianca`,
`Projeto`, `CalendarioBimestre`, `PeriodoAvaliativo`, `MensagemCoordenacao`,
`CoordenacaoCache` (unique `instituicao_id+data_referencia`), `PromptTemplate`
(via `cliente_id`), `MetaAEE`/`SessaoAEE` (FK real).

**SEM instituição (dependem do banco dedicado para isolamento):**

| Modelo | Como se ancora hoje | Risco em banco compartilhado |
|---|---|---|
| `RegistroEscrita` | `nome_aluno` + `turma_id` (texto) | casamento por nome colide entre escolas |
| `RegistroDesenho` | idem | idem |
| `RegistroLeitura` | FKs `crianca`/`turma`/`professor` | isolamento indireto (ok se filtrado) |
| `RegistroObservacao` | FKs criança/professor | indireto |
| `PlanejamentoSemanal/Diario/Habilidade` | `turma`/`professora` | indireto |
| `ObservacaoTranscricao` | professor | indireto |
| `ProducaoFoto`/`ProducaoFotoCrianca` | professora/criança | indireto |
| `SerieConfig`, `ConfiguracaoRegistro` | nada | vira config GLOBAL compartilhada |
| `HabilidadeBNCC`, `PerguntaBNCC` | nada (catálogo) | ok como global — decidir e documentar |
| `OpenAIUsage` | usuario | precisa de instituição p/ billing por tenant |

### 1.3 Pontos do código que assumem single-tenant

1. **Agregações da coordenação sem filtro** (`services/coordenacao_cache.py`:
   `Crianca.objects.count()`, `ProducaoCrianca.objects.all()`, `_mapas_alfabetizacao`
   etc.) — num banco compartilhado misturaria escolas no Pulso/indicadores.
2. **Views com `.objects.all()`** — ex.: `views_legacy.listar_registros_escrita`
   (linha ~592). Varredura completa necessária (`views_legacy.py`, `views_rest.py`,
   `views/`).
3. **`servir_arquivo` sem autenticação** (`views/analise_producao.py`,
   `@api_view(['GET'])` puro): qualquer pessoa com o `arquivo_hash` baixa a
   imagem — o hash funciona como *capability* sem verificação de tenant.
4. **Casamento por `nome_aluno`** (escrita/desenho ↔ criança; relatório usa
   `nome_aluno__icontains`): entre escolas, homônimos vazariam produções de uma
   escola para o relatório de outra. **Este é o risco mais grave.**
5. **`DEFAULT_PERMISSION_CLASSES = AllowAny`** (known issue do CLAUDE.md):
   proteção por view, fácil de esquecer em endpoint novo.
6. **Unique constraints globais** que passam a ser inter-tenant: `Usuario.email`
   (decidir: e-mail globalmente único é aceitável — recomendo manter),
   `RegistroEscrita.arquivo_hash` (ok, contém aleatoriedade).
7. **Frontend filtra por `instituicao_id` do `user_metadata`** em várias
   queries do `apiClient` — filtro client-side **não é segurança**; o servidor
   precisa impor.
8. **Jobs/infra por tenant**: `refresh_coordenacao_cache` (management command +
   scheduler Celery) roda para *uma* instituição; `report_generator` e NaraNN
   são stateless (ok); S3 sem prefixo por tenant.

---

## 2. Decisão de arquitetura

| Opção | Descrição | Prós | Contras |
|---|---|---|---|
| **A. Shared schema (row-level)** ✅ | Um banco, `instituicao_id` em tudo, filtro imposto no ORM | Metade do caminho já existe; operação simples; migrações únicas; custo baixo | Isolamento depende de disciplina de código (mitigável com manager + testes) |
| B. Schema-per-tenant (`django-tenants`) | Um schema Postgres por escola, roteado por subdomínio | Isolamento forte no banco | Reescrita de infra grande; migrações N× ; conflita com o código atual que já mistura `instituicao_id`; subdomínio por escola exige DNS/certificados |
| C. DB-per-tenant automatizado | Formalizar o status quo com provisioning | Zero mudança de código | Não é multi-tenant de verdade: custo linear, N deploys, sem visão agregada |

**Recomendação: Opção A.** O modelo de dados já aponta para ela (metade dos
modelos tem `instituicao_id`, prompts já usam `cliente_id`), o time é pequeno e
a fraqueza (esquecer um filtro) é endereçável com um **manager de tenant
obrigatório + suíte de testes de isolamento** (fase 0). A opção B só se
justificaria com exigência contratual de isolamento físico.

---

## 3. Fases do plano

> Convenções em todas as fases (do CLAUDE.md): testes em `tests/`, CHANGELOG
> em toda mudança, ambiente conda `nara_server`, nada de código novo em
> `views_legacy.py` (reimplementar em `views/<modulo>.py` com override no
> `views/__init__.py`).

### Fase 0 — Rede de segurança (antes de mexer em qualquer coisa)

**Objetivo:** conseguir *provar* isolamento antes de precisar dele.

- Fixture de teste com **duas instituições completas** (turmas, crianças,
  professores, registros de todos os tipos) em `tests/backend/`.
- Suíte `test_isolamento_tenant.py`: para cada endpoint de leitura, logar como
  usuário da escola A e assertar que **nada** da escola B aparece. Ela nasce
  majoritariamente **vermelha** — é o mapa do trabalho das fases 1–3.
- Inventário automatizado: teste que falha se um modelo novo não declarar
  ancoragem de tenant (lista de exceções explícita para catálogos globais).

**Prompt para o Claude:**
> Crie em `tests/backend/` uma fixture com duas instituições completas (turmas,
> crianças, professores, registros de escrita/desenho/leitura/observação,
> planejamentos, relatórios) e uma suíte `test_isolamento_tenant.py` que, para
> cada endpoint de listagem/detalhe da API, autentica como usuário da escola A
> e verifica que nenhum dado da escola B é retornado. Marque com
> `@pytest.mark.xfail(strict=False)` os casos que hoje falham, gerando um
> relatório do que está vazando. Não corrija os vazamentos ainda — esta fase é
> só diagnóstico executável. Atualize o CHANGELOG.

### Fase 1 — Completar o modelo de dados

**Objetivo:** toda linha de dado tem dono (tenant) explícito e derivável.

- Adicionar `instituicao_id` (UUID, indexado, null=True inicialmente) a:
  `RegistroEscrita`, `RegistroDesenho`, `RegistroLeitura`, `RegistroObservacao`,
  `PlanejamentoSemanal`, `ObservacaoTranscricao`, `ProducaoFoto`, `SerieConfig`,
  `ConfiguracaoRegistro`, `OpenAIUsage` (filhos como `PlanejamentoDiario`
  derivam do pai — documentar).
- Adicionar **FK `crianca` a `RegistroEscrita`/`RegistroDesenho`** (nullable) e
  passar a preenchê-la no upload — o casamento por nome não sobrevive ao
  multi-tenant (e já é fragilidade conhecida hoje).
- Migration de **backfill derivado**: escrita/desenho ← `turma_id` → `Turma.instituicao_id`;
  leitura/observação ← criança; planejamento ← turma; usage ← usuário. Registros
  órfãos vão para relatório de exceções, não travam a migração.
- Depois do backfill validado: `null=False` em segunda migration.

**Prompt para o Claude:**
> Adicione `instituicao_id` (UUIDField, db_index, inicialmente null) aos modelos
> listados na Fase 1 do docs/PLANO_MULTI_TENANT.md e FK nullable `crianca` a
> RegistroEscrita e RegistroDesenho. Crie a migration de schema e uma data
> migration de backfill que deriva a instituição via turma/criança/professor,
> logando órfãos sem interromper. Preencha os campos novos em todos os pontos
> de escrita (uploads, services). Rode a suíte, escreva testes do backfill em
> `tests/backend/` e atualize o CHANGELOG. Não altere comportamento de leitura
> ainda.

### Fase 2 — Enforcement central (o coração da mudança)

**Objetivo:** filtro de tenant deixar de ser opt-in por view.

- **Middleware** que resolve `request.instituicao_id` a partir do usuário
  autenticado (`Usuario.instituicao`) — nunca do payload do cliente.
- **`TenantManager`/`TenantQuerySet`** nos modelos com tenant: método
  `.da_instituicao(request)` e, onde viável, manager default que **exige**
  escopo (acesso sem escopo explícito lança erro em DEBUG/testes).
- Trocar `DEFAULT_PERMISSION_CLASSES` para `IsAuthenticated` e liberar
  explicitamente as exceções (login, health, reset de senha) — inverte o
  default inseguro atual.
- Varredura completa de `views_legacy.py`/`views_rest.py`/`views/`
  substituindo `.objects.all()`/filtros ausentes; cada view legada tocada é
  **reimplementada em `views/<modulo>.py`** (regra do projeto).
- `servir_arquivo`: exigir autenticação e validar que o registro do hash
  pertence à instituição do usuário.
- Frontend continua enviando o que envia; o servidor passa a **ignorar**
  `instituicao_id` vindo do cliente (deriva do usuário).
- Critério de aceite: suíte da Fase 0 **toda verde** (remover os `xfail`).

**Prompt para o Claude:**
> Implemente o enforcement de tenant descrito na Fase 2 do
> docs/PLANO_MULTI_TENANT.md: middleware que resolve request.instituicao_id do
> usuário autenticado, TenantQuerySet/Manager nos modelos com instituicao_id,
> DEFAULT_PERMISSION_CLASSES=IsAuthenticated com allowlist explícita, e
> varredura de todas as views substituindo consultas sem escopo — views legadas
> tocadas devem ser reimplementadas em views/<modulo>.py conforme o CLAUDE.md.
> Inclua autenticação e checagem de dono em servir_arquivo. Trabalhe endpoint
> por endpoint removendo os xfail de test_isolamento_tenant.py até a suíte
> ficar verde. Teste no Chrome os fluxos principais (professora e coordenação)
> ao final. CHANGELOG detalhado.

### Fase 3 — Coordenação e jobs por tenant

**Objetivo:** agregações e agendamentos cientes de tenant.

- Reescrever `services/coordenacao_cache.py` para receber `instituicao_id` e
  **filtrar tudo** (remover a premissa documentada de banco dedicado). O
  `NARA_INSTITUICAO_ID` do env morre.
- `refresh_coordenacao_cache` (command + task Celery do scheduler): iterar
  **todas** as instituições ativas.
- Revisar `services/alerts.py`, `analytics.py`, `indicadores_turma`,
  `alfabetizacao_criancas` (estes últimos já filtram por turma — validar a
  cadeia turma→instituição).

**Prompt para o Claude:**
> Refatore services/coordenacao_cache.py para que todas as agregações filtrem
> por instituicao_id recebido por parâmetro, removendo a premissa de banco
> dedicado documentada no módulo e o uso de NARA_INSTITUICAO_ID. Atualize o
> management command e a task do scheduler para iterar todas as instituições
> ativas. Adapte tests/backend/test_coordenacao_cache.py para o novo contrato,
> acrescentando um teste com duas instituições que prova que os agregados não
> se misturam. CHANGELOG.

### Fase 4 — Storage e artefatos

**Objetivo:** arquivos também isolados (defesa em profundidade).

- Novos uploads com prefixo por tenant: `t/<instituicao_id>/escrita/...`,
  `t/<...>/relatorios/...`, `audio/leitura/...` idem.
- URLs pré-assinadas continuam curtas (1h) — ok.
- `servir_arquivo`/downloads: além da checagem da Fase 2, caminho novo já
  embute o tenant. Arquivos legados são migrados na Fase 6 (cópia S3 com
  prefixo) ou mantidos com validação por registro (decisão de custo).

**Prompt para o Claude:**
> Introduza prefixo por instituição nas chaves S3 de todos os uploads novos
> (produções, áudio de leitura, PDFs de relatório, logos), centralizando a
> montagem da chave em api/storage.py. Garanta retrocompatibilidade de leitura
> com chaves antigas sem prefixo. Testes do formato de chave e CHANGELOG.

### Fase 5 — Frontend

**Objetivo:** alinhar o cliente ao novo contrato (sem confiar nele).

- Remover envios redundantes de `instituicao_id` onde o servidor agora deriva.
- Admin global (se o produto exigir gestão cross-escola): perfil `admin` com
  seletor de instituição — decisão de produto, não requisito técnico.
- Testes E2E (Playwright em `tests/`) com duas escolas.

**Prompt para o Claude:**
> Revise o frontend (apiClient e services/api.js) removendo o envio de
> instituicao_id nos endpoints em que o backend agora deriva do usuário, e
> ajuste os pontos que liam NARA_INSTITUICAO_ID implícito. Rode os fluxos
> principais no Chrome (login professora, registro, relatório, coordenação) e
> os testes E2E. CHANGELOG.

### Fase 6 — Migração dos clientes antigos (consolidação)

**Objetivo:** trazer cada banco dedicado para a instância compartilhada.

Ponto a favor decisivo: **PKs são UUID** em quase tudo — colisão de ids entre
escolas é improvável por construção (verificar as exceções de PK inteira:
`RegistroEscrita/Desenho/Leitura` etc., que precisarão de **remapeamento de id**
no import, com tabela de/para para preservar FKs).

Passo a passo por escola:

1. **Congelamento**: janela de manutenção; backup completo (banco + S3).
2. **Export**: dump lógico por tabela (`COPY`/fixtures) do banco da escola.
3. **Normalização**: script de import que
   - garante a `Instituicao` da escola no banco alvo;
   - preenche `instituicao_id` nos registros que não têm (usando o valor do
     `.env` da escola de origem / derivação por turma);
   - **remapeia PKs inteiras** e atualiza FKs dependentes;
   - deduplica catálogos globais (`HabilidadeBNCC`, `PerguntaBNCC` — manter um
     catálogo canônico e mapear referências);
   - resolve colisões de `Usuario.email` (relatório manual — não automatizar).
4. **S3**: cópia dos objetos para o bucket alvo com o prefixo do tenant;
   atualização de `arquivo_path`/`pdf_storage_key`/`logo_url` no import.
5. **Validação**: contagens por tabela origem×destino, amostragem de
   relatórios/PDF abertos lado a lado, suíte de isolamento rodada no alvo.
6. **Cutover**: DNS/URL da escola aponta para a instância compartilhada;
   instância antiga fica read-only por N dias (rollback barato).
7. Repetir escola a escola — **piloto com a menor primeiro**, nunca big-bang.

**Prompt para o Claude:**
> Escreva o comando de management `importar_tenant` descrito na Fase 6 do
> docs/PLANO_MULTI_TENANT.md: recebe um dump do banco de uma escola e o UUID da
> instituição, importa preenchendo instituicao_id ausente, remapeando PKs
> inteiras com tabela de/para (preservando FKs), deduplicando HabilidadeBNCC e
> PerguntaBNCC contra o catálogo do destino e reportando colisões de email sem
> resolvê-las automaticamente. Inclua modo --dry-run com relatório de contagens
> por tabela e testes de integração em tests/integration/ usando dois dumps
> sintéticos. CHANGELOG.

### Fase 7 — Hardening e operação contínua

- Suíte de isolamento vira **gate de CI** (endpoint novo sem teste de tenant
  não passa).
- `OpenAIUsage` com `instituicao_id` → custo de IA por escola (billing).
- Rate-limit por tenant (throttles atuais são globais/por usuário).
- Auditoria de acessos cross-tenant negados (log estruturado).
- Documentar no CLAUDE.md a regra: *todo modelo novo declara tenant; toda view
  nova usa o escopo do middleware*.

**Prompt para o Claude:**
> Feche o hardening multi-tenant: adicione instituicao_id ao OpenAIUsage com
> backfill via usuário, throttling por instituição, logging estruturado de
> tentativas de acesso cross-tenant e uma seção no CLAUDE.md documentando as
> regras de tenancy para código novo (manager obrigatório, teste de isolamento
> por endpoint). CHANGELOG.

---

## 4. Riscos principais e mitigação

| Risco | Mitigação |
|---|---|
| Vazamento silencioso entre escolas (o pior cenário — dados de crianças) | Fase 0 antes de tudo; manager que *exige* escopo; gate de CI |
| Casamento por nome misturar escolas | FK `crianca` na Fase 1 + escopo em toda query de nome |
| Backfill errado de `instituicao_id` | Data migration com relatório de órfãos + validação por contagem antes do `null=False` |
| Regressão nas telas (filtros novos escondendo dados legítimos) | Testes E2E com duas escolas; rollout com escola piloto |
| Consolidação corromper FKs (PKs inteiras) | Tabela de/para no import + `--dry-run` + instância antiga read-only para rollback |
| Endpoint novo esquecer o filtro (pós-projeto) | Default `IsAuthenticated` + manager + regra no CLAUDE.md + CI |

## 5. Ordem recomendada e dependências

```
Fase 0 ──► Fase 1 ──► Fase 2 ──► Fase 3 ──► Fase 5 ──► Fase 6 (por escola) ──► Fase 7
                         └──────► Fase 4 (paralelo a 3)
```

Fases 0–5 acontecem na base de código com o sistema ainda operando no modelo
atual (nada quebra os deploys dedicados — filtros por instituição são inócuos
num banco de uma escola só). A Fase 6 é a virada operacional, escola a escola.
