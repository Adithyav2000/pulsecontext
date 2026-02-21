# PulseContext — Backend (MVP0)

Status: refactored to Service + Repository pattern. Minimal FastAPI app with DB-backed ingest/timeline and a simple UI.

Quick status
- DB: PostgreSQL service in `infra/docker-compose.yml` (container: `infra-db-1`) — port 5432.
- Backend: FastAPI app in `backend/` (run with the project's `.venv`).
- Endpoints: `/health`, `/ingest`, `/timeline`, `/seed`, `/ui`.

How to run (from project root)

1. Start DB (from `pulsecontext/infra`):

```powershell
cd infra
docker compose up -d
```

2. Start backend (from `pulsecontext/backend`):

```powershell
cd backend
.venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

3. Test in browser:

- http://localhost:8000/health
- http://localhost:8000/docs
- http://localhost:8000/ui

Files and purpose
- `main.py` — thin HTTP routes. No DB SQL here.
- `settings.py` — single source of runtime config (reads `.env`).
- `db.py` — `get_conn()` helper (psycopg). Swap to pooling here later.
- `models.py` — Pydantic models (input validation).
- `repo_events.py` — SQL / DB-only functions (repository pattern).
- `service_events.py` — Business rules: validation, normalization, security checks, calls repo.
- `.env` — dev config used by `settings.py`.
- `requirements.txt` — Python deps used to create `.venv`.

Notes / troubleshooting
- If `/health` fails: ensure DB container is healthy (`docker logs infra-db-1`) and `DB_URL` in `.env` is reachable.
- If venv activation fails on Windows PowerShell, run: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` then activate.
- All DB writes go through `EventService.ingest_events()` — this is intentional.

Next steps
- Implement auth and caller_user propagation to `ingest`.
- Add DB migrations and tests.
