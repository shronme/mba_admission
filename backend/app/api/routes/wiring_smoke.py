from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException
import redis

from app.core.config import settings

from app.core.celery_app import celery_app
router = APIRouter(prefix="/wiring", tags=["wiring"])


@router.post("/smoke")
def enqueue_wiring_smoke_job() -> dict:
    """
    Enqueue a wiring smoke job.

    A FE stand-in can use this to verify:
    FastAPI -> Celery enqueue -> Celery worker -> Redis/DB checks.
    """

    # Fail fast when Redis isn't reachable the same way redis-py would connect.
    try:
        redis.Redis.from_url(settings.redis_url).ping()
    except Exception as e:  # noqa: BLE001 - smoke-test diagnostics
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Redis broker not reachable (redis-py)",
                "message": str(e),
                "settings_redis_url": settings.redis_url,
                "hint": "Inside Docker use REDIS_URL=redis://redis:6379/0. On the host use redis://127.0.0.1:6379/0 and publish port 6379 in compose.",
            },
        )

    # Celery uses Kombu; verify that path too (avoids 'ping works but delay() refuses').
    broker_url = celery_app.conf.broker_url or settings.celery_broker_url()
    try:
        with celery_app.connection() as conn:
            conn.ensure_connection(max_retries=1)
    except Exception as e:  # noqa: BLE001 - smoke-test diagnostics
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Celery broker not reachable (Kombu)",
                "message": str(e),
                "broker_url_resolved": broker_url,
                "settings_redis_url": settings.redis_url,
                "hint": "If broker_url_resolved shows localhost while web runs in Docker, fix REDIS_URL. If uvicorn runs on the host, publish Redis 6379 and use redis://127.0.0.1:6379/0.",
            },
        )

    try:
        # Use the process-local `celery_app` explicitly. `task.delay()` can bind to a
        # different default app in edge import/reload cases, which then points at the
        # wrong broker (often localhost -> connection refused inside Docker).
        async_result = celery_app.send_task("app.workers.tasks.wiring_smoke_job")
        return {"job_id": async_result.id}
    except Exception as e:  # noqa: BLE001 - smoke-test diagnostics
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Failed to enqueue Celery job",
                "message": str(e),
                "broker_url_resolved": broker_url,
                "hint": "Ensure the Celery broker URL is reachable from the web process.",
            },
        )


@router.get("/smoke/{job_id}")
def get_wiring_smoke_job(job_id: str) -> dict:
    async_result = AsyncResult(job_id, app=celery_app)
    payload: dict = {"job_id": job_id, "state": async_result.state}

    if async_result.ready():
        payload["result"] = async_result.result
    elif async_result.failed():
        payload["error"] = str(async_result.result)

    return payload

