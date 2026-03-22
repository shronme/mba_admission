import logging
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import StreamingResponse
import time
from typing import Callable, Awaitable
from starlette.staticfiles import StaticFiles

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.candidates_enter import router as candidates_enter_router
from app.api.routes.files import router as files_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.chat import router as chat_router
from app.api.routes.wiring_smoke import router as wiring_smoke_router
from app.core.config import settings
from app.core.logging import configure_logging, reset_log_context, set_log_context
from app.core.phoenix import configure_phoenix_tracing

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    # Initialize Phoenix tracing before any LLM/DSPy clients are constructed.
    configure_phoenix_tracing()
    app = FastAPI(title="AI Admissions API", version="0.1.0")

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable[[Request], Awaitable]):  # type: ignore[valid-type]
        """
        Emit request lifecycle logs with request_id/correlation_id.

        Note: for streaming responses, the request may finish before the full body is
        generated; chat streaming logs also cover token generation errors.
        """

        # Prefer an explicit correlation id, but fall back to request id.
        raw_cid = request.headers.get("X-Correlation-ID") or request.headers.get("x-correlation-id")
        raw_rid = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")

        request_id = (raw_rid or "").strip() or str(uuid.uuid4())
        correlation_id = (raw_cid or "").strip() or request_id
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        tokens = set_log_context(
            request_id=request_id,
            correlation_id=correlation_id,
        )
        started = time.perf_counter()
        reset_needed = True
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - started) * 1000.0
            logger.info(
                "request_complete method=%s path=%s status_code=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

            # For streaming responses, reset context only after the stream finishes
            # so that generator logs still include request_id/correlation_id.
            if isinstance(response, StreamingResponse):
                original_iterator = response.body_iterator

                async def wrapped_iterator():
                    try:
                        async for chunk in original_iterator:
                            yield chunk
                    finally:
                        reset_log_context(tokens)

                response = StreamingResponse(
                    wrapped_iterator(),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                    background=response.background,
                )
                reset_needed = False
            return response
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000.0
            logger.exception(
                "request_exception method=%s path=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        finally:
            if reset_needed:
                reset_log_context(tokens)

    logger.info("web_app_start env=%s", settings.env)

    # Always enable CORS for browser clients (origins never empty after settings fallback).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(candidates_enter_router)
    app.include_router(files_router)
    app.include_router(jobs_router)
    app.include_router(chat_router)
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

