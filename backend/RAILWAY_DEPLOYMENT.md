# Railway Deployment (Docker-based) - Task 001

This doc explains how to deploy the backend skeleton on Railway using:
- FastAPI web process (`uvicorn`)
- Celery worker process (`celery worker`)
- Managed Postgres + Redis services

## 1) Prerequisites
1. Create a Railway account and a new project.
2. Make sure your Railway project can connect to Docker builds from this repository.

## 2) Add managed services
1. Add a **Redis** service to the Railway project.
2. Add a **Postgres** service to the Railway project.

## 3) Configure environment variables
The backend reads these variables (see `backend/app/core/config.py`):
1. `DATABASE_URL` (asyncpg required)
2. `REDIS_URL`
3. Optional: `LOG_LEVEL`, `ENV`

### DATABASE_URL format note (async SQLAlchemy)
Railway’s Postgres URL is often `postgres://...`.
Change it to `postgresql+asyncpg://...` before setting `DATABASE_URL`.

Example transformation:
- `postgres://user:pass@host:5432/dbname`
- `postgresql+asyncpg://user:pass@host:5432/dbname`

### REDIS_URL format
Set `REDIS_URL` to the Redis connection string Railway provides, typically in the form:
- `redis://default:password@host:port/0`

Celery uses Redis for both broker and result backend in this skeleton.

**Optional but recommended (Celery env precedence):** set these on **both** `web` and `worker` to the same Redis URL Railway gives you (mirrors `REDIS_URL`):
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

Celery may read `CELERY_BROKER_URL` from the environment; if it points at `localhost` while the app runs in a container, enqueue will fail with `Connection refused`.

## 4) Add the Docker build
1. Configure the deployable Docker source to use:
   - Dockerfile: `backend/Dockerfile`
2. Build context should include the `backend/` directory (in most setups, using the repo root as context is fine).

## 5) Configure processes (web + worker)
In Railway, add two processes pointing at the same Docker image.

### Process A: `web`
Start command:
```sh
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Process B: `worker`
Start command:
```sh
celery -A app.core.celery_app worker -l info
```

## 6) Deploy
Deploy the Railway service(s).

## 7) Validate connectivity (before building the frontend)
### A) Mock browser UI (optional)
Open `https://<your-web-host>/fe/` — a tiny static page calls `/health` and the wiring smoke endpoints in-browser (same origin).

### B) Check `/health`
1. Open the web process URL in your browser (or use `curl`).
2. Expected response from `GET /health`:
```json
{"status":"ok"}
```

### C) Wiring smoke test endpoints
After the worker is running, verify cross-component wiring using:
- `POST /wiring/smoke` -> returns a `job_id`
- `GET /wiring/smoke/{job_id}` -> returns `{ state, result }` when complete

You can test quickly with `curl`:
```sh
curl -s -X POST "$WEB_URL/wiring/smoke" -H "Content-Type: application/json"
```
Then poll:
```sh
curl -s "$WEB_URL/wiring/smoke/<job_id>"
```

Expected `result` includes:
- `redis_connected: true`
- `db_connected: true`
- `select_one: 1`

## 8) Local parity (recommended)
For local development, use `docker compose up -d redis postgres`, then:
- Terminal 1 (web): `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Terminal 2 (worker): `celery -A app.core.celery_app worker -l info`
- Smoke test: `python scripts/wiring_smoke_test.py`

