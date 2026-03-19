# Backend (FastAPI)

## Task 002 — persistence

- **Models:** `app/db/models/` (candidates, profiles, chats, files, strategy, tasks, essays, AI runs, audit).
- **Repositories:** `app/repositories/` (`CandidateRepository`, `ChatRepository`).
- **Migrations:** Alembic in `alembic/versions/` — create new revisions with `alembic revision --autogenerate` only.

### Test with Docker Compose (migrations on boot)

From the **repository root**:

```bash
docker compose up --build web
```

- **`web`** waits until **Postgres is healthy**, then the entrypoint runs **`alembic upgrade head`**, then starts **uvicorn** on [http://localhost:8000](http://localhost:8000).
- **`worker`** does not run migrations (only the web role does).

Full stack (API + worker + Redis + Postgres):

```bash
docker compose up --build
```

Optional seed (host Python, DB reachable on `localhost:5432`):

```bash
cd backend && export PYTHONPATH=. DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions
python scripts/seed_task002_demo.py
```

### Commands without Docker (from `backend/`)

```bash
export PYTHONPATH=.
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions

alembic upgrade head
pytest -q
python scripts/seed_task002_demo.py
```

Use `docker compose up -d postgres` from the repo root if you only need Postgres on `localhost:5432`.

## Task 003 — Celery AI job framework

- **Base task:** `app/workers/base_task.py` (`AiJobTask` — retries, logging, `on_failure` → `ai_run` FAILED).
- **Payloads:** `app/workers/payloads.py` (Pydantic; add one model per job type).
- **Worker DB:** `app/core/sync_db.py`, `app/workers/ai_run_sync.py`.
- **Sample job:** `POST /jobs/sample-sleep` → `GET /jobs/ai-runs/{id}` (see **[`docs/AI_JOB_FRAMEWORK.md`](docs/AI_JOB_FRAMEWORK.md)**).

### Fake login (candidates)

- **`POST /candidates/enter`** — JSON `{ "email": "…", "full_name": "…" (optional) }`. Case-insensitive email match; creates a candidate with a derived display name if new. Returns `{ created, candidate }` including `profile` when present.

This is a **scaffold** (no auth); lock down or replace before production.

See **[`RAILWAY_DEPLOYMENT.md`](RAILWAY_DEPLOYMENT.md)** for production deploy notes.
