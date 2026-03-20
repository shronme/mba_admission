from __future__ import annotations

import re

import dspy


class IntentSignature(dspy.Signature):
    message = dspy.InputField()
    intent = dspy.OutputField()
    reasoning = dspy.OutputField()


class StaticIntentClassifier(dspy.Module):
    """
    Minimal sample DSPy module (Task 004 acceptance).

    This module is deterministic and does not require an LLM; it exists to
    prove the DSPy runtime + module execution wiring works.
    """

    def forward(self, message: str) -> dspy.Prediction:  # type: ignore[override]
        msg = (message or "").strip()
        lower = msg.lower()

        if any(k in lower for k in ("upload", "document", "transcript", "resume", "grades")):
            intent = "intake_documents"
            reasoning = "User is asking for or referencing documents."
        elif any(k in lower for k in ("goal", "goals", "mba", "program", "admission", "admissions", "round")):
            intent = "intake_goals"
            reasoning = "User is asking about admissions/program goals."
        elif any(k in lower for k in ("essay", "personal statement", "draft", "write the essay")):
            intent = "admissions_essay_planning"
            reasoning = "User is asking about essay planning."
        else:
            intent = "admissions_general_help"
            reasoning = "Default to admissions help."

        # Guardrail-like refinement.
        if re.search(r"\b(calculus|quantum|photosynthesis)\b", lower):
            intent = "off_topic"
            reasoning = "Message contains non-admissions keywords."

        return dspy.Prediction(message=msg, intent=intent, reasoning=reasoning)

