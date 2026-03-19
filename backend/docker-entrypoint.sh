#!/bin/sh
set -e

# Single image: select process via env (Railway / compose set per service).
# - web: FastAPI (honours Railway PORT)
# - worker: Celery worker
ROLE="${APP_ROLE:-web}"

case "$ROLE" in
  web)
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
