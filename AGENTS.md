# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

AI Admissions OS — a FastAPI backend (Python 3.11) with a placeholder worker process, orchestrated via Docker Compose (API + worker + PostgreSQL 16 + Redis 7). Currently Phase 0 bootstrap; only the `/health` endpoint exists.

### Running services

- **Full stack (Docker Compose):** `make up` starts api (port 8000), worker, postgres (5432), redis (6379). Stop with `make down`.
- **Backend dev server (without Docker):** activate the venv then run `cd backend && PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`. The current test suite does not require Postgres or Redis.

### Testing

- `make test` or `cd backend && PYTHONPATH=. python -m pytest -q` — runs the backend test suite. Tests use FastAPI's `TestClient` (in-process); no database or Redis needed.

### Linting

- No linter is configured yet (no ruff, flake8, mypy, or pyproject.toml).

### Docker in Cloud Agent VMs

Docker requires special setup in the cloud agent environment (fuse-overlayfs storage driver, iptables-legacy). After Docker is installed, start the daemon with `sudo dockerd &>/tmp/dockerd.log &` and allow non-root access with `sudo chmod 666 /var/run/docker.sock`.

### Key gotchas

- The `backend/Dockerfile` build context is the repo root (`.`), not `backend/`.
- The worker is a no-op heartbeat loop; it doesn't process real jobs yet.
- No Alembic migrations exist; PostgreSQL is declared but not connected by app code.
