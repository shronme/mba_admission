#!/bin/sh
set -e

# Single image: select process via env (Railway / compose set per service).
# - web: Alembic migrate (unless skipped) + FastAPI (honours Railway PORT)
# - worker: Celery worker (does not run migrations — avoid concurrent upgrades)
ROLE="${APP_ROLE:-web}"

case "$ROLE" in
  web)
    if [ "${SKIP_DB_MIGRATIONS:-}" != "1" ]; then
      echo "docker-entrypoint: alembic upgrade head"
      export PYTHONPATH="${PYTHONPATH:-/app/backend}"
      cd /app/backend
      alembic upgrade head
    else
      echo "docker-entrypoint: SKIP_DB_MIGRATIONS=1 — skipping Alembic"
    fi
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  worker)
    exec celery -A app.core.celery_app worker -l info
    ;;
  *)
    echo "docker-entrypoint: unknown APP_ROLE='$ROLE' (use 'web' or 'worker')" >&2
    exit 1
    ;;
esac
