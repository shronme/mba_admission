from __future__ import annotations

import json

import dspy

_NO_FILES_NUDGE = (
    "\n\n_(Tip: uploading your resume, transcripts, or any background notes "
    "will let me give you much more tailored guidance.)_"
)

# Ordered list of (attribute_key, question) pairs that drive the interview.
# The key is used to check whether the area has already been captured in the
# candidate's profile attributes so we don't re-ask covered ground.
INTERVIEW_QUESTIONS: list[tuple[str, str]] = [
    ("career_path", "Walk me through your career path — where did you start and how did you get to where you are now?"),
    ("undergrad_degree", "Why did you choose your undergrad degree or field of study?"),
    ("role_transitions", "You've moved between roles (or industries) — what drove those transitions?"),
    ("post_mba_goals", "What do you actually want to do after the program? Be as specific as you can."),
    ("motivation_timing", "Why now? What's changed or is changing that makes this the right moment to pursue the degree?"),
    ("why_not_current_path", "Why not stay on your current path? What can't you achieve without the degree?"),
    ("evidence_for_goals", "What's the strongest evidence that you can achieve the goals you just described?"),
    ("identified_weaknesses", "What's weak or missing in your profile right now — and how are you thinking about addressing it?"),
]


class OpenAIIntakeInterviewSignature(dspy.Signature):
    """
    You are an experienced MBA admissions coach conducting a structured intake interview.

    CRITICAL RULE — STAY ON THE CURRENT QUESTION:
    The field `last_question_asked` tells you exactly what you asked the candidate last turn.
    Before moving to any new topic, you MUST verify that the candidate's answer actually
    addresses that specific question. Examples of NOT answering:
    - Asked "Why did you choose your undergrad degree?" → candidate says "I want to be an
      entrepreneur" → this does NOT answer the undergrad question; re-ask it.
    - Asked "Walk me through your career path" → candidate says "I want an MBA" → does not
      address career history; re-ask it.
    If the answer is off-topic or only tangentially related to what was asked, gently
    acknowledge what they said, clarify what you were asking, and re-ask the same question.
    Only move to the next question when the current one has a real, specific answer.

    OTHER RULES:
    - Briefly acknowledge the candidate's answer before asking the next question.
    - Ask exactly ONE question per turn.
    - Skip areas already captured in current_profile_json.
    - If answer_classification is 'candidate_question', answer the candidate's question
      clearly and concisely first, then re-ask last_question_asked.
    - If has_files is 'false', append this reminder at the very end (new line):
      "(Tip: uploading your resume, transcripts, or any background notes will let me
      give you much more tailored guidance.)"
    - Extract concrete profile information from the candidate's answer into
      profile_updates_json. Use keys: career_path, undergrad_degree, role_transitions,
      post_mba_goals, motivation_timing, why_not_current_path, evidence_for_goals,
      identified_weaknesses. Return {{}} if the answer was vague or off-topic.
    """

    candidate_name: str = dspy.InputField(desc="The candidate's full name.")
    last_question_asked: str = dspy.InputField(
        desc="The exact question you asked the candidate in the previous turn. Empty string on the first turn."
    )
    current_profile_json: str = dspy.InputField(
        desc="JSON object of profile attributes already captured. Keys present mean that area is covered."
    )
    conversation_history: str = dspy.InputField(
        desc="Recent conversation as alternating INTERVIEWER / CANDIDATE lines."
    )
    user_message: str = dspy.InputField(desc="The candidate's latest message.")
    has_files: str = dspy.InputField(desc="'true' if the candidate has uploaded documents, 'false' otherwise.")
    answer_classification: str = dspy.InputField(
        desc="One of: relevant, candidate_question. 'relevant' means the message attempted to answer the question."
    )
    response: str = dspy.OutputField(
        desc=(
            "Your reply. If the answer addressed last_question_asked: acknowledge + ask next question. "
            "If the answer did NOT address last_question_asked: acknowledge what they said, clarify "
            "what you were asking, and re-ask the same question. "
            "If candidate_question: answer their question first, then re-ask last_question_asked."
        )
    )
    profile_updates_json: str = dspy.OutputField(
        desc="Valid JSON object of new profile key/value pairs extracted from the candidate's answer. Empty object {} if answer was vague or off-topic."
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
        conversation_history: str,
        user_message: str,
        has_files: bool,
        answer_classification: str,
    ) -> dspy.Prediction:
        return self._predict(
            candidate_name=candidate_name,
            last_question_asked=last_question_asked,
            current_profile_json=current_profile_json,
            conversation_history=conversation_history,
            user_message=user_message,
            has_files="true" if has_files else "false",
            answer_classification=answer_classification,
        )


class MockIntakeInterviewer(dspy.Module):
    """
    Deterministic interviewer for mock/test mode.

    - Attempts to extract profile updates from the user message.
    - If the current question's key was NOT populated by the answer, stays on that
      question and asks it again (handles off-topic / vague answers).
    - When answer_classification is 'candidate_question', re-asks last_question_asked.
    - Appends the no-files nudge when has_files=False.
    """

    def forward(  # type: ignore[override]
        self,
        candidate_name: str,
        last_question_asked: str,
        current_profile_json: str,
        conversation_history: str,
        user_message: str,
        has_files: bool,
        answer_classification: str,
    ) -> dspy.Prediction:
        try:
            profile: dict = json.loads(current_profile_json) if current_profile_json else {}
        except (json.JSONDecodeError, ValueError):
            profile = {}

        # Determine which question is currently pending (first key absent from profile).
        current_key: str | None = None
        current_question: str | None = None
        for key, question in INTERVIEW_QUESTIONS:
            if key not in profile:
                current_key = key
                current_question = question
                break

        all_done_question = (
            "You've covered a lot of ground — thank you. "
            "Is there anything else about your background or goals you'd like to add before we move on?"
        )

        # Build the response
        if answer_classification == "candidate_question":
            response = (
                "That's a great question. The MBA admissions process typically takes 6–12 months "
                "from preparation to decision, and strong applications combine a clear narrative, "
                "compelling recommendations, and a polished set of essays.\n\n"
                f"Now, back to where we were — {last_question_asked or current_question or all_done_question}"
            )
            profile_updates: dict = {}
        else:
            # Try to extract profile data from the answer.
            profile_updates = _extract_profile_updates(user_message, profile)

            # If the current question's key was not populated, the answer didn't
            # address it — re-ask with a gentle redirect.
            if current_key and current_key not in profile_updates:
                response = (
                    f"Thanks for sharing that — it's useful context. "
                    f"I want to make sure I understand: {current_question}"
                )
            else:
                # Answer populated the key — advance to the next question.
                merged_profile = {**profile, **profile_updates}
                next_question: str | None = None
                for key, question in INTERVIEW_QUESTIONS:
                    if key not in merged_profile:
                        next_question = question
                        break
                ack = _build_acknowledgement(user_message)
                response = f"{ack}\n\n{next_question or all_done_question}"

        if not has_files:
            response += _NO_FILES_NUDGE

        return dspy.Prediction(
            response=response,
            profile_updates_json=json.dumps(profile_updates, ensure_ascii=False),
        )


def _extract_last_interviewer_question(conversation_history: str) -> str:
    """Pull the most recent INTERVIEWER line from the history string."""
    lines = conversation_history.strip().splitlines()
    for line in reversed(lines):
        if line.upper().startswith("INTERVIEWER:") or line.upper().startswith("ASSISTANT:"):
            text = line.split(":", 1)[-1].strip()
            # Return only the last sentence if it ends with '?'
            sentences = text.split("?")
            if len(sentences) > 1:
                return sentences[-2].strip().split("\n")[-1].strip() + "?"
            return text
    return ""


def _build_acknowledgement(user_message: str) -> str:
    msg = user_message.strip()
    if len(msg) < 20:
        return "Thanks for sharing that."
    if any(kw in msg.lower() for kw in ("because", "wanted", "decided", "chose", "moved")):
        return "That's really helpful context — thank you."
    return "Got it, appreciate you sharing that."


def _extract_profile_updates(user_message: str, existing_profile: dict) -> dict:
    """
    Very lightweight keyword heuristics to populate profile keys from the message.
    Only extracts keys not already present so we don't overwrite richer data.
    """
    updates: dict = {}
    msg_lower = user_message.lower()

    if "career_path" not in existing_profile and any(
        kw in msg_lower for kw in ("started", "began", "career", "worked at", "joined", "role")
    ):
        updates["career_path"] = user_message.strip()

    if "undergrad_degree" not in existing_profile and any(
        kw in msg_lower for kw in ("degree", "major", "studied", "undergrad", "bachelor", "university", "college")
    ):
        updates["undergrad_degree"] = user_message.strip()

    if "role_transitions" not in existing_profile and any(
        kw in msg_lower for kw in ("moved", "switched", "transition", "left", "changed", "promoted")
    ):
        updates["role_transitions"] = user_message.strip()

    if "post_mba_goals" not in existing_profile and any(
        kw in msg_lower for kw in ("want to", "goal", "after the program", "hope to", "plan to", "aim to")
    ):
        updates["post_mba_goals"] = user_message.strip()

    if "motivation_timing" not in existing_profile and any(
        kw in msg_lower for kw in ("now", "timing", "right time", "this year", "ready", "opportunity")
    ):
        updates["motivation_timing"] = user_message.strip()

    if "why_not_current_path" not in existing_profile and any(
        kw in msg_lower for kw in ("can't", "cannot", "without", "ceiling", "limited", "stuck", "plateau")
    ):
        updates["why_not_current_path"] = user_message.strip()

    if "evidence_for_goals" not in existing_profile and any(
        kw in msg_lower for kw in ("led", "built", "launched", "achieved", "result", "impact", "evidence", "proof")
    ):
        updates["evidence_for_goals"] = user_message.strip()

    if "identified_weaknesses" not in existing_profile and any(
        kw in msg_lower for kw in ("weak", "gap", "missing", "lack", "haven't", "low gpa", "low gmat", "no experience")
    ):
        updates["identified_weaknesses"] = user_message.strip()

    return updates
