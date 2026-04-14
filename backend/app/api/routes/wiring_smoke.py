import logging
from fastapi import APIRouter, HTTPException

from app.core.db import async_select_one
router = APIRouter(prefix="/wiring", tags=["wiring"])
logger = logging.getLogger(__name__)


@router.post("/smoke")
async def run_wiring_smoke() -> dict:
    """
    In-process wiring check (Celery removed):
    - Postgres `SELECT 1`
    """

    try:
        select_one = await async_select_one()
    except Exception as e:  # noqa: BLE001 - smoke-test diagnostics
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Database not reachable",
                "message": str(e),
            },
        )

    return {"db_connected": True, "select_one": select_one}


@router.get("/smoke/{job_id}")
def get_wiring_smoke_job(job_id: str) -> dict:
    raise HTTPException(status_code=410, detail="Celery wiring smoke polling removed.")

