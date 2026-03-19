---
name: task-001-backend
overview: Add a production-oriented FastAPI backend skeleton with async Postgres wiring, Celery + Redis configuration, health endpoint, logging, local docker-compose, and Railway-friendly Docker build/run commands.
todos:
  - id: create-backend-structure
    content: Add `backend/` package skeleton (FastAPI app, core modules, routers, placeholders for services/dspy/workers).
    status: completed
  - id: config-settings
    content: Implement `backend/app/core/config.py` with `pydantic-settings` for env-driven config (DB/Redis/Celery/Logging/Healthcheck flags).
    status: completed
  - id: async-postgres-wiring
    content: Implement `backend/app/core/db.py` with async SQLAlchemy engine + session dependency; add a manual connection test helper (not run in CI automatically).
    status: completed
  - id: celery-redis-wiring
    content: Implement `backend/app/core/celery_app.py` + a minimal `ping_redis` task in `backend/app/workers/tasks/`.
    status: completed
  - id: fastapi-health
    content: Implement `backend/app/main.py` and `backend/app/api/routes/health.py` for `/health`.
    status: completed
  - id: logging
    content: Add `backend/app/core/logging.py` and wire `configure_logging()` into `backend/app/main.py`.
    status: completed
  - id: deps-and-tests
    content: Create `backend/requirements.txt` and `backend/tests/test_health.py` to satisfy existing CI workflow expectations.
    status: completed
  - id: local-docker-compose
    content: Add root `docker-compose.yml` for Redis + Postgres; add example env values matching service hostnames.
    status: completed
  - id: dockerfile-railway-notes
    content: Add `backend/Dockerfile` and document Railway web/worker run commands + env var mapping.
    status: completed
  - id: railway-runbook
    content: Add a step-by-step Railway deployment runbook (Docker-based) as an in-repo doc (e.g. `backend/RAILWAY_DEPLOYMENT.md`), including how to create env vars, configure web/worker processes, and validate deployment.
    status: completed
  - id: wiring-smoke-test
    content: "Add a basic end-to-end wiring smoke test script (e.g. `backend/scripts/wiring_smoke_test.py` or `.sh`) that proves all pieces talk to each other: FastAPI -> enqueue Celery job -> worker -> Redis broker -> Postgres (via a minimal DB read/write). Include simple commands you can run before building the frontend (a lightweight FE stand-in via `curl`/HTTP)."
    status: completed
isProject: false
---

## Scope

Implement `TASK 001` per your backlog: FastAPI skeleton, `/health`, config management, Celery app wiring, Redis config, Postgres connection setup, basic logging, and local dev `docker-compose` for Postgres + Redis.

This repo currently lacks the `backend/` directory entirely, but CI expects it (see `[.github/workflows/ci.yml](backend/.github/workflows/ci.yml)` which runs `pip install -r requirements.txt` and `pytest` inside `backend/`).

## Target architecture (wiring)

```mermaid
flowchart LR
  Client[Client] -->|HTTP| FastAPI[FastAPI app]
  FastAPI -->|enqueue| Celery[Celery app]
  Celery -->|messages| Redis[Redis broker/result]
  Worker[Celery worker] -->|run tasks| Celery
  Worker -->|DB ops| Postgres[(Postgres)]
```



## Implementation plan

1. Create backend package structure under `backend/` matching the backlog’s suggested layout.
  - Add `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/db.py`, `backend/app/core/celery_app.py`.
  - Add `backend/app/api/routes/health.py` and `backend/app/api/routes/__init__.py`.
  - Add `backend/app/services/` and `backend/app/dspy_modules/` as empty packages (placeholders for later tasks).
  - Add `backend/app/workers/tasks/` with at least one minimal Celery task (e.g., `ping_redis`) so the worker can demonstrate connectivity.
2. Add config management with `pydantic-settings`.
  - `backend/app/core/config.py` defines settings for:
    - `ENV`, `LOG_LEVEL`
    - `DATABASE_URL`
    - `REDIS_URL` (and Celery `broker_url`/`result_backend` derived from it)
    - `CELERY_TASK_DEFAULT_QUEUE` (optional)
    - `HEALTHCHECK_DB` (default false to keep CI lightweight)
  - Ensure settings are friendly for Railway env vars.
3. Implement async Postgres wiring (since you selected async SQLAlchemy).
  - `backend/app/core/db.py` uses `sqlalchemy.ext.asyncio.create_async_engine` and an `async_sessionmaker`.
  - Provide a FastAPI dependency `get_db_session()` that yields an `AsyncSession`.
  - Provide a non-invasive `async def test_db_connection()` utility for manual verification (avoid running it automatically in CI).
4. Implement Celery + Redis wiring.
  - `backend/app/core/celery_app.py` creates and configures the Celery instance from settings.
  - Configure JSON serialization, broker/result backend = Redis.
  - Provide a tiny example task in `backend/app/workers/tasks/ping_redis.py` that pings Redis.
  - Ensure the Celery app can import cleanly without requiring Postgres/Redis to be up at import time.
5. Add FastAPI skeleton and health endpoint.
  - `backend/app/main.py` creates the FastAPI app, installs basic logging, includes health router.
  - `/health` endpoint returns `{"status":"ok"}`.
  - Optionally, if `HEALTHCHECK_DB=true`, include `db_connected` and `redis_connected` fields (but keep default off).
6. Add basic structured logging.
  - `backend/app/core/logging.py` provides a `configure_logging()` using stdlib logging (optionally JSON formatting if desired).
  - Ensure logs include `logger name`, `level`, and message; keep it simple for Railway.
7. Add dependencies and tests so CI passes.
  - Create `backend/requirements.txt` including runtime deps + test deps required by CI.
  - Create `backend/tests/test_health.py` that boots the FastAPI app and validates `/health` returns OK.
8. Add local dev docker-compose.
  - Create root `docker-compose.yml` with:
    - `redis` service (with exposed port 6379 for local development)
    - `postgres` service (with exposed port 5432)
  - Add root `.env.example` (or `backend/.env.example`) with local values for `DATABASE_URL` and `REDIS_URL` that match service hostnames (`postgres`, `redis`).
9. Railway-friendly Dockerization (since you selected Docker).
  - Create `backend/Dockerfile` that:
    - installs `requirements.txt`
    - sets `WORKDIR` to `backend/`
    - runs from module `app.*` correctly
  - Document Railway process split:
    - Web service command: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
    - Worker service command: `celery -A app.core.celery_app worker -l info`
  - Document required env vars on Railway: `DATABASE_URL`, `REDIS_URL` (and optionally `LOG_LEVEL`, `ENV`).

## Deliverables checklist vs acceptance criteria

- FastAPI boots locally: `uvicorn` command documented
- `/health` returns OK: endpoint + test
- Celery worker starts successfully: documented `celery worker` command
- Redis broker is connected: run `ping_redis` task to verify
- DB session can initialize: manual `test_db_connection()` utility
- docker-compose can start local dependencies: `docker compose up -d redis postgres`
- Railway deployability: step-by-step Railway runbook (Docker-based) provided at the end of implementation (documented in-repo)
- Cross-component wiring check: runnable “wiring smoke test” that validates FastAPI + Celery enqueue + Celery worker + Redis broker + Postgres connectivity (FE stand-in via `curl`), before frontend work

