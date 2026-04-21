from __future__ import annotations

import json
import os
from typing import Any

import dspy
import logging

from app.core.dspy_runtime import run_dspy_module
from app.core.dspy_runtime import configure_dspy_from_env
from app.db.enums import ProgramType
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
    "write my essay",
    "write the essay",
    "write an essay",
    "draft a full essay",
    "complete the essay",
)

_OFF_TOPIC_KEYWORDS = ("calculus", "photosynthesis", "quantum", "chemistry")

# Attributes that are populated by CV/document extraction. Their presence signals
# that at least one document has been fully processed — used for phase detection.
_DOC_DERIVED_ATTRS = frozenset({"domain_base", "core_identity", "core_strengths", "transferable_assets"})

logger = logging.getLogger(__name__)

_DEGREE_TOKENS = {
    "ms": "MS",
    "mba": "MBA",
    "phd": "PhD",
    "jd": "JD",
    "md": "MD",
    "llm": "LLM",
    "mpp": "MPP",
    "mpa": "MPA",
    "mph": "MPH",
    "msw": "MSW",
    "mfa": "MFA",
    "meng": "MEng",
    "dnp": "DNP",
    "med": "MEd",
}


def _normalize_program_type(program_type: ProgramType | str | None) -> ProgramType:
    if program_type is None:
        return ProgramType.GRAD
    if isinstance(program_type, ProgramType):
        return program_type
    try:
        return ProgramType(str(program_type).lower())
    except ValueError:
        return ProgramType.GRAD


def _coach_title(program_type: ProgramType | str | None) -> str:
    p = _normalize_program_type(program_type)
    if p == ProgramType.MBA:
        return "MBA admissions coach"
    if p == ProgramType.PHD:
        return "PhD admissions coach"
    if p == ProgramType.UNDERGRAD:
        return "undergraduate admissions coach"
    if p == ProgramType.GRAD:
        return "graduate admissions coach"
    return "graduate and professional school admissions coach"


def _life_story_degree_clause(program_type: ProgramType | str | None) -> str:
    p = _normalize_program_type(program_type)
    if p == ProgramType.MBA:
        return "why an MBA makes sense for you right now"
    if p == ProgramType.PHD:
        return "why this doctoral path makes sense for you right now"
    if p == ProgramType.UNDERGRAD:
        return "what you're looking for from your undergraduate path right now"
    if p == ProgramType.GRAD:
        return "why this graduate program direction makes sense for you right now"
    return "why this next academic or professional step makes sense for you right now"


def _format_grad_focus_slug(slug: str) -> str:
    parts = [p for p in slug.strip().split("_") if p]
    if not parts:
        return slug
    out: list[str] = []
    for part in parts:
        low = part.lower()
        out.append(_DEGREE_TOKENS.get(low, part.capitalize()))
    return " ".join(out)


def _compute_intake_phase(file_count: int, attributes: dict[str, Any]) -> str:
    """
    Determine the current intake phase from observable state.

    "intro"       — no documents uploaded yet; focus on requesting CV + life story.
    "bridge"      — documents uploaded but not yet processed (or being processed);
                    ask the candidate about their target programs while extraction runs.
    "gap_filling" — documents have been processed (doc-derived attributes present) OR the
                    candidate has already answered the target_programs bridge question;
                    conduct gap-targeted interview questions.
    """
    if file_count == 0:
        return "intro"
    has_doc_content = any(attributes.get(k) for k in _DOC_DERIVED_ATTRS)
    target_programs_filled = bool(attributes.get("target_programs")) or bool(
        attributes.get("target_schools")
    )
    if has_doc_content or target_programs_filled:
        return "gap_filling"
    return "bridge"


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
        # Skip automated system messages — they are not interview questions
        # and must not be treated as the "last question asked".
        msg_type = (m.get("extra") or {}).get("type")
        if msg_type in ("file_notification", "extraction_summary"):
            continue
        return m["content"]
    return ""


async def generate_assistant_response(
    *,
    user_message: str,
    file_count: int,
    candidate_profile: dict[str, Any] | None,
    docs_snippets: list[str],
    recent_messages: list[dict[str, Any]],
    profile_complete: bool = False,
    current_completeness_score: int = 0,
    thread_stage: str | None = None,
    selected_schools: list[dict[str, Any]] | None = None,
    admission_evaluation_result: dict[str, Any] | None = None,
    session: Any | None = None,
    candidate_id: Any | None = None,
    openai_client: Any | None = None,
    available_documents: list[dict[str, Any]] | None = None,
) -> Any:
    """
    DSPy pipeline: route based on profile completeness, then generate a response.

    Returns a 4-tuple of:
      - response_text: str
      - profile_updates: dict  — new key/value pairs to merge into CandidateProfile.attributes
      - is_complete: bool      — whether the profile is complete after merging updates
      - completeness_score: int — 0-100 quality-aware score from ProfileAgent (stable, to be persisted)

    When profile_complete=True the ResearchAgent handles the response.
    When profile_complete=False the IntakeInterviewer conducts a phase-aware interview.
    """

    from app.core.dspy_runtime import openai_calls_enabled

    # The advisor stage uses `await module.aforward(...)` directly (not `run_dspy_module`),
    # so ensure DSPy has an LM configured before any DSPy Predict is invoked.
    configure_dspy_from_env()

    use_openai = openai_calls_enabled()

    user_lower = (user_message or "").lower()

    # --- Guardrails ---
    if (thread_stage or "").lower() != "advisor" and any(
        phrase in user_lower for phrase in _DISALLOWED_FULL_ESSAY_PHRASES
    ):
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

    # --- Route to advisor agent when thread is advisor stage ---
    if (thread_stage or "").lower() == "advisor":
        from app.dspy.agent_advisor import AgentAdvisorModule, MockAgentAdvisorModule
        from app.dspy.agent_tools import build_agent_tools

        if session is None or candidate_id is None or openai_client is None:
            raise ValueError(
                "advisor stage requires session, candidate_id, and openai_client"
            )

        retrieve_fn, save_fn = build_agent_tools(session, candidate_id, openai_client)
        dspy_mode = (os.getenv("DSPY_MODE") or "").lower()
        module = (
            MockAgentAdvisorModule()
            if dspy_mode == "mock"
            else AgentAdvisorModule(retrieve_fn, save_fn)
        )

        # Format conversation history as ASSISTANT/USER lines (newest last).
        lines = []
        for m in recent_messages:
            role = (m.get("role") or "").lower()
            label = "ASSISTANT" if role == "assistant" else "USER"
            content = (m.get("content") or "").strip()
            if content:
                lines.append(f"{label}: {content}")
        history = "\n".join(lines)

        # Pre-format doc snippets so the agent can usually answer without any
        # retrieval tool call (the snippets were already fetched via pgvector
        # in the chat route using `user_message` as the query).
        if docs_snippets:
            preloaded_snippets_text = "\n\n".join(
                f"[{i + 1}] {snippet}" for i, snippet in enumerate(docs_snippets)
            )
        else:
            preloaded_snippets_text = "No snippets pre-loaded."

        pred: dspy.Prediction = await module.aforward(
            profile_attributes_json=json.dumps(candidate_attributes, ensure_ascii=False),
            selected_schools_json=json.dumps(selected_schools or [], ensure_ascii=False),
            available_documents_json=json.dumps(
                available_documents or [], ensure_ascii=False
            ),
            preloaded_document_snippets=preloaded_snippets_text,
            conversation_history=history,
            user_message=user_message,
        )
        traj = getattr(pred, "trajectory", None)
        try:
            traj_len = len(traj) if traj is not None else 0
        except Exception:
            traj_len = 0
        logger.info(
            "advisor_react_complete candidate_id=%s trajectory_len=%s",
            str(candidate_id),
            traj_len,
        )
        return pred

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
    intake_phase = _compute_intake_phase(file_count, candidate_attributes)
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
        projected_attributes, use_openai=use_openai, min_score=current_completeness_score
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
        intake_phase=intake_phase,
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
    is_complete, _, synthesized, post_update_score = run_profile_agent(
        merged_attributes, use_openai=use_openai, min_score=current_score
    )

    # Merge synthesized derived attributes into the updates so they get persisted.
    if synthesized:
        profile_updates = {**profile_updates, **synthesized}

    # If the profile just crossed the completion threshold this turn, override the
    # interviewer's response — which was generated before we knew extraction would
    # push the score to 100 — with a clean handoff so no further questions are asked.
    if is_complete and not profile_complete:
        response_text = (
            "That's exactly what I needed — your profile is now complete. "
            "I have a comprehensive picture of your background, strengths, and goals. "
            "Give me a moment to analyse the best school fit and application strategy for you."
        )

    return response_text, profile_updates, is_complete, post_update_score


def generate_initial_greeting(
    *,
    candidate_name: str | None = None,
    existing_attributes: dict[str, Any] | None = None,
    has_files: bool = False,
    profile_complete: bool = False,
    program_type: ProgramType | str | None = None,
    grad_program_focus: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Generate the opening message when a new thread is created.

    If the profile is already complete, returns the ResearchAgent handover message.
    Otherwise returns a greeting appropriate to the candidate's current state.
    """
    attrs = existing_attributes or {}
    name_part = f" {candidate_name}" if candidate_name else ""

    if profile_complete:
        from app.core.dspy_runtime import openai_calls_enabled

        use_openai = openai_calls_enabled()
        research_agent = OpenAIResearchAgent() if use_openai else MockResearchAgent()
        out = run_dspy_module(
            research_agent,
            candidate_name=candidate_name or "Candidate",
            profile_attributes_json=json.dumps(attrs, ensure_ascii=False),
        )
        return str(getattr(out, "response", "")), {}

    gaps = get_profile_gaps(attrs)
    answered_count = len(CANDIDATE_INPUT_ATTRIBUTES) - len(gaps)

    # Returning candidate — pick up where they left off
    if answered_count > 0 or has_files:
        covered = ", ".join(k.replace("_", " ") for k in CANDIDATE_INPUT_ATTRIBUTES if attrs.get(k))
        preamble = f"Welcome back{name_part}!"
        if covered:
            preamble += f" We've already covered: {covered}."
        preamble += " Let's pick up where we left off.\n\n"

        if has_files and not any(attrs.get(k) for k in _DOC_DERIVED_ATTRS):
            # Files uploaded but not yet processed
            greeting = (
                preamble
                + "I can see you've already uploaded some documents — I'm still reviewing them. "
                "While that finishes, have you thought about which programs or schools you're interested in?"
            )
        elif gaps:
            from app.dspy.profile_agent import PROFILE_ATTRIBUTE_SCHEMA
            first_gap = gaps[0]
            schema_desc = PROFILE_ATTRIBUTE_SCHEMA.get(first_gap, "").split(".")[0]
            greeting = (
                preamble
                + f"Let's continue with your {first_gap.replace('_', ' ')}. {schema_desc}."
            )
        else:
            greeting = (
                preamble
                + "We've already covered a lot of ground together. "
                "Is there anything you'd like to revisit or clarify before we move on to strategy?"
            )
        return greeting, {}

    # Fresh start — introduce the process and request documents
    coach = _coach_title(program_type)
    degree_clause = _life_story_degree_clause(program_type)
    focus_line = ""
    if grad_program_focus and grad_program_focus.strip():
        focus_line = (
            f"From your intake, you're focused on **{_format_grad_focus_slug(grad_program_focus.strip())}** "
            "— we'll keep that front and center.\n\n"
        )
    greeting = (
        f"Hi{name_part}! I'm your {coach}.\n\n"
        f"{focus_line}"
        "Here's how we'll work together: I'll help you build a complete, honest picture of your "
        "background and goals, then use that to craft an application strategy that's genuinely yours. "
        "The process has a few steps:\n\n"
        "1. You share your CV and a life story document\n"
        "2. I review them and extract the key information about your profile\n"
        "3. We fill in any remaining gaps through a focused conversation\n"
        "4. Together we map out your school list and application approach\n\n"
        "**To get started, please upload two things:**\n\n"
        "- **Your CV or résumé** — I'm looking for your career trajectory, the types of roles "
        "you've held, the scope of your responsibilities, and any patterns that reveal your "
        "professional identity.\n\n"
        "- **A life story document** — this can be a personal statement draft, a narrative bio, "
        "or even just a few paragraphs about what shaped you: your values, turning points, "
        f"key experiences, and {degree_clause}.\n\n"
        "You can upload them as PDF or Word documents. Take your time — I'll be here when you're ready."
    )
    return greeting, {}
