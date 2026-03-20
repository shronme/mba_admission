#!/bin/sh
set -e

# Single image: select process via env (Railway / compose set per service).
# - web: Alembic migrate (unless skipped) + FastAPI (honours Railway PORT)
# - worker: Celery worker (does not run migrations — avoid concurrent upgrades)
ROLE="${APP_ROLE:-web}"

case "$ROLE" in
  web)
    if [ "${SKIP_DB_MIGRATIONS:-}" != "1" ]; then
      export PYTHONPATH="${PYTHONPATH:-/app/backend}"
      cd /app/backend
      echo "docker-entrypoint: enabling pgvector extension"
      python -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
engine = create_engine(settings.database_url_sync())
with engine.connect() as conn:
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    conn.commit()
engine.dispose()
print('pgvector extension ready')
"
      echo "docker-entrypoint: alembic upgrade head"
      alembic upgrade head
    else
      echo "docker-entrypoint: SKIP_DB_MIGRATIONS=1 — skipping Alembic"
    fi
    if [ "${ENV:-}" = "development" ]; then
      exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
    else
      exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    fi
    ;;
  worker)
    if [ "${ENV:-}" = "development" ]; then
      exec watchmedo auto-restart --directory=./app --pattern="*.py" --recursive -- \
        celery -A app.core.celery_app:celery_app worker -l info
    else
      exec celery -A app.core.celery_app:celery_app worker -l info
    fi
    ;;
  *)
    echo "docker-entrypoint: unknown APP_ROLE='$ROLE' (use 'web' or 'worker')" >&2
    exit 1
    ;;
esac
