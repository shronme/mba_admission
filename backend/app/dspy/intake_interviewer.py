from __future__ import annotations

import json

import dspy

from app.dspy.profile_agent import (
    CANDIDATE_INPUT_ATTRIBUTES,
    _ATTRIBUTE_SCHEMA_JSON,
)

# Plain-English question prompts for the mock interviewer — kept separate from the
# attribute schema so we never splice a completeness definition into a question.
_MOCK_QUESTION_HINTS: dict[str, str] = {
    "core_identity": "how would you describe yourself as a professional — beyond your job title?",
    "domain_base": "what industry and functional area have you been working in, and how long?",
    "core_strengths": "what are two or three strengths you'd say colleagues consistently rely on you for?",
    "differentiation_layer": "is there a personal experience or value that shapes how you show up at work?",
    "intellectual_working_style": "how do you typically approach a complex or ambiguous problem?",
    "motivation": "what's driving you to pursue an MBA right now, specifically?",
    "core_tension": "where do you feel the biggest gap between where you are today and where you want to go?",
    "transferable_assets": "what skills or experiences from your background do you think translate most directly to your target direction?",
    "target_programs": "have you started thinking about which programs or schools you're interested in? Even a rough list helps — reach schools, safe bets, or program types you're drawn to.",
}

# Phase identifiers passed from the pipeline.
# "intro"       — no documents uploaded yet
# "bridge"      — documents uploaded, extraction in progress; ask about target schools
# "gap_filling" — documents processed (or target_programs answered); ask gap-targeted questions
INTAKE_PHASES = ("intro", "bridge", "gap_filling")


class OpenAIIntakeInterviewSignature(dspy.Signature):
    """
    You are an experienced MBA admissions coach conducting a structured intake interview.
    CRITICAL: You MUST always respond in English. Never switch to any other language,
    regardless of what language the candidate writes in. If the candidate writes in
    Hebrew or any other language, still reply entirely in English.

    Your behaviour is governed by `intake_phase`, which has three possible values:

    ─────────────────────────────────────────────────────────────────
    PHASE: intro  (no documents uploaded yet)
    ─────────────────────────────────────────────────────────────────
    The candidate has not yet uploaded their CV or life story.
    - If the candidate sends a message, respond warmly and briefly.
    - You may acknowledge what they said (e.g. if they share context verbally), but keep it short.
    - Always redirect them to upload their documents — this is the primary action needed.
    - Do NOT ask profile gap questions yet.
    - Do NOT append a file nudge; the whole message is already about uploading docs.

    ─────────────────────────────────────────────────────────────────
    PHASE: bridge  (documents received, extraction running)
    ─────────────────────────────────────────────────────────────────
    The candidate has uploaded documents. Acknowledge the upload warmly.
    - Ask exactly ONE question: have they thought about which MBA programs or schools
      they are interested in? Probe for specific schools, program types (full-time, EMBA,
      part-time), intake year, and their reasoning.
    - Store their answer as `target_programs` in `profile_updates_json`.
    - Do NOT ask profile gap questions yet — the document extraction is still running.
    - Do NOT append a file nudge.

    ─────────────────────────────────────────────────────────────────
    PHASE: gap_filling  (documents extracted; gap-driven interview)
    ─────────────────────────────────────────────────────────────────
    Documents have been processed and key profile data has been extracted.
    - Look at `profile_gaps_json` — the ordered list of attributes still missing or thin.
    - Pick the highest-priority gap and ask exactly ONE targeted question about it.
    - IMPORTANT: An attribute in `profile_gaps_json` may already have partial content in
      `current_profile_json`. When it does, acknowledge what you have and ask for the
      specific missing detail — never ask about an attribute from scratch if content exists.
    - Use `attribute_schema_json` to understand what good content looks like.
    - Briefly acknowledge the candidate's previous answer before asking the next question.
    - Naturally weave in a brief progress indicator once per response. Skip if the score
      hasn't visibly changed.
    - IMPORTANT: The `completeness_score` reflects the state BEFORE your extraction runs,
      so the actual score after this turn may be higher. To avoid stating a number that
      immediately conflicts with the UI progress bar:
        * Below 80%: you may use the exact score (e.g. "You're at 60% — solid progress.")
        * 80% and above: use ONLY qualitative phrases — NEVER a specific percentage.
          Use phrases like "almost there", "very close to complete", "just one area left",
          "the profile is nearly done", or "this last detail will wrap it up".
    - If `answer_classification` is 'candidate_question': answer their question clearly,
      then re-ask the most important gap question.
    - If `answer_classification` is 'irrelevant': briefly acknowledge, then ask the next
      gap question — never mechanically repeat the last question verbatim.
    - Extract concrete profile information from the candidate's answer into
      `profile_updates_json`. Return {} if the answer was vague or off-topic.
      Every value in `profile_updates_json` must be written in clear professional
      English — translate or paraphrase from the candidate's language when needed;
      keep proper nouns (people, schools, employers) in a standard English form
      when one exists.

    ─────────────────────────────────────────────────────────────────
    UNIVERSAL RULES (all phases)
    ─────────────────────────────────────────────────────────────────
    - Ask at most ONE question per turn.
    - Never copy-paste `last_question_asked` verbatim — always re-frame naturally.
    - Be warm, direct, and conversational. No robotic or mechanical phrasing.
    - ALWAYS respond in English. Never switch languages under any circumstances.
    """

    candidate_name: str = dspy.InputField(desc="The candidate's full name.")
    intake_phase: str = dspy.InputField(
        desc=(
            "Current phase of the intake flow. One of: 'intro' (no docs uploaded), "
            "'bridge' (docs uploaded, extraction in progress — ask about target schools), "
            "'gap_filling' (docs processed — ask gap-targeted questions)."
        )
    )
    last_question_asked: str = dspy.InputField(
        desc="The exact question you asked in the previous turn. Empty string on the first turn."
    )
    current_profile_json: str = dspy.InputField(
        desc=(
            "JSON object of profile attributes already captured. A key being present means content "
            "exists for that attribute, but it may still appear in profile_gaps_json if the content "
            "is thin or vague. Use this to avoid re-asking from scratch — build on what's here."
        )
    )
    profile_gaps_json: str = dspy.InputField(
        desc=(
            "JSON array of candidate-input attribute keys that are still missing or insufficient "
            "(thin/vague), in priority order. Only relevant in gap_filling phase."
        )
    )
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object mapping attribute keys to descriptions of what good content looks like."
    )
    completeness_score: str = dspy.InputField(
        desc="Integer 0–100 indicating how complete the profile is. Use for progress notes in gap_filling phase."
    )
    conversation_history: str = dspy.InputField(
        desc="Recent conversation as alternating INTERVIEWER / CANDIDATE lines."
    )
    user_message: str = dspy.InputField(desc="The candidate's latest message.")
    has_files: str = dspy.InputField(desc="'true' if the candidate has uploaded documents, 'false' otherwise.")
    answer_classification: str = dspy.InputField(
        desc=(
            "One of: relevant, irrelevant, candidate_question. "
            "'relevant' means the message addressed the question. "
            "'irrelevant' means the message didn't address the question. "
            "'candidate_question' means the candidate asked their own question."
        )
    )
    response: str = dspy.OutputField(
        desc=(
            "Your reply, shaped by intake_phase. "
            "intro: brief warm response + redirect to upload docs. "
            "bridge: acknowledge upload + ask about target schools/programs. "
            "gap_filling: acknowledge previous answer + ask ONE targeted gap question + optional progress note."
        )
    )
    profile_updates_json: str = dspy.OutputField(
        desc=(
            "Valid JSON object of new profile key/value pairs extracted from the candidate's "
            "answer; all string values must be English (translate if they wrote in another language). "
            "In bridge phase, store school/program answer as 'target_programs'. "
            "In gap_filling phase, use keys from attribute_schema_json. Return {} if nothing to extract."
        )
    )


class OpenAIIntakeInterviewer(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(OpenAIIntakeInterviewSignature)

    def forward(  # type: ignore[override]
        self,
        candidate_name: str,
        intake_phase: str,
        last_question_asked: str,
        current_profile_json: str,
        profile_gaps_json: str,
        attribute_schema_json: str,
        completeness_score: int,
        conversation_history: str,
        user_message: str,
        has_files: bool,
        answer_classification: str,
    ) -> dspy.Prediction:
        return self._predict(
            candidate_name=candidate_name,
            intake_phase=intake_phase,
            last_question_asked=last_question_asked,
            current_profile_json=current_profile_json,
            profile_gaps_json=profile_gaps_json,
            attribute_schema_json=attribute_schema_json,
            completeness_score=str(completeness_score),
            conversation_history=conversation_history,
            user_message=user_message,
            has_files="true" if has_files else "false",
            answer_classification=answer_classification,
        )


class MockIntakeInterviewer(dspy.Module):
    """
    Deterministic interviewer for mock/test mode.

    Implements the same 3-phase logic as OpenAIIntakeInterviewer without an LLM.
    """

    def forward(  # type: ignore[override]
        self,
        candidate_name: str,
        intake_phase: str,
        last_question_asked: str,
        current_profile_json: str,
        profile_gaps_json: str,
        attribute_schema_json: str,
        completeness_score: int,
        conversation_history: str,
        user_message: str,
        has_files: bool,
        answer_classification: str,
    ) -> dspy.Prediction:
        try:
            profile: dict = json.loads(current_profile_json) if current_profile_json else {}
        except (json.JSONDecodeError, ValueError):
            profile = {}

        try:
            gaps: list[str] = json.loads(profile_gaps_json) if profile_gaps_json else []
            if not isinstance(gaps, list):
                gaps = []
        except (json.JSONDecodeError, ValueError):
            gaps = [k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in profile]

        profile_updates: dict = {}

        # ── Phase: intro ──────────────────────────────────────────────────────
        if intake_phase == "intro":
            ack = _build_acknowledgement(user_message)
            response = (
                f"{ack}\n\n"
                "To get started properly I'll need two documents from you:\n\n"
                "- **Your CV or résumé** — so I can understand your career trajectory, "
                "the types of roles you've held, and the scope of your responsibilities.\n\n"
                "- **A life story document** — a personal statement draft, narrative bio, "
                "or a few paragraphs about what shaped you: your values, turning points, "
                "and why an MBA makes sense for you right now.\n\n"
                "Go ahead and upload them whenever you're ready."
            )
            return dspy.Prediction(
                response=response,
                profile_updates_json=json.dumps({}, ensure_ascii=False),
            )

        # ── Phase: bridge ─────────────────────────────────────────────────────
        if intake_phase == "bridge":
            response = (
                "Thanks for uploading your documents — I'm reviewing them now and will "
                "extract the key information about your background.\n\n"
                "While that's running, I'd love to ask: have you started thinking about "
                "which MBA programs or schools you're interested in? Even a rough sense — "
                "specific schools, program types (full-time, EMBA, part-time), intake year, "
                "or the kinds of programs you're drawn to — is really helpful at this stage."
            )
            # If the user's message contains school-related content, capture it
            msg_lower = user_message.lower()
            if any(
                kw in msg_lower
                for kw in (
                    "harvard", "wharton", "stanford", "kellogg", "booth", "columbia",
                    "insead", "lbs", "hec", "mba", "program", "school", "apply",
                    "full-time", "part-time", "emba", "intake",
                )
            ):
                profile_updates["target_programs"] = user_message.strip()
                response = (
                    f"Got it — that's a helpful starting point. {_build_progress_note(completeness_score)}\n\n"
                    "I'll keep that in mind as we build your profile. "
                    "I'll have more on school fit once I've reviewed your documents."
                )
            return dspy.Prediction(
                response=response,
                profile_updates_json=json.dumps(profile_updates, ensure_ascii=False),
            )

        # ── Phase: gap_filling ────────────────────────────────────────────────
        current_gap = gaps[0] if gaps else None

        all_done_message = (
            "You've covered a lot of ground — thank you. "
            "Is there anything else about your background or goals you'd like to add before we move on?"
        )

        progress_note = _build_progress_note(completeness_score)

        if answer_classification == "candidate_question":
            next_q = (
                _MOCK_QUESTION_HINTS.get(
                    current_gap,
                    f"can you tell me about your {current_gap.replace('_', ' ')}?",
                )
                if current_gap
                else all_done_message
            )
            response = (
                "That's a great question. The MBA admissions process typically takes 6–12 months "
                "from preparation to decision, and strong applications combine a clear narrative, "
                "compelling recommendations, and a polished set of essays.\n\n"
                f"Now, back to what I'd love to understand — {next_q}"
            )
        else:
            profile_updates = _extract_profile_updates(user_message, profile)

            if current_gap and current_gap not in profile_updates:
                hint = _MOCK_QUESTION_HINTS.get(
                    current_gap,
                    f"can you tell me more about your {current_gap.replace('_', ' ')}?",
                )
                response = f"Thanks for sharing that. {progress_note}\n\n{hint}"
            else:
                merged_profile = {**profile, **profile_updates}
                remaining_gaps = [k for k in CANDIDATE_INPUT_ATTRIBUTES if k not in merged_profile]
                next_gap = remaining_gaps[0] if remaining_gaps else None

                ack = _build_acknowledgement(user_message)
                if next_gap:
                    next_q = _MOCK_QUESTION_HINTS.get(
                        next_gap,
                        f"can you walk me through your {next_gap.replace('_', ' ')}?",
                    )
                    response = f"{ack} {progress_note}\n\n{next_q}"
                else:
                    response = f"{ack}\n\n{all_done_message}"

        return dspy.Prediction(
            response=response,
            profile_updates_json=json.dumps(profile_updates, ensure_ascii=False),
        )


def _build_progress_note(score: int) -> str:
    """Return a short, encouraging progress sentence based on the completeness score."""
    if score <= 0:
        return "We're just getting started."
    if score < 25:
        return f"We're about {score}% of the way through — good start."
    if score < 50:
        return f"You're at {score}% — we're making solid progress."
    if score < 75:
        return f"You're at {score}% — more than halfway there."
    if score < 80:
        return f"Great progress — the profile is {score}% complete."
    # Above 80%: avoid exact numbers since the score often jumps after extraction,
    # which would make the message conflict with the UI progress bar.
    if score < 90:
        return "Great progress — nearly there."
    if score < 100:
        return "Almost there — just a couple of areas left."
    return "The profile is complete."


def _build_acknowledgement(user_message: str) -> str:
    msg = user_message.strip()
    if len(msg) < 20:
        return "Thanks for sharing that."
    if any(kw in msg.lower() for kw in ("because", "wanted", "decided", "chose", "moved")):
        return "That's really helpful context — thank you."
    return "Got it, appreciate you sharing that."


def _extract_profile_updates(user_message: str, existing_profile: dict) -> dict:
    """
    Lightweight keyword heuristics to populate profile keys from the message.
    Only extracts keys not already present so we don't overwrite richer data.
    """
    updates: dict = {}
    msg_lower = user_message.lower()

    if "core_identity" not in existing_profile and any(
        kw in msg_lower for kw in ("i am", "i've been", "i work", "my role", "i lead")
    ):
        updates["core_identity"] = user_message.strip()

    if "domain_base" not in existing_profile and any(
        kw in msg_lower for kw in ("sector", "industry", "government", "military", "finance", "tech", "startup")
    ):
        updates["domain_base"] = user_message.strip()

    if "core_strengths" not in existing_profile and any(
        kw in msg_lower for kw in ("strength", "good at", "excel", "known for", "skilled", "expertise")
    ):
        updates["core_strengths"] = user_message.strip()

    if "differentiation_layer" not in existing_profile and any(
        kw in msg_lower for kw in ("resilience", "community", "adversity", "values", "identity", "personal")
    ):
        updates["differentiation_layer"] = user_message.strip()

    if "intellectual_working_style" not in existing_profile and any(
        kw in msg_lower for kw in ("analytical", "systematic", "think", "approach", "problem", "data")
    ):
        updates["intellectual_working_style"] = user_message.strip()

    if "motivation" not in existing_profile and any(
        kw in msg_lower for kw in ("want to", "goal", "after the", "hope to", "plan to", "aim to", "mba because")
    ):
        updates["motivation"] = user_message.strip()

    if "core_tension" not in existing_profile and any(
        kw in msg_lower for kw in ("pivot", "transition", "switch", "change", "move into", "leave")
    ):
        updates["core_tension"] = user_message.strip()

    if "transferable_assets" not in existing_profile and any(
        kw in msg_lower for kw in ("transferable", "bring", "apply", "leverage", "experience in", "background in")
    ):
        updates["transferable_assets"] = user_message.strip()

    return updates
