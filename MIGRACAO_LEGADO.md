# Migração do legado → multi-nara — rastreamento

Objetivo: quando a migração terminar, rodar um "pente fino" nos arquivos
legados abaixo pra confirmar que nada mais referencia eles, e então
descartá-los (renomear pra `.bak` ou apagar). Enquanto isso, eles continuam
intactos no repositório como fonte de referência.

Comando pra checar se um arquivo legado ainda é importado por algo:
```bash
grep -rn "from api.<nome_arquivo>\|from \.<nome_arquivo>\|import <nome_arquivo>" server/api --include="*.py"
```

## Status por arquivo legado

### `server/api/views_legacy.py` — PARCIALMENTE minerado, NÃO descartar ainda
Extraído até agora:
- `run_with_timeout`, `validate_uploaded_file`, `IA_REQUEST_TIMEOUT_SECONDS`,
  `IA_AUDIO_TIMEOUT_SECONDS` → `server/api/ia_utils.py` (portados sem alteração,
  são funções puras)

Ainda **não** minerado (fica pra quando reconstruirmos essas features de verdade,
com upload/IA, não só CRUD simples):
- Upload/validação de imagem (`ALLOWED_IMAGE_MIME_TYPES`, `resolve_mime_type`,
  `CANONICAL_MIME_BY_EXTENSION`) — usar quando fizermos análise de
  escrita/desenho com upload real
- Upload/validação de áudio (`ALLOWED_AUDIO_MIME_TYPES`) — usar no fluxo de
  `RegistroLeitura` com o NaraNN
- `check_rate_limit` — rate limiting customizado
- Lógica de geração de PDF de relatório (`ensure_pdf` e afins, se existir
  mais adiante no arquivo — ainda não vi o arquivo inteiro)
- Fluxo de dispositivo gravador (pareamento, upload de áudio do gravador)

### `server/api/views_rest.py` — NÃO minerado ainda
Era referenciado por praticamente todo o `urls.py` antigo (CRUD de
`criancas`, `relatorios`, `turmas`, `instituicoes`, `usuarios`, `disciplinas`,
etc.). Como reconstruímos o CRUD desses recursos do zero (com o schema novo),
é bem provável que a maior parte vire descartável sem extração — mas alguma
lógica de negócio específica (ex: geração de relatório, cálculo de
indicadores da coordenação) pode valer a pena revisar antes de descartar.

### `server/api/views_backup.py`, `server/api/views_clean.py` — NÃO abertos ainda
Não sabemos o que têm. Prováveis variações/rascunhos do `views_rest.py`.
Avaliar quando (e se) formos precisar.

### `server/api/models/prompt.py`, `paee.py`, `dispositivo.py` — DESCARTADOS
Renomeados pra `.bak` (não apagados). Todo o conteúdo já foi reconstruído
dentro de `server/api/models/base.py`. Não precisam de mineração — já foram
100% substituídos, não complementados.

### `server/api/serializers.py` (versão antiga) — DESCARTADO
Substituído inteiro. Usava models que não existem mais (`Crianca`,
`PerguntaBNCC`, etc.). Não houve extração — foi reescrito do zero.

### `server/api/urls.py` (versão antiga) — DESCARTADO
Substituído inteiro por um novo, construído incrementalmente conforme cada
recurso foi reconstruído.

### `server/api/admin.py.bak` — NÃO aberto
Existe no projeto (vi só o nome no print da pasta), nunca cheguei a olhar o
conteúdo. O `admin.py` novo foi escrito do zero, sem depender dele.

## Arquivos JÁ portados por completo (não são mais "legado", já são o código atual)
- `password_reset.py` → `services/password_reset.py` (1 correção: `ativo`→`is_active`)
- `planejamento_ia.py` → `services/planejamento_ia.py` (`_candidatos_bncc` reescrita)
- `planejamento.py` (service) → `services/planejamento.py` (`resolver_habilidade_bncc` simplificada)
- `openai_client.py`, `throttles.py` → copiados sem alteração
- `storage.py` → copiado (só renomeou parâmetro `crianca`→`aluno`)
- `prompt_resolver.py` → adaptado (`cliente_id` solto → FK `instituicao`)
- `views/auth.py` → reconstruído com JWT, mantendo `alterar_senha` original
- `views/planejamento.py` → portado com ajustes de schema (FK `professor`
  em vez de `professora_id`/`professora_nome`, `related_name` corrigido)