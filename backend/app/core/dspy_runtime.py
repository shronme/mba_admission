from __future__ import annotations

import logging
import os
import time
from typing import Any

import dspy
from opentelemetry import trace  # type: ignore[import-not-found]
from opentelemetry.trace import Status, StatusCode  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

_configured = False


def configure_dspy_from_env() -> None:
    """
    Configure DSPy from environment variables.

    Local/dev can run without an LLM by setting `DSPY_MODE=mock` (default).
    In that mode we do *not* configure a real LM; only deterministic modules
    (pure Python `dspy.Module.forward`) should be used.

    Env vars:
    - `DSPY_MODE`: `mock` (default) or `openai`/`anthropic` (anything else means "try real")
    - `DSPY_MODEL`: e.g. `openai/gpt-4o-mini` (defaults to `openai/gpt-4o-mini`)
    - `OPENAI_API_KEY`: required for real OpenAI calls
    """

    global _configured
    if _configured:
        return

    mode = (os.getenv("DSPY_MODE") or "mock").lower()
    model = os.getenv("DSPY_MODEL") or "openai/gpt-4o-mini"
    openai_key = os.getenv("OPENAI_API_KEY")

    if mode == "mock" or not openai_key:
        logger.info(
            "DSPy not configured for real LLM calls (DSPY_MODE=%s, OPENAI_API_KEY set=%s).",
            mode,
            bool(openai_key),
        )
        _configured = True
        return

    # For MVP we only support OpenAI via DSPy/LiteLLM right now.
    lm = dspy.LM(model, api_key=openai_key)
    dspy.configure(lm=lm)
    logger.info("DSPy configured with model=%s", model)
    _configured = True


def run_dspy_module(module: Any, **inputs: Any) -> Any:
    """
    Execute a DSPy module with basic structured logging.

    Returns the module's Prediction / output object.
    """

    configure_dspy_from_env()

    module_name = getattr(module, "name", None) or module.__class__.__name__
    start = time.perf_counter()
    with tracer.start_as_current_span(
        "dspy.module.exec",
        attributes={
            "openinference.span.kind": "CHAIN",
            "module.name": str(module_name),
            "model_id": os.getenv("DSPY_MODEL") or "unknown",
        },
    ) as span:
        try:
            out = module(**inputs)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            span.set_status(Status(StatusCode.OK))
            logger.info(
                "dspy_exec module=%s status=success elapsed_ms=%s model=%s",
                module_name,
                elapsed_ms,
                os.getenv("DSPY_MODEL") or "unknown",
            )
            return out
        except Exception as e:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            logger.exception(
                "dspy_exec module=%s status=failure elapsed_ms=%s model=%s",
                module_name,
                elapsed_ms,
                os.getenv("DSPY_MODEL") or "unknown",
            )
            raise

