import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.wiring_smoke import router as wiring_smoke_router
from app.core.config import settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="AI Admissions API", version="0.1.0")

    # Always enable CORS for browser clients (origins never empty after settings fallback).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(wiring_smoke_router)

    # Minimal static “mock FE” (same origin as API — no CORS).
    mock_fe_dir = Path(__file__).resolve().parent.parent / "static" / "mock_fe"
    if mock_fe_dir.is_dir():
        app.mount(
            "/fe",
            StaticFiles(directory=str(mock_fe_dir), html=True),
            name="mock_fe",
        )

    return app


app = create_app()

