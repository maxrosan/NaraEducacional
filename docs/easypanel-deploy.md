# Implantacao da Nara no Easypanel

Este tutorial descreve a implantacao da plataforma Nara no Easypanel com tres instancias isoladas (Unifan, Unica e Demo), mantendo um unico servico de Postgres com bases separadas.

## 1. Provisionamento do Postgres

1. No Easypanel, crie um servico de Postgres com o nome `nara-db`.
2. Configure a imagem `postgres:14-alpine`.
3. Defina usuario e senha do banco conforme as credenciais oficiais do projeto.
4. Abra o terminal do container `nara-db` e crie as bases:

```bash
psql -U nara_user -d postgres -c "CREATE DATABASE nara_demo;"
psql -U nara_user -d postgres -c "CREATE DATABASE nara_unifan;"
psql -U nara_user -d postgres -c "CREATE DATABASE nara_unica;"
```

## 2. Backend (Django) por instancia

Crie tres servicos do tipo Aplicativo, por exemplo:

- `demo-backend`
- `unifan-backend`
- `unica-backend`

### Origem do codigo

- Repositorio: Nara
- Branch: `master`

### Build

- Build Context: `server`
- Dockerfile Path: `server/Dockerfile`

### Rede

- Porta do container: `8001`
- Dominio: use o dominio da API da instancia (ex: `api-demo.naraeducacional.com`).

### Variaveis de ambiente

Configure as variaveis do `.env.prod` por instancia, garantindo:

- `POSTGRES_DB` aponta para a base correta (`nara_demo`, `nara_unifan`, `nara_unica`).
- `POSTGRES_HOST` aponta para `nara-db`.
- Chaves sensiveis (OpenAI e S3) sao informadas apenas no Easypanel.

### Armazenamento

Mapeie o volume `/app/uploads` para persistencia de midias.

## 3. Frontend (Vite) por instancia

Crie tres servicos do tipo Aplicativo, por exemplo:

- `demo-frontend`
- `unifan-frontend`
- `unica-frontend`

### Build

- Build Context: `client`
- Dockerfile Path: `client/Dockerfile`

### Rede

- Porta do container: `5173`
- Dominio: use o dominio publico da instancia (ex: `demo.naraeducacional.com`).

### Variaveis do frontend

Defina `VITE_API_BASE_URL` com a URL completa do backend da instancia, por exemplo:

- `https://api-demo.naraeducacional.com`

## 4. Restauracao de dados no ambiente Demo

1. Conecte um cliente SQL (DBeaver ou TablePlus) ao IP do VPS na porta `5432`.
2. Use a base `nara_demo`, usuario `nara_user` e a senha do servico `nara-db`.
3. Execute o script do arquivo `backups/backup_nara_20260130_225016.sql` diretamente na base `nara_demo`.

## 5. Validacao recomendada antes do deploy

Antes de subir a instancia Unifan, valide a lista de variaveis de ambiente para garantir que:

- A base e o dominio correspondem a Unifan.
- As chaves de OpenAI e S3 estao corretas.
- Os parametros de seguranca (como `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`) estao ajustados.
