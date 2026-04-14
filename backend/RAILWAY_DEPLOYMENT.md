# Railway Deployment (Docker-based) - Task 001

This doc explains how to deploy the backend skeleton on Railway using:
- FastAPI web process (`uvicorn`)
- Managed Postgres + Redis services

## 0) Builder: use Docker (not Railpack)
New Railway services default to **Railpack**, which often **cannot** infer this monorepo (errors like `start.sh not found` / “could not determine how to build”).

This repo includes **`railway.toml` at the repository root** with `builder = "DOCKERFILE"` and `dockerfilePath = "backend/Dockerfile"`, so **web** and **worker** services pick up the same Docker build as `docker-compose` (build context = repo root).

**Healthchecks:** only the **web** service should use an HTTP healthcheck (e.g. `/health`).

**Next.js (`apps/web`):** separate Railway service — step-by-step in **[`apps/web/README.md`](../apps/web/README.md#deploy-on-railway)** (root directory `apps/web`, `NEXT_PUBLIC_API_URL`, CORS on the API).

**Dashboard alternative:** Service → **Settings → Build → Builder** → **Dockerfile**, path `backend/Dockerfile`, root directory = repo root (empty).

## 1) Prerequisites
1. Create a Railway account and a new project.
2. Make sure your Railway project can connect to Docker builds from this repository.

## 2) Add managed services
1. Add a **Postgres** service to the Railway project.
3. **(Recommended for uploads)** Add a Railway **Storage Bucket** — private, **S3-compatible** object storage for file bytes. Postgres should only store **`uploaded_files` metadata** (filename, size, `storage_uri`, status); the API uploads/downloads via the S3 API using credentials from the bucket’s **Credentials** tab. See Railway’s guide: **[Storage Buckets](https://docs.railway.com/guides/storage-buckets)**.

   Typical env vars (names vary slightly in the dashboard; mirror them into your **web** service): bucket name, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, `REGION`, and S3 **`ENDPOINT`** (Railway uses an S3-compatible endpoint, not AWS’s default). Buckets are **private** by default — use **presigned GET/PUT URLs** from FastAPI rather than exposing the bucket publicly.

## 3) Configure environment variables
The backend reads these variables (see `backend/app/core/config.py`):
1. `DATABASE_URL` (asyncpg required)
2. Optional: `LOG_LEVEL`, `ENV`

### DATABASE_URL format note (async SQLAlchemy)
Railway’s Postgres URL is often `postgres://...` or `postgresql://...` **without** a driver.

The backend **auto-normalizes** those to `postgresql+asyncpg://...` when settings load (see `normalize_database_url_for_asyncpg` in `backend/app/core/config.py`). You can still set `DATABASE_URL` to `postgresql+asyncpg://...` yourself if you prefer.

### Database migrations (Alembic — Task 002)
Schema is managed with **Alembic** (`backend/alembic/`, `backend/alembic.ini`). The image includes these files.

**On container start (Docker Compose + Railway):** the **`web`** process runs `alembic upgrade head` **before** `uvicorn` (see [`docker-entrypoint.sh`](docker-entrypoint.sh)). The **worker** does **not** run migrations (avoids two replicas racing the same upgrade).

- **Opt out (debug / custom flows):** set `SKIP_DB_MIGRATIONS=1` on the **web** service and run `alembic upgrade head` yourself.

`alembic/env.py` converts `DATABASE_URL` (`postgresql+asyncpg://…`) to a sync `postgresql+psycopg://…` URL for migrations.

**Local without Compose:** from `backend/` with Postgres running:
```bash
export PYTHONPATH=.
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions
alembic upgrade head
```

**New revisions:** always use autogenerate against a dev database, never hand-edit empty migrations:
```bash
alembic revision --autogenerate -m "describe change"
```

**Demo seed (optional):** `python scripts/seed_task002_demo.py` (requires `DATABASE_URL` and `PYTHONPATH=.` from `backend/` — not run automatically in Docker).

## 4) Add the Docker build
1. Configure the deployable Docker source to use:
   - Dockerfile: `backend/Dockerfile`
2. Build context should include the `backend/` directory (in most setups, using the repo root as context is fine).

## 5) Configure process (web)
Use **one Railway service** from the **same repo + same Dockerfile** (`backend/Dockerfile`). The image uses [`docker-entrypoint.sh`](docker-entrypoint.sh).

### Process A: `web` service
1. **Variables:** set `APP_ROLE=web` (optional if you rely on the default `web` in the entrypoint).
2. Railway injects **`PORT`** automatically — the entrypoint runs **`alembic upgrade head`** then `uvicorn` on that port.
3. **Custom Start Command:** leave **empty** so Docker’s `ENTRYPOINT` runs (recommended), *or* set the same as local:  
   `./docker-entrypoint.sh`  
   (only needed if your platform replaces `ENTRYPOINT`; on Railway, empty is usually fine.)

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
Verify cross-component wiring using:
- `POST /wiring/smoke` -> returns `{ redis_connected, db_connected, select_one }`

You can test quickly with `curl`:
```sh
curl -s -X POST "$WEB_URL/wiring/smoke" -H "Content-Type: application/json"
```

Expected `result` includes:
- `redis_connected: true`
- `db_connected: true`
- `select_one: 1`

## 8) Local parity (recommended)
For local development, use `docker compose up -d redis postgres`, then:
- Terminal 1 (web): `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Smoke test: `python scripts/wiring_smoke_test.py`

