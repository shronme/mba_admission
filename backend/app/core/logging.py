import contextvars
import logging
import os
import sys
import uuid
from typing import Optional, Tuple, TypeVar

from app.core.config import settings

_T = TypeVar("_T")

# Per-request log context (safe for async via contextvars).
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="-"
)


def set_log_context(
    *,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Tuple[contextvars.Token[str], contextvars.Token[str]]:
    """
    Set per-request log context and return tokens for later reset.
    """

    rid = (request_id or "").strip() or str(uuid.uuid4())
    cid = (correlation_id or "").strip() or "-"
    t1 = _request_id_var.set(rid)
    t2 = _correlation_id_var.set(cid)
    return t1, t2


def reset_log_context(tokens: Tuple[contextvars.Token[str], contextvars.Token[str]]) -> None:
    t1, t2 = tokens
    _request_id_var.reset(t1)
    _correlation_id_var.reset(t2)


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # These are referenced by our formatter.
        if not hasattr(record, "request_id") or getattr(record, "request_id") in (None, ""):
            record.request_id = _request_id_var.get()
        if not hasattr(record, "correlation_id") or getattr(record, "correlation_id") in (None, ""):
            record.correlation_id = _correlation_id_var.get()
        return True


def configure_logging() -> None:
    """
    Logger setup that works well for container platforms (Railway).

    - Always logs to stdout/stderr via StreamHandler.
    - Adds `request_id` and `correlation_id` to all `app.*` logs.
    - Safe in both `web` and `worker` processes.
    """

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    if "pytest" in sys.modules:
        log_level = logging.INFO

    # Ensure our app logs consistently include our context fields, regardless of how
    # uvicorn/celery configure global logging.
    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_level)
    # Allow propagation so test suites (caplog) can capture `app.*` records.
    # Note: this may duplicate logs in some environments, but keeps observability tests stable.
    app_logger.propagate = True

    # Avoid duplicate handlers on reload/re-import.
    app_logger.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(log_level)
    handler.addFilter(_ContextFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s correlation_id=%(correlation_id)s %(message)s",
        )
    )
    app_logger.addHandler(handler)

    # Also set root level so libraries (e.g. SQLAlchemy) still emit something.
    logging.getLogger().setLevel(log_level)

    # Ensure nested app.* loggers bubble up (pytest caplog expects propagation).
    for name, obj in logging.root.manager.loggerDict.items():
        if not isinstance(name, str):
            continue
        if name == "app" or name.startswith("app."):
            try:
                logging.getLogger(name).propagate = True
            except Exception:
                continue

