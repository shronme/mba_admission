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


def openai_calls_enabled() -> bool:
    """
    Return True when the app should attempt OpenAI-backed DSPy modules.

    Historical footgun:
    - Many call sites used `(DSPY_MODE or "mock") == "openai"` as a guard.
    - In deployments where OPENAI_API_KEY is set but DSPY_MODE is unset, this
      silently forced mock mode and made quality scores look "much lower" than
      expected.

    Rule:
    - If DSPY_MODE is explicitly "mock" → never call OpenAI.
    - Otherwise, if OPENAI_API_KEY is present → allow OpenAI calls.
    """

    mode = (os.getenv("DSPY_MODE") or "").strip().lower()
    if mode == "mock":
        return False
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def configure_dspy_from_env() -> None:
    """
    Configure DSPy from environment variables.

    Local/dev can run without an LLM by setting `DSPY_MODE=mock` (default).
    In that mode we do *not* configure a real LM; only deterministic modules
    (pure Python `dspy.Module.forward`) should be used.

    Env vars:
    - `DSPY_MODE`: `mock` (default), `perplexity` (skip bootstrap if LM already set; else same as
      env Perplexity below), or other non-mock values for OpenAI-style bootstrap
    - `DSPY_MODEL`: e.g. `openai/gpt-4o-mini` (defaults to `openai/gpt-4o-mini`)
    - `OPENAI_API_KEY`: required for real OpenAI calls
    - `PERPLEXITY_API_KEY`: required when `DSPY_MODEL` is a `perplexity/...` LiteLLM id
    """

    global _configured
    if _configured:
        return

    # If the API key is present, default to OpenAI unless the operator explicitly
    # forced mock mode (DSPY_MODE=mock). This matches expected production behavior.
    mode = (os.getenv("DSPY_MODE") or ("openai" if (os.getenv("OPENAI_API_KEY") or "").strip() else "mock")).lower()
    model = os.getenv("DSPY_MODEL") or "openai/gpt-4o-mini"
    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    perplexity_key = (
        (os.getenv("PERPLEXITY_API_KEY") or os.getenv("PERPLEXITYAI_API_KEY") or "")
        .strip()
    )

    if mode == "mock":
        logger.info("DSPy not configured for real LLM calls (DSPY_MODE=mock).")
        _configured = True
        return

    # Batch tools (e.g. research_program_dossiers) call `dspy.configure(lm=...)` before this;
    # do not replace that LM with OPENAI_API_KEY when the shell still has DSPY_MODE=openai.
    if mode == "perplexity" and dspy.settings.lm is not None:
        logger.info(
            "DSPy env bootstrap skipped (DSPY_MODE=perplexity; LM already configured)."
        )
        _configured = True
        return

    if model.startswith("perplexity/"):
        if not perplexity_key:
            logger.info(
                "DSPy not configured (DSPY_MODEL=%s but PERPLEXITY_API_KEY is unset).",
                model,
            )
            _configured = True
            return
        # Perplexity's OpenAI-compatible API does not accept some newer OpenAI parameters
        # (notably structured `response_format`) that DSPy/LiteLLM may include. Ask LiteLLM
        # to drop unsupported params instead of failing the request.
        try:
            import litellm  # type: ignore[import-not-found]

            if hasattr(litellm, "drop_params"):
                litellm.drop_params = True
        except Exception:  # noqa: BLE001 - best-effort compatibility
            pass
        base = (os.getenv("PERPLEXITY_BASE_URL") or os.getenv("PERPLEXITY_API_BASE") or "").strip()
        try:
            lm = (
                dspy.LM(model, api_key=perplexity_key, api_base=base)
                if base
                else dspy.LM(model, api_key=perplexity_key)
            )
        except TypeError:
            lm = (
                dspy.LM(model, api_key=perplexity_key, base_url=base)
                if base
                else dspy.LM(model, api_key=perplexity_key)
            )
        dspy.configure(lm=lm)
        logger.info("DSPy configured with model=%s (Perplexity)", model)
        _configured = True
        return

    if not openai_key:
        logger.info(
            "DSPy not configured for real LLM calls (DSPY_MODE=%s, OPENAI_API_KEY set=%s).",
            mode,
            bool(openai_key),
        )
        _configured = True
        return

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

