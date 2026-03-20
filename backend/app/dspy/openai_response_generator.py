from __future__ import annotations

import dspy


class OpenAIResponseSignature(dspy.Signature):
    """
    Generate an assistant response strictly within admissions/help scope.
    """

    primary_intent = dspy.InputField()
    secondary_flags = dspy.InputField()
    requires_clarification = dspy.InputField()
    user_message = dspy.InputField()
    memory_context = dspy.InputField()
    final_answer = dspy.OutputField()


class OpenAIResponseGenerator(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(OpenAIResponseSignature)

    def forward(  # type: ignore[override]
        self,
        primary_intent: str,
        secondary_flags: list[str] | str,
        requires_clarification: bool,
        user_message: str,
        memory_context: str,
    ) -> dspy.Prediction:
        # Passing lists is fine, but we also accept stringified flags for flexibility.
        return self._predict(
            primary_intent=primary_intent,
            secondary_flags=secondary_flags,
            requires_clarification=requires_clarification,
            user_message=user_message,
            memory_context=memory_context,
        )

