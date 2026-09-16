# AGENTS.md

## Project Overview

Nara is a pedagogical support platform with AI-assisted BNCC report generation. It is a full-stack application with a React SPA frontend and a Django REST backend.

## Architecture

- Frontend: `client/` — React 19, Vite, React Router, Tailwind, Radix UI
- Backend: `server/` — Django 5.2, DRF, session/cookie auth, PostgreSQL
- Tests: `tests/` — E2E with Playwright
- Infra: Docker Compose (dev + prod), Gunicorn, Nginx

User roles:

- `admin`
- `coordenador`
- `professor`
- `professor_especialista`
- `especialista`

## Key Entrypoints

- `client/src/main.jsx` — React bootstrap (Router, AuthProvider, Sentry, health check)
- `client/src/App.jsx` — All SPA routes (public + protected)
- `client/src/contexts/AuthContext.jsx` — Session management, inactivity timeout
- `client/src/lib/apiClient.js` — Supabase-compatible facade over REST API
- `client/src/services/api.js` — Direct HTTP calls for legacy/specific endpoints
- `server/nara_api/urls.py` — Routes `/admin/` and `/api/`
- `server/api/urls.py` — All API endpoint definitions
- `server/api/views_rest.py` — Modern REST CRUD views
- `server/api/views_legacy.py` — Legacy views still actively used
- `server/api/views/__init__.py` — Merges legacy + REST + new views using `*` imports with manual overrides

## Development

### With Docker

```bash
cp .env.example .env
# Edit .env with real credentials
docker-compose up -d --build
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8001`

### Without Docker

```bash
# Backend
cd server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8001

# Frontend
cd client
npm install
npm run dev
```

## Running Tests

```bash
# Backend
cd server && python manage.py test

# E2E
cd tests && pytest

# Frontend build check
cd client && npm run build
```

## Code Patterns

### Frontend API calls

Two patterns coexist:

1. `apiClient.from('table').select()/insert()` for Supabase-style CRUD over REST.
2. `apiService`, `authFetch`, or raw `fetch` for uploads, AI endpoints, and legacy flows.

All requests use `credentials: 'include'` for session cookies. Write requests include `X-CSRFToken`.

### Auth flow

1. Frontend calls `GET /api/auth/csrf/` then `POST /api/auth/login/`.
2. Django creates the session and returns cookie plus user payload.
3. `AuthContext` manages auth state and `ProtectedRoute` enforces access by auth and role.
4. Login redirects by role: `/admin`, `/coordenacao`, or `/home-professor`.

### Backend structure

- Models: `server/api/models.py`
- Serializers: `server/api/serializers.py`
- Services: `server/api/services/`
- Views: split across `views_rest.py`, `views_legacy.py`, and `views/`

### External integrations

- OpenAI: transcription, observation extraction, report generation, media analysis
- S3: uploads in production; local `server/uploads/` in development
- Mailtrap: password reset emails
- Sentry: frontend and backend error tracking
- `ffmpeg`: implicit dependency for audio processing

## Known Issues

- `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES = AllowAny`; endpoint protection depends on individual views
- `views_legacy.py` is large and tightly coupled but still central
- `views_clean.py` and `views_backup.py` are dead code
- Frontend references tables not present in the backend: `projeto_turmas`, `observacoes_comentarios`, `observacoes_especialistas`, `especialista_funcoes`, `atendimentos_especialistas`
- Duplicate code exists in audio and BNCC flows
- Some pages are present but not routed: `CoordinatorIndicatorsPage.jsx`, `TestAnalysisPage.jsx`, `TestProductionAnalysis.jsx`

## Working Conventions

- The codebase, comments, variable names, and UI text are primarily in Brazilian Portuguese
- Preserve existing naming and language conventions when changing code
- Inspect route guards, auth bootstrap, and mixed legacy/REST flows carefully before making auth or navigation changes
