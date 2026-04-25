from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

import dspy

from app.schemas.agent_advisor_intent import (
    AgentAdvisorIntentOutput,
    AdvisorTargetDoc,
    AdvisorTaskKind,
)


class IntentClassifierSignature(dspy.Signature):
    """
    Classify the user's intent for the advisor agent and return a JSON object string.

    Output MUST be a single JSON object with keys:
    - task_kind: rewrite_cv | qa | smalltalk | other
    - target_doc: cv | life_story | essay | other
    - emphasis: short free-text string
    - prior_feedback: newline-separated bullet lines (e.g. "- ...") or empty string
    """

    conversation_history: str = dspy.InputField(
        desc="Conversation window (last ~10 messages), newest last."
    )
    user_message: str = dspy.InputField(desc="The candidate's latest message.")
    intent_json: str = dspy.OutputField(desc="JSON object string.")


class OpenAIIntentClassifier(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(IntentClassifierSignature)

    def forward(self, conversation_history: str, user_message: str) -> dspy.Prediction:  # type: ignore[override]
        return self._predict(
            conversation_history=conversation_history or "",
            user_message=user_message or "",
        )

    async def aforward(self, conversation_history: str, user_message: str) -> dspy.Prediction:  # type: ignore[override]
        return await self._predict.aforward(
            conversation_history=conversation_history or "",
            user_message=user_message or "",
        )


class MockIntentClassifier:
    """
    Deterministic keyword-based intent classifier for `DSPY_MODE=mock`.

    Rule precedence (highest first):
    1) rewrite_cv: "rewrite|revise|redraft|polish|improve|edit" + ("cv|resume|résumé")
       OR bare "improve my cv" style phrases.
    2) smalltalk: greetings / thanks.
    3) qa: question marks or common Q&A starters.
    4) other: default.
    """

    _REWRITE_RE = re.compile(
        r"(?i)\b(rewrite|revise|redraft|polish|improve|edit)\b.*\b(cv|resume|résumé)\b"
    )
    _SMALLTALK_RE = re.compile(r"(?i)^\s*(hi|hello|hey|thanks|thank you)\b")
    _QA_START_RE = re.compile(
        r"(?i)^\s*(what|why|how|when|where|who|can you|could you|do you|is it|are there|should i)\b"
    )

    def classify(self, *, conversation_history: str, user_message: str) -> AgentAdvisorIntentOutput:
        msg = (user_message or "").strip()
        low = msg.lower()

        if self._REWRITE_RE.search(msg) or "improve my cv" in low or "update my cv" in low:
            task_kind = AdvisorTaskKind.REWRITE_CV
            target_doc = AdvisorTargetDoc.CV
        elif self._SMALLTALK_RE.search(msg):
            task_kind = AdvisorTaskKind.SMALLTALK
            target_doc = AdvisorTargetDoc.OTHER
        elif "?" in msg or self._QA_START_RE.search(msg):
            task_kind = AdvisorTaskKind.QA
            target_doc = AdvisorTargetDoc.OTHER
        else:
            task_kind = AdvisorTaskKind.OTHER
            target_doc = AdvisorTargetDoc.OTHER

        emphasis = ""
        if task_kind == AdvisorTaskKind.REWRITE_CV:
            emphasis = "Improve clarity and quantify impact where already present."
        elif task_kind == AdvisorTaskKind.QA:
            emphasis = "Answer succinctly and ask one clarifying question if needed."

        # Deterministic "prior_feedback": extract up to 3 assistant lines that look like feedback.
        prior_feedback = ""
        history = conversation_history or ""
        feedback_lines: list[str] = []
        for line in history.splitlines():
            if not line.strip():
                continue
            if not line.upper().startswith("ASSISTANT:"):
                continue
            content = line.split(":", 1)[1].strip()
            if any(tok in content.lower() for tok in ("emphasize", "focus on", "tighten", "quantify")):
                feedback_lines.append(f"- {content}")
        if feedback_lines:
            prior_feedback = "\n".join(feedback_lines[-3:])

        return AgentAdvisorIntentOutput(
            task_kind=task_kind,
            target_doc=target_doc,
            emphasis=emphasis,
            prior_feedback=prior_feedback,
        )

    def classify_json(self, *, conversation_history: str, user_message: str) -> str:
        out = self.classify(conversation_history=conversation_history, user_message=user_message)
        return json.dumps(
            {
                "task_kind": out.task_kind.value,
                "target_doc": out.target_doc.value,
                "emphasis": out.emphasis,
                "prior_feedback": out.prior_feedback,
            }
        )


def last_n_messages_text(
    conversation_history: str | Sequence[dict[str, Any]] | None,
    *,
    n: int = 10,
) -> str:
    """
    Normalize conversation history into an ASSISTANT/USER transcript and keep only last N messages.
    """
    if not conversation_history:
        return ""

    if isinstance(conversation_history, str):
        lines = [ln for ln in conversation_history.splitlines() if ln.strip()]
        # Assume each message is already on its own line as "ASSISTANT: ..." / "USER: ...".
        return "\n".join(lines[-n:])

    if isinstance(conversation_history, Sequence):
        msgs = [m for m in conversation_history if isinstance(m, dict)]
        tail = msgs[-n:]
        out_lines: list[str] = []
        for m in tail:
            role = str(m.get("role") or "").lower()
            label = "ASSISTANT" if role == "assistant" else "USER"
            content = str(m.get("content") or "").strip()
            if content:
                out_lines.append(f"{label}: {content}")
        return "\n".join(out_lines)

    return ""

