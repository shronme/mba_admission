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

- **`POST /candidates/enter`** — JSON `{ "email": "…", "full_name": "…" (optional) }`. Case-insensitive email match; creates a candidate with a derived display name if new. Returns `{ created, candidate, session_token }` including `profile` when present.

Use the returned token for subsequent endpoints:
- `Authorization: Bearer <session_token>`

This is still a **scaffold** (fake auth); lock down or replace before production.

See **[`RAILWAY_DEPLOYMENT.md`](RAILWAY_DEPLOYMENT.md)** for production deploy notes.

## Candidate chat + file intake (initial scaffold)

- **Upload docs (bytes stored in Railway Storage bucket when configured):**
  - `POST /files/upload` (multipart, field name: `files`)
  - `GET /files` (lists uploaded files for the candidate)
  - `GET /files/{file_id}/download` (streams raw bytes)
- **Chat:**
  - `POST /chat/threads` (creates a thread + initial assistant intake message)
  - `GET /chat/threads/{thread_id}/messages` (message history)
  - `POST /chat/threads/{thread_id}/messages/stream` (streams assistant output as `text/plain`)

All `/files/*` and `/chat/*` endpoints require:
- `Authorization: Bearer <session_token>`

DSPy plumbing currently powers the assistant text decisions in a deterministic MVP mode; later we’ll wire real LLM calls + streaming tokens.

### Using OpenAI for DSPy (optional)

To enable real LLM calls for the assistant:
- Set `DSPY_MODE=openai`
- Set `OPENAI_API_KEY` in your runtime environment (Docker compose: in your shell before `make up`, e.g. `export OPENAI_API_KEY=...`)
- Optional: set `DSPY_MODEL` (defaults to `openai/gpt-4o-mini`)

## Phoenix Cloud Traces (optional)

If you want traces in Phoenix Cloud, set these on **both** `web` and `worker`:
- `PHOENIX_COLLECTOR_ENDPOINT` (HTTP collector endpoint, must end with `/v1/traces`)
- `PHOENIX_API_KEY` (optional, if your collector requires auth)
- `PHOENIX_PROJECT_NAME` (optional; defaults to `mba_admissions`)

The backend will emit a `startup.phoenix.tracing` span on startup so you can confirm traces are flowing.

To get LLM/chain observability in Phoenix, ensure real LLM calls are enabled (set `DSPY_MODE=openai` and `OPENAI_API_KEY`), then hit the chat endpoint at least once (e.g. `POST /chat/threads/{thread_id}/messages/stream`).
