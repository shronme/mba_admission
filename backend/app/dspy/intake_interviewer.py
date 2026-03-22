from __future__ import annotations

import json

import dspy

from app.dspy.profile_agent import (
    CANDIDATE_INPUT_ATTRIBUTES,
    _ATTRIBUTE_SCHEMA_JSON,
)

_NO_FILES_NUDGE = (
    "\n\n_(Tip: uploading your resume, transcripts, or any background notes "
    "will let me give you much more tailored guidance.)_"
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
    "risks": "are there any parts of your profile — GPA, work history, career pivot — that you think admissions committees will scrutinise?",
}


class OpenAIIntakeInterviewSignature(dspy.Signature):
    """
    You are an experienced MBA admissions coach conducting a structured intake interview.

    CRITICAL RULE — ALWAYS MOVE THE CONVERSATION FORWARD:
    Never mechanically repeat your last question verbatim. Even if `answer_classification`
    is 'irrelevant', briefly acknowledge what the candidate said and then ask the single
    most important unanswered question from `profile_gaps_json`. Use `last_question_asked`
    as context for what you were trying to learn, but always re-frame it naturally rather
    than copy-pasting it.

    QUESTION GENERATION:
    - Look at `profile_gaps_json` — the ordered list of profile attributes that are still
      missing OR present but too thin/vague. Pick the most important gap to address next.
    - IMPORTANT: An attribute in `profile_gaps_json` may already have partial content in
      `current_profile_json`. In that case the attribute is THIN, not absent. When this
      happens you MUST:
        1. Acknowledge what you already have ("I've got your fintech background noted —").
        2. Explain specifically what additional detail would make it stronger (seniority
           level, scope, breadth, etc.).
        3. Ask a targeted follow-up, NOT a generic "tell me about X" question.
      Never ask about an attribute from scratch if content already exists for it.
    - Use `attribute_schema_json` to understand what good content looks like for that
      attribute, then craft a natural, conversational question that would draw out the
      missing detail from this specific candidate.
    - Ask exactly ONE question per turn.

    PROGRESS COMMUNICATION:
    - `completeness_score` is an integer 0–100 reflecting how complete the profile is,
      already accounting for the candidate's most recent answer.
    - Naturally weave a brief progress indicator into your response each turn — but keep
      it encouraging and conversational, not robotic. Examples:
        "We're about 40% of the way through — you're making solid progress."
        "You're at 75% — just a couple of areas left to cover."
        "Almost there — the profile is 90% complete."
    - If the score has not visibly changed since the prior turn, do NOT repeat the same
      number — instead say something like "still making progress" or skip the percentage.
    - Place the progress note at the END of your acknowledgement, before the next question.
    - Keep it to one short sentence. Never repeat it mid-response.

    OTHER RULES:
    - Briefly acknowledge the candidate's answer before asking the next question.
    - Skip attributes already captured AND complete in current_profile_json (i.e., not in
      profile_gaps_json).
    - If answer_classification is 'candidate_question', answer the candidate's question
      clearly and concisely first, then re-ask last_question_asked.
    - If has_files is 'false', append this reminder at the very end (new line):
      "(Tip: uploading your resume, transcripts, or any background notes will let me
      give you much more tailored guidance.)"
    - Extract concrete profile information from the candidate's answer into
      profile_updates_json. Use the attribute keys from attribute_schema_json.
      Return {} if the answer was vague or off-topic.
    """

    candidate_name: str = dspy.InputField(desc="The candidate's full name.")
    last_question_asked: str = dspy.InputField(
        desc="The exact question you asked the candidate in the previous turn. Empty string on the first turn."
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
            "(thin/vague), in priority order. An attribute in this list may already have partial "
            "content in current_profile_json — in that case it is THIN, not absent. Always check "
            "current_profile_json before deciding how to frame your follow-up."
        )
    )
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object mapping attribute keys to descriptions of what good content looks like."
    )
    completeness_score: str = dspy.InputField(
        desc="Integer 0–100 indicating how complete the profile is. Use this to inform the candidate of their progress."
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
            "'irrelevant' means the message didn't address the question — gently acknowledge it, "
            "then ask the single most important unanswered question from profile_gaps_json "
            "(do NOT mechanically repeat last_question_asked verbatim). "
            "'candidate_question' means the candidate asked their own question."
        )
    )

    response: str = dspy.OutputField(
        desc=(
            "Your reply. Briefly acknowledge the candidate's message, then ask exactly one "
            "targeted question about the highest-priority gap from profile_gaps_json. "
            "Never copy-paste last_question_asked verbatim — always re-frame naturally. "
            "If answer_classification is 'candidate_question': answer their question first, "
            "then ask the most important gap question."
        )
    )
    profile_updates_json: str = dspy.OutputField(
        desc=(
            "Valid JSON object of new profile key/value pairs extracted from the candidate's "
            "answer. Keys must match attribute_schema_json. Return {} if answer was vague or off-topic."
        )
    )


class OpenAIIntakeInterviewer(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(OpenAIIntakeInterviewSignature)

    def forward(  # type: ignore[override]
        self,
        candidate_name: str,
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

    - Reads profile_gaps_json to find the first uncovered attribute.
    - Asks a generic "tell me about X" question for that attribute.
    - Attempts simple keyword extraction for profile updates.
    - When answer_classification is 'candidate_question', re-asks last_question_asked.
    - Appends the no-files nudge when has_files=False.
    """

    def forward(  # type: ignore[override]
        self,
        candidate_name: str,
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
            profile_updates: dict = {}
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

        if not has_files:
            response += _NO_FILES_NUDGE

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
    if score < 90:
        return f"Great progress — the profile is {score}% complete."
    if score < 100:
        return f"Almost there — {score}% complete, just a couple of areas left."
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

    if "risks" not in existing_profile and any(
        kw in msg_lower for kw in ("weak", "gap", "missing", "lack", "haven't", "low gpa", "low gmat", "concern")
    ):
        updates["risks"] = user_message.strip()

    return updates
