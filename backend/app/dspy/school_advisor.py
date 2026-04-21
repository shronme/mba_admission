from __future__ import annotations

import json
from typing import Any

import dspy

from app.core.dspy_runtime import run_dspy_module


class AdvisorSignature(dspy.Signature):
    """
    You are an admissions advisor chatting with a candidate who has already completed
    an admission evaluation and confirmed a target school list.

    Use the candidate context to give specific, actionable guidance. Handle at minimum:
    - CV gap questions
    - essay angle / narrative strategy questions
    - test score strategy (GMAT/GRE) questions
    - open-ended "what should I focus on next" questions

    Rules:
    - Be concrete: reference the selected schools and the evaluation's priority actions when relevant.
    - Ask at most 1 clarifying question if needed; otherwise propose a clear next step.
    - Do not fabricate personal details; rely on the JSON context.
    """

    profile_attributes_json: str = dspy.InputField(desc="Candidate profile.attributes JSON.")
    selected_schools_json: str = dspy.InputField(
        desc='Confirmed schools JSON array like [{"school": "...", "program_slug": "..."}].'
    )
    admission_evaluation_result_json: str = dspy.InputField(
        desc='Evaluation JSON (status=complete) including priority_actions per program.'
    )
    conversation_history: str = dspy.InputField(
        desc="Recent conversation history formatted as ASSISTANT/USER lines."
    )
    user_message: str = dspy.InputField(desc="Latest user message.")

    response: str = dspy.OutputField(desc="Advisor response to stream back to the user.")


class OpenAIAdvisorModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(AdvisorSignature)

    def forward(  # type: ignore[override]
        self,
        profile_attributes_json: str,
        selected_schools_json: str,
        admission_evaluation_result_json: str,
        conversation_history: str,
        user_message: str,
    ) -> dspy.Prediction:
        return self._predict(
            profile_attributes_json=profile_attributes_json,
            selected_schools_json=selected_schools_json,
            admission_evaluation_result_json=admission_evaluation_result_json,
            conversation_history=conversation_history,
            user_message=user_message,
        )


class MockAdvisorModule(dspy.Module):
    def forward(  # type: ignore[override]
        self,
        profile_attributes_json: str,
        selected_schools_json: str,
        admission_evaluation_result_json: str,
        conversation_history: str,
        user_message: str,
    ) -> dspy.Prediction:
        # Deterministic, non-empty response for CI and local dev.
        try:
            selected = json.loads(selected_schools_json) if selected_schools_json else []
        except Exception:
            selected = []
        schools = []
        if isinstance(selected, list):
            for row in selected:
                if isinstance(row, dict) and isinstance(row.get("school"), str):
                    schools.append(row["school"])
        schools_part = ", ".join(schools[:3]) if schools else "your selected schools"
        response = (
            f"(mock advisor) For {schools_part}, here's a concrete next step: "
            "pick one priority gap you can address this week, and I’ll help you turn it into a plan. "
            f"You asked: {user_message.strip() or '(empty)'}"
        )
        return dspy.Prediction(response=response)


def generate_opening_advisor_message(
    *,
    selected_schools: list[dict[str, Any]],
    admission_evaluation_result: dict[str, Any] | None,
    candidate_name: str | None = None,
    use_openai: bool,
) -> str:
    """
    Opening greeting for a newly created advisor thread.

    Must be non-empty and mockable.
    """
    if not use_openai:
        schools = [str(s.get("school") or "") for s in selected_schools if isinstance(s, dict)]
        schools = [s for s in schools if s.strip()]
        head = ", ".join(schools[:3]) if schools else "your selected schools"
        name_part = f" {candidate_name}" if candidate_name else ""
        return (
            f"Welcome{name_part} — I’m your admissions advisor. "
            f"I see you confirmed {head}. "
            "Tell me where you want to start: CV gaps, essay strategy, test score plan, or your top priorities."
        )

    # Best-effort: reuse the advisor module to generate an opening message.
    module = OpenAIAdvisorModule()
    out = run_dspy_module(
        module,
        profile_attributes_json="{}",
        selected_schools_json=json.dumps(selected_schools, ensure_ascii=False),
        admission_evaluation_result_json=json.dumps(admission_evaluation_result or {}, ensure_ascii=False),
        conversation_history="",
        user_message=(
            "Open the conversation with a short greeting that names the confirmed schools, "
            "mentions 2-3 top priority actions from the evaluation, and invites me to choose a focus."
        ),
    )
    text = str(getattr(out, "response", "") or "").strip()
    return text or "Welcome — tell me what you want to focus on first."

