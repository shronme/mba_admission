from __future__ import annotations

import dspy


class OpenAIIntentSignature(dspy.Signature):
    """
    Determine which admissions-related stage the user is in.

    Allowed `intent` outputs:
    - intake_documents
    - intake_goals
    - admissions_general_help
    - off_topic
    """

    message = dspy.InputField()
    intent = dspy.OutputField()
    reasoning = dspy.OutputField()
    confidence = dspy.OutputField()


class OpenAIIntentClassifier(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(OpenAIIntentSignature)

    def forward(self, message: str) -> dspy.Prediction:  # type: ignore[override]
        return self._predict(message=message)

