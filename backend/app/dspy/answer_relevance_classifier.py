from __future__ import annotations

import re

import dspy

_TOPIC_KEYWORDS = (
    "career", "job", "role", "work", "company", "industry", "degree", "major",
    "school", "university", "college", "program", "mba", "grad", "goal",
    "plan", "timeline", "round", "why", "because", "moved", "transition",
    "promotion", "manager", "leadership", "impact", "evidence", "weakness",
    "gap", "gmat", "gre", "gpa", "test", "score", "application", "essay",
    "recommendation", "sponsor", "finance", "consulting", "tech", "startup",
)


class AnswerRelevanceSignature(dspy.Signature):
    """
    Classify how a candidate's message relates to the last question asked by the interviewer.

    Output classification must be exactly one of:
    - relevant: the message meaningfully addresses the question
    - irrelevant: the message does not address the question at all
    - candidate_question: the candidate is asking their own question rather than answering
    """

    last_question_asked: str = dspy.InputField(
        desc="The most recent question the interviewer asked the candidate."
    )
    user_message: str = dspy.InputField(
        desc="The candidate's latest message."
    )
    classification: str = dspy.OutputField(
        desc="Exactly one of: relevant, irrelevant, candidate_question"
    )
    reasoning: str = dspy.OutputField(
        desc="One-sentence explanation (for logging only)."
    )


class OpenAIAnswerRelevanceClassifier(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(AnswerRelevanceSignature)

    def forward(  # type: ignore[override]
        self,
        last_question_asked: str,
        user_message: str,
    ) -> dspy.Prediction:
        result = self._predict(
            last_question_asked=last_question_asked,
            user_message=user_message,
        )
        raw = (getattr(result, "classification", "") or "").strip().lower()
        if raw not in {"relevant", "irrelevant", "candidate_question"}:
            raw = "relevant"
        return dspy.Prediction(
            classification=raw,
            reasoning=str(getattr(result, "reasoning", "")),
        )


class MockAnswerRelevanceClassifier(dspy.Module):
    """
    Deterministic heuristic classifier for mock/test mode.

    Rules (in priority order):
    1. If the message ends with '?' (ignoring trailing whitespace/punctuation) → candidate_question
    2. If message has fewer than 8 words AND contains none of the topic keywords → irrelevant
    3. Otherwise → relevant
    """

    def forward(  # type: ignore[override]
        self,
        last_question_asked: str,
        user_message: str,
    ) -> dspy.Prediction:
        stripped = user_message.strip()

        # Rule 1: candidate asking a question
        if stripped.endswith("?"):
            return dspy.Prediction(
                classification="candidate_question",
                reasoning="Message ends with a question mark — candidate is asking something.",
            )

        # Also check for question patterns without trailing '?'
        question_starters = re.compile(
            r"^\s*(what|why|how|when|where|who|can you|could you|do you|is it|are there|will)\b",
            re.IGNORECASE,
        )
        if question_starters.match(stripped):
            return dspy.Prediction(
                classification="candidate_question",
                reasoning="Message starts with a question word — candidate is asking something.",
            )

        words = stripped.lower().split()

        # Rule 2: too short and off-topic
        if len(words) < 8 and not any(kw in stripped.lower() for kw in _TOPIC_KEYWORDS):
            return dspy.Prediction(
                classification="irrelevant",
                reasoning="Very short message with no recognisable admissions-related content.",
            )

        return dspy.Prediction(
            classification="relevant",
            reasoning="Message appears to address the interview question.",
        )
