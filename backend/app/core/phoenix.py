from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_configured = False


def configure_phoenix_tracing() -> None:
    """
    Configure Phoenix Cloud (OTEL) tracing if env vars are present.

    This is intentionally safe to call in all processes (web + worker).
    If Phoenix env vars are not set, tracing becomes a no-op.

    Env vars:
    - PHOENIX_COLLECTOR_ENDPOINT  e.g. https://app.phoenix.arize.com/s/<space>
    - PHOENIX_API_KEY             your Phoenix Cloud API key
    - PHOENIX_PROJECT_NAME        project name (default: mba_admissions)
    """

    global _configured
    if _configured:
        return

    collector = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").strip()
    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    project_name = os.getenv("PHOENIX_PROJECT_NAME", "mba_admissions").strip()

    if not collector:
        logger.info("Phoenix tracing not enabled (PHOENIX_COLLECTOR_ENDPOINT not set)")
        return

    logger.info(
        "Phoenix tracing starting (collector_set=%s, api_key_set=%s, project_name=%s)",
        bool(collector),
        bool(api_key),
        project_name,
    )

    try:
        from phoenix.otel import register  # type: ignore[import-not-found]

        # `register()` returns the Phoenix TracerProvider and sets it as the OTel global.
        # We keep the reference so we can bind instrumentors to the same provider.
        tracer_provider = register(
            auto_instrument=False,
            project_name=project_name,
        )

        # Explicitly bind OpenInference instrumentors to this provider so OpenAI /
        # LiteLLM / DSPy calls are traced against the correct exporter, not whatever
        # the current OTel global happens to be at instrument() time.
        try:
            from openinference.instrumentation.dspy import DSPyInstrumentor  # type: ignore[import-not-found]
            from openinference.instrumentation.litellm import LiteLLMInstrumentor  # type: ignore[import-not-found]
            from openinference.instrumentation.openai import OpenAIInstrumentor  # type: ignore[import-not-found]

            DSPyInstrumentor().instrument(tracer_provider=tracer_provider)
            LiteLLMInstrumentor().instrument(tracer_provider=tracer_provider)
            OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
            logger.info("Phoenix OpenInference instrumentors attached")
        except Exception as e:  # noqa: BLE001
            logger.exception("Phoenix OpenInference instrumentors failed: %s", e)

        logger.info(
            "Phoenix tracing enabled (collector=%s, api_key_set=%s)",
            collector,
            bool(api_key),
        )

        # Emit a startup span to confirm traces flow immediately on boot.
        try:
            from opentelemetry import trace  # type: ignore[import-not-found]
            from opentelemetry.trace import Status, StatusCode  # type: ignore[import-not-found]

            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("startup.phoenix.tracing") as span:
                span.set_attribute("openinference.span.kind", "CHAIN")
                span.set_attribute("phoenix.enabled", True)
                span.set_attribute("phoenix.project.name", project_name)
                span.set_status(Status(StatusCode.OK))
        except Exception:  # noqa: BLE001
            logger.exception("Phoenix startup span emission failed")

        _configured = True
    except Exception as e:  # noqa: BLE001
        logger.exception("Phoenix tracing configuration failed: %s", e)
