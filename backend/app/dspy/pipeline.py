from __future__ import annotations

import json
import os
from typing import Any

from app.core.dspy_runtime import run_dspy_module
from app.dspy.answer_relevance_classifier import (
    MockAnswerRelevanceClassifier,
    OpenAIAnswerRelevanceClassifier,
)
from app.dspy.intake_interviewer import MockIntakeInterviewer, OpenAIIntakeInterviewer
from app.dspy.response_generator import AdmissionsResponseGenerator
from app.dspy.openai_response_generator import OpenAIResponseGenerator
from app.schemas.intent_routing import (
    IntentRoutingOutput,
    PrimaryIntent,
    SecondaryFlag,
)

_DISALLOWED_FULL_ESSAY_PHRASES = (
    "write my personal statement",
    "write the essay",
    "write an essay",
    "draft a full essay",
    "complete the essay",
)

_OFF_TOPIC_KEYWORDS = ("calculus", "photosynthesis", "quantum", "chemistry")


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
        f"{m.get('role', '?').upper()}: {m.get('content', '')}"[:500] for m in recent_messages
    )[:4000]

    return (
        "Candidate profile:\n"
        f"- name: {candidate_name or 'unknown'}\n"
        f"- attributes: {json.dumps(attrs, ensure_ascii=False)[:2000]}\n\n"
        f"Documents extracted snippets:\n{docs_joined or '(none)'}\n\n"
        f"Recent conversation:\n{history or '(none)'}\n"
    )


def _build_conversation_history(recent_messages: list[dict[str, Any]]) -> str:
    """Format recent messages as INTERVIEWER / CANDIDATE lines for the intake modules."""
    lines = []
    for m in recent_messages:
        role = (m.get("role") or "").lower()
        label = "INTERVIEWER" if role == "assistant" else "CANDIDATE"
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _last_assistant_message(recent_messages: list[dict[str, Any]]) -> str:
    """Return the content of the most recent assistant message, or empty string."""
    for m in reversed(recent_messages):
        if (m.get("role") or "").lower() == "assistant" and m.get("content"):
            return m["content"]
    return ""


def generate_assistant_response(
    *,
    user_message: str,
    file_count: int,
    candidate_profile: dict[str, Any] | None,
    docs_snippets: list[str],
    recent_messages: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """
    DSPy pipeline: Intent Classification → Answer Relevance → Intake Interview.

    Returns a tuple of (response_text, profile_updates).
    profile_updates is a dict of new key/value pairs to merge into CandidateProfile.attributes.
    """

    use_openai = (
        (os.getenv("DSPY_MODE") or "mock").lower() == "openai"
        and bool(os.getenv("OPENAI_API_KEY"))
    )

    user_lower = (user_message or "").lower()

    # --- Guardrails (unchanged) ---
    disallowed_full_essay = any(phrase in user_lower for phrase in _DISALLOWED_FULL_ESSAY_PHRASES)
    off_topic = any(kw in user_lower for kw in _OFF_TOPIC_KEYWORDS)

    if disallowed_full_essay:
        return (
            "I can help you brainstorm, outline, and improve your draft, but I can't write a full essay for you. "
            "Paste the prompt and share a few bullet points from your own story, and I'll help shape a strong outline.",
            {},
        )

    if off_topic:
        return (
            "I can only help with graduate admissions (documents, goals, school strategy, and essay planning). "
            "Tell me what program/cycle you're targeting and what documents you have.",
            {},
        )

    # --- Routing ---
    secondary_flags: list[SecondaryFlag] = []
    has_files = file_count > 0
    if not has_files:
        secondary_flags.append(SecondaryFlag.NO_FILES)

    routing = IntentRoutingOutput(
        primary_intent=PrimaryIntent.INTAKE_INTERVIEW,
        secondary_flags=secondary_flags,
        confidence=0.95,
        reasoning="Always route to intake interview.",
        recommended_agent="intake_interview_agent",
        requires_clarification=False,
    )

    # --- Context ---
    candidate_name = candidate_profile.get("full_name") if candidate_profile else None
    candidate_attributes: dict[str, Any] = (
        (candidate_profile.get("attributes") or {}) if candidate_profile else {}
    )
    current_profile_json = json.dumps(candidate_attributes, ensure_ascii=False)
    conversation_history = _build_conversation_history(recent_messages)

    # --- Answer Relevance Classification ---
    # Skip on the very first turn (no prior assistant message exists yet).
    last_question = _last_assistant_message(recent_messages)
    answer_classification = "relevant"

    if last_question:
        relevance_classifier = (
            OpenAIAnswerRelevanceClassifier() if use_openai else MockAnswerRelevanceClassifier()
        )
        rel_pred = run_dspy_module(
            relevance_classifier,
            last_question_asked=last_question,
            user_message=user_message,
        )
        answer_classification = str(getattr(rel_pred, "classification", "relevant"))

        if answer_classification == "irrelevant":
            # Short-circuit: alert and re-ask the same question
            alert = (
                f"It looks like that didn't quite address what I asked. Let me re-ask:\n\n"
                f"{last_question}"
            )
            if not has_files:
                from app.dspy.intake_interviewer import _NO_FILES_NUDGE
                alert += _NO_FILES_NUDGE
            return alert, {}

    # --- Intake Interview Response Generation ---
    interviewer = OpenAIIntakeInterviewer() if use_openai else MockIntakeInterviewer()
    out = run_dspy_module(
        interviewer,
        candidate_name=candidate_name or "Candidate",
        last_question_asked=last_question,
        current_profile_json=current_profile_json,
        conversation_history=conversation_history,
        user_message=user_message,
        has_files=has_files,
        answer_classification=answer_classification,
    )

    response_text = str(getattr(out, "response", ""))

    # Parse profile updates — skip extraction when candidate was asking a question
    profile_updates: dict[str, Any] = {}
    if answer_classification != "candidate_question":
        raw_updates = str(getattr(out, "profile_updates_json", "") or "")
        try:
            parsed = json.loads(raw_updates)
            if isinstance(parsed, dict):
                profile_updates = parsed
        except (json.JSONDecodeError, ValueError):
            pass

    return response_text, profile_updates


def generate_initial_greeting(
    *,
    candidate_name: str | None = None,
    existing_attributes: dict[str, Any] | None = None,
    has_files: bool = False,
) -> tuple[str, dict[str, Any]]:
    """
    Generate the opening message when a new thread is created.

    Reads existing profile attributes so returning candidates are not re-asked
    questions they have already answered. Picks the first unanswered question
    from the interview bank; if all are answered, invites the candidate to elaborate.
    """
    from app.dspy.intake_interviewer import INTERVIEW_QUESTIONS, _NO_FILES_NUDGE

    attrs = existing_attributes or {}
    name_part = f" {candidate_name}" if candidate_name else ""

    # Find the first question whose profile key is not yet populated.
    next_question: str | None = None
    for key, question in INTERVIEW_QUESTIONS:
        if key not in attrs:
            next_question = question
            break

    if next_question is None:
        # All areas covered — invite elaboration.
        next_question = (
            "We've already covered a lot of ground together. "
            "Is there anything you'd like to revisit, clarify, or add before we move on to strategy?"
        )

    # Tailor the preamble based on whether this is a fresh start or a return visit.
    answered_count = sum(1 for key, _ in INTERVIEW_QUESTIONS if key in attrs)
    if answered_count == 0:
        preamble = (
            f"Hi{name_part}! I'm your MBA admissions coach. "
            "I'll be asking you a series of questions to understand your background, goals, and motivations — "
            "this will help us build a strong, personalised application strategy together.\n\n"
        )
    else:
        covered = ", ".join(
            key.replace("_", " ")
            for key, _ in INTERVIEW_QUESTIONS
            if key in attrs
        )
        preamble = (
            f"Welcome back{name_part}! We've already covered: {covered}. "
            "Let's pick up where we left off.\n\n"
        )

    greeting = preamble + next_question

    if not has_files:
        greeting += _NO_FILES_NUDGE

    return greeting, {}
