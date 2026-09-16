# GEMINI.md

## Project Overview
Nara is a pedagogical support platform with AI-assisted BNCC (Base Nacional Comum Curricular) report generation. It is a full-stack application consisting of a React SPA frontend and a Django REST backend.

## Architecture & Tech Stack
- **Frontend**: `client/` — React 19, Vite, React Router, Tailwind CSS, Radix UI.
- **Backend**: `server/` — Django 5.2, Django REST Framework (DRF), session/cookie authentication, PostgreSQL.
- **Tests**: `tests/` — E2E tests using Playwright.
- **Infrastructure**: Docker Compose (dev + prod), Gunicorn, Nginx.
- **User Roles**: `admin`, `coordenador`, `professor`, `professor_especialista`, `especialista`.

## Key Entrypoints
- `client/src/main.jsx`: React bootstrap (Router, AuthProvider, Sentry, health check).
- `client/src/App.jsx`: SPA routes definition (public + protected).
- `client/src/contexts/AuthContext.jsx`: Session management and inactivity timeout.
- `client/src/lib/apiClient.js`: Supabase-compatible facade over the REST API.
- `client/src/services/api.js`: Direct HTTP calls for legacy or specific endpoints.
- `server/nara_api/urls.py`: Main URL routing for `/admin/` and `/api/`.
- `server/api/urls.py`: API endpoint definitions.
- `server/api/views_rest.py`: Modern REST CRUD views.
- `server/api/views_legacy.py`: Legacy views still in active use.
- `server/api/views/__init__.py`: Merged views (legacy + REST + new).

## Development & Testing

### Environment Setup
1. Copy `.env.example` to `.env` in both root and subdirectories.
2. Edit `.env` with appropriate credentials.

### Running with Docker (Recommended)
```powershell
docker-compose up -d --build
```
- Frontend: http://localhost:5173
- Backend: http://localhost:8001

### Running without Docker
**Backend:**
```powershell
cd server
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8001
```
**Frontend:**
```powershell
cd client
npm install
npm run dev
```

### Testing Commands
- **Backend Tests**: `cd server; python manage.py test`
- **E2E Tests (Playwright)**: `cd tests; pytest`
- **Frontend Build Check**: `cd client; npm run build`

## Code Patterns & Conventions

### Frontend API Interactions
Two coexisting patterns:
1. `apiClient.from('table').select()/insert()`: Supabase-style facade for REST CRUD.
2. `apiService`/`authFetch`/raw `fetch`: Used for uploads, AI endpoints, and legacy flows.
- All requests must use `credentials: 'include'` for session cookies.
- Write operations must include the `X-CSRFToken` header.

### Authentication Flow
1. Frontend: `GET /api/auth/csrf/` then `POST /api/auth/login/`.
2. Backend: Django creates session, returns cookie + user payload.
3. `AuthContext` manages state; `ProtectedRoute` guards routes by auth and role.

### Backend Structure
- **Models**: `server/api/models.py` (Instituicao, Usuario, Turma, Crianca, RegistroObservacao, Relatorio, etc.).
- **Serializers**: `server/api/serializers.py` (includes frontend compatibility aliases).
- **Services**: `server/api/services/` (relatorio AI gen, audio transcription, media analysis, analytics, alerts).

### Language Policy
The codebase, comments, variable names, and UI text are primarily in **Brazilian Portuguese**. Adhere to this convention for all new code, comments, and user-facing text.

## Known Issues & Technical Debt
- `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES = AllowAny`: Security relies on individual view protections.
- `views_legacy.py` is large and tightly coupled but remains central.
- `views_clean.py` and `views_backup.py` are deprecated/dead code.
- Frontend references some non-existent backend tables (e.g., `projeto_turmas`).
- Code duplication exists in audio flows and BNCC components.
- Several pages are currently unrouted (e.g., `CoordinatorIndicatorsPage.jsx`).
