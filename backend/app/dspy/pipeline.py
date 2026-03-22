from __future__ import annotations

import json
import os
from typing import Any

from app.core.dspy_runtime import run_dspy_module
from app.dspy.answer_relevance_classifier import (
    MockAnswerRelevanceClassifier,
    OpenAIAnswerRelevanceClassifier,
)
from app.dspy.intake_interviewer import (
    MockIntakeInterviewer,
    OpenAIIntakeInterviewer,
    _extract_profile_updates as _heuristic_extract,
)
from app.dspy.profile_agent import (
    CANDIDATE_INPUT_ATTRIBUTES,
    _ATTRIBUTE_SCHEMA_JSON,
    get_profile_gaps,
    run_profile_agent,
)
from app.dspy.research_agent import MockResearchAgent, OpenAIResearchAgent

_DISALLOWED_FULL_ESSAY_PHRASES = (
    "write my personal statement",
    "write the essay",
    "write an essay",
    "draft a full essay",
    "complete the essay",
)

_OFF_TOPIC_KEYWORDS = ("calculus", "photosynthesis", "quantum", "chemistry")


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
    """Return the content of the most recent interviewer message, skipping file notifications."""
    for m in reversed(recent_messages):
        if (m.get("role") or "").lower() != "assistant":
            continue
        if not m.get("content"):
            continue
        # Skip automated file-notification messages — they are not interview questions
        # and must not be treated as the "last question asked".
        if (m.get("extra") or {}).get("type") == "file_notification":
            continue
        return m["content"]
    return ""


def generate_assistant_response(
    *,
    user_message: str,
    file_count: int,
    candidate_profile: dict[str, Any] | None,
    docs_snippets: list[str],
    recent_messages: list[dict[str, Any]],
    profile_complete: bool = False,
) -> tuple[str, dict[str, Any], bool, int]:
    """
    DSPy pipeline: route based on profile completeness, then generate a response.

    Returns a 4-tuple of:
      - response_text: str
      - profile_updates: dict  — new key/value pairs to merge into CandidateProfile.attributes
      - is_complete: bool      — whether the profile is complete after merging updates
      - completeness_score: int — 0-100 quality-aware score from ProfileAgent (stable, to be persisted)

    When profile_complete=True the ResearchAgent handles the response.
    When profile_complete=False the IntakeInterviewer conducts a gap-driven question.
    """

    use_openai = (
        (os.getenv("DSPY_MODE") or "mock").lower() == "openai"
        and bool(os.getenv("OPENAI_API_KEY"))
    )

    user_lower = (user_message or "").lower()

    # --- Guardrails ---
    if any(phrase in user_lower for phrase in _DISALLOWED_FULL_ESSAY_PHRASES):
        return (
            "I can help you brainstorm, outline, and improve your draft, but I can't write a full essay for you. "
            "Paste the prompt and share a few bullet points from your own story, and I'll help shape a strong outline.",
            {},
            profile_complete,
            -1,  # sentinel: no score update on guardrail short-circuit
        )

    if any(kw in user_lower for kw in _OFF_TOPIC_KEYWORDS):
        return (
            "I can only help with graduate admissions (documents, goals, school strategy, and essay planning). "
            "Tell me what programme/cycle you're targeting and what documents you have.",
            {},
            profile_complete,
            -1,
        )

    candidate_name = candidate_profile.get("full_name") if candidate_profile else None
    candidate_attributes: dict[str, Any] = (
        (candidate_profile.get("attributes") or {}) if candidate_profile else {}
    )

    # --- Route to ResearchAgent when the profile is already complete ---
    if profile_complete:
        research_agent = OpenAIResearchAgent() if use_openai else MockResearchAgent()
        research_out = run_dspy_module(
            research_agent,
            candidate_name=candidate_name or "Candidate",
            profile_attributes_json=json.dumps(candidate_attributes, ensure_ascii=False),
        )
        return str(getattr(research_out, "response", "")), {}, True, 100

    # --- Intake Interview flow ---
    has_files = file_count > 0
    conversation_history = _build_conversation_history(recent_messages)
    last_question = _last_assistant_message(recent_messages)
    current_profile_json = json.dumps(candidate_attributes, ensure_ascii=False)

    # Apply a fast heuristic extraction on the user's message so the score we
    # pass to the interviewer reflects the *current* answer, not the profile from
    # the previous turn. This removes the one-turn lag where the bot would say
    # "89%" right after an answer that clearly moves the needle.
    heuristic_updates = _heuristic_extract(user_message, candidate_attributes)
    projected_attributes = {**candidate_attributes, **heuristic_updates}

    # Run ProfileAgent on the projected (heuristically updated) profile to get
    # quality-aware gaps and a score that is close to what it will be after this
    # turn's full extraction. This is what the candidate sees as their progress
    # indicator, so it must reflect content quality — not just key presence.
    _, current_gaps, _, current_score = run_profile_agent(
        projected_attributes, use_openai=use_openai
    )
    profile_gaps_json = json.dumps(current_gaps, ensure_ascii=False)

    # --- Answer Relevance Classification ---
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

    # --- Generate intake response ---
    interviewer = OpenAIIntakeInterviewer() if use_openai else MockIntakeInterviewer()
    out = run_dspy_module(
        interviewer,
        candidate_name=candidate_name or "Candidate",
        last_question_asked=last_question,
        current_profile_json=current_profile_json,
        profile_gaps_json=profile_gaps_json,
        attribute_schema_json=_ATTRIBUTE_SCHEMA_JSON,
        completeness_score=current_score,
        conversation_history=conversation_history,
        user_message=user_message,
        has_files=has_files,
        answer_classification=answer_classification,
    )

    response_text = str(getattr(out, "response", ""))

    # Parse profile updates (skip when candidate was asking a question)
    profile_updates: dict[str, Any] = {}
    if answer_classification != "candidate_question":
        raw_updates = str(getattr(out, "profile_updates_json", "") or "")
        try:
            parsed = json.loads(raw_updates)
            if isinstance(parsed, dict):
                profile_updates = parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # Determine completeness on the merged profile so the caller can persist the flag.
    merged_attributes = {**candidate_attributes, **profile_updates}
    is_complete, _, synthesized, post_update_score = run_profile_agent(merged_attributes, use_openai=use_openai)

    # Merge synthesized derived attributes into the updates so they get persisted.
    if synthesized:
        profile_updates = {**profile_updates, **synthesized}

    return response_text, profile_updates, is_complete, post_update_score


def generate_initial_greeting(
    *,
    candidate_name: str | None = None,
    existing_attributes: dict[str, Any] | None = None,
    has_files: bool = False,
    profile_complete: bool = False,
) -> tuple[str, dict[str, Any]]:
    """
    Generate the opening message when a new thread is created.

    If the profile is already complete, returns the ResearchAgent handover message.
    Otherwise returns a personalised greeting that picks up from the first uncovered gap.
    """
    from app.dspy.intake_interviewer import _NO_FILES_NUDGE

    attrs = existing_attributes or {}
    name_part = f" {candidate_name}" if candidate_name else ""

    if profile_complete:
        use_openai = (
            (os.getenv("DSPY_MODE") or "mock").lower() == "openai"
            and bool(os.getenv("OPENAI_API_KEY"))
        )
        research_agent = OpenAIResearchAgent() if use_openai else MockResearchAgent()
        out = run_dspy_module(
            research_agent,
            candidate_name=candidate_name or "Candidate",
            profile_attributes_json=json.dumps(attrs, ensure_ascii=False),
        )
        return str(getattr(out, "response", "")), {}

    gaps = get_profile_gaps(attrs)
    first_gap = gaps[0] if gaps else None

    answered_count = len(CANDIDATE_INPUT_ATTRIBUTES) - len(gaps)

    if answered_count == 0:
        preamble = (
            f"Hi{name_part}! I'm your MBA admissions coach. "
            "I'll ask you a series of questions to understand your background, goals, and motivations — "
            "this will help us build a strong, personalised application strategy together.\n\n"
        )
    else:
        covered = ", ".join(k.replace("_", " ") for k in CANDIDATE_INPUT_ATTRIBUTES if k in attrs)
        preamble = (
            f"Welcome back{name_part}! We've already covered: {covered}. "
            "Let's pick up where we left off.\n\n"
        )

    if first_gap:
        from app.dspy.profile_agent import PROFILE_ATTRIBUTE_SCHEMA
        schema_desc = PROFILE_ATTRIBUTE_SCHEMA.get(first_gap, "").split(".")[0]
        next_question = (
            f"To get started, can you tell me about your "
            f"{first_gap.replace('_', ' ')}? {schema_desc}."
        )
    else:
        next_question = (
            "We've already covered a lot of ground together. "
            "Is there anything you'd like to revisit, clarify, or add before we move on to strategy?"
        )

    greeting = preamble + next_question

    if not has_files:
        greeting += _NO_FILES_NUDGE

    return greeting, {}
