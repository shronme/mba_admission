from __future__ import annotations

import json
import os
from typing import Any

from app.core.dspy_runtime import run_dspy_module
from app.dspy.response_generator import AdmissionsResponseGenerator
from app.dspy.openai_intent_classifier import OpenAIIntentClassifier
from app.dspy.openai_response_generator import OpenAIResponseGenerator
from app.dspy.static_intent_classifier import StaticIntentClassifier
from app.schemas.intent_routing import (
    IntentRoutingOutput,
    PrimaryIntent,
    SecondaryFlag,
)


def _primary_from_raw(raw_intent: str) -> PrimaryIntent:
    ri = (raw_intent or "").strip().lower()
    if "intake_documents" in ri:
        return PrimaryIntent.INTAKE_DOCS
    if "intake_goals" in ri:
        return PrimaryIntent.INTAKE_GOALS
    if "admissions_general_help" in ri:
        return PrimaryIntent.ADMISSIONS_HELP
    if "admissions_essay_planning" in ri:
        return PrimaryIntent.ADMISSIONS_HELP
    if "off_topic" in ri:
        return PrimaryIntent.OFF_TOPIC
    return PrimaryIntent.ADMISSIONS_HELP


def _build_memory_context(
    *,
    candidate_name: str | None,
    candidate_attributes: dict[str, Any] | None,
    docs_snippets: list[str],
    recent_messages: list[dict[str, Any]],
) -> str:
    attrs = candidate_attributes or {}
    docs_joined = "\n\n".join(snippet[:2000] for snippet in docs_snippets if snippet)[:8000]
    history = "\n".join(
        f"{m.get('role','?').upper()}: {m.get('content','')}"[:500] for m in recent_messages
    )[:4000]

    return (
        "Candidate profile:\n"
        f"- name: {candidate_name or 'unknown'}\n"
        f"- attributes: {json.dumps(attrs, ensure_ascii=False)[:2000]}\n\n"
        f"Documents extracted snippets:\n{docs_joined or '(none)'}\n\n"
        f"Recent conversation:\n{history or '(none)'}\n"
    )


def generate_assistant_response(
    *,
    user_message: str,
    file_count: int,
    candidate_profile: dict[str, Any] | None,
    docs_snippets: list[str],
    recent_messages: list[dict[str, Any]],
) -> str:
    """
    DSPy pipeline (MVP): Intent Classification → Response Generation.

    For now the modules are deterministic (no real LLM calls), but the
    structure matches the intended tool-routing pipeline.
    """

    use_openai = (
        (os.getenv("DSPY_MODE") or "mock").lower() == "openai"
        and bool(os.getenv("OPENAI_API_KEY"))
    )

    # 1) Intent Classification (DSPy module)
    classifier = OpenAIIntentClassifier() if use_openai else StaticIntentClassifier()
    pred = run_dspy_module(classifier, message=user_message)
    raw_intent = str(getattr(pred, "intent", "admissions_general_help"))

    primary_intent = _primary_from_raw(raw_intent)
    secondary_flags: list[SecondaryFlag] = []

    user_lower = (user_message or "").lower()
    disallowed_full_essay = any(
        kw in user_lower
        for kw in (
            "write my personal statement",
            "write the essay",
            "write an essay",
            "draft a full essay",
            "complete the essay",
        )
    )
    if disallowed_full_essay:
        secondary_flags.append(SecondaryFlag.DISALLOWED_FULL_ESSAY)

    if file_count <= 0:
        secondary_flags.append(SecondaryFlag.NEEDS_DOC_UPLOAD)
        primary_intent = PrimaryIntent.INTAKE_DOCS
    elif primary_intent == PrimaryIntent.INTAKE_DOCS:
        secondary_flags.append(SecondaryFlag.NEEDS_GOALS_CLARIFICATION)
        primary_intent = PrimaryIntent.INTAKE_GOALS

    requires_clarification = primary_intent == PrimaryIntent.INTAKE_GOALS and not any(
        kw in user_lower for kw in ("round", "timeline", "deadline", "program", "school")
    )

    routing = IntentRoutingOutput(
        primary_intent=primary_intent,
        secondary_flags=list({f for f in secondary_flags}),
        confidence=0.85,
        reasoning=str(getattr(pred, "reasoning", ""))[:1000],
        recommended_agent="admissions_intake_agent",
        requires_clarification=requires_clarification,
    )

    # 2) Memory / context injection (string assembly for now)
    memory_context = _build_memory_context(
        candidate_name=candidate_profile.get("full_name") if candidate_profile else None,
        candidate_attributes=candidate_profile.get("attributes") if candidate_profile else None,
        docs_snippets=docs_snippets,
        recent_messages=recent_messages,
    )

    # 3) Response Generation (DSPy module)
    responder = OpenAIResponseGenerator() if use_openai else AdmissionsResponseGenerator()
    out = run_dspy_module(
        responder,
        primary_intent=routing.primary_intent.value,
        secondary_flags=[f.value for f in routing.secondary_flags],
        requires_clarification=routing.requires_clarification,
        user_message=user_message,
        memory_context=memory_context,
    )
    return str(getattr(out, "final_answer", ""))

