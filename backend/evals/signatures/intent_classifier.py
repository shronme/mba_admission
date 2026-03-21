"""
Signature variants for IntentClassifier.

Variants differ in field structure — which output fields are included and
how tightly constrained the output type is.
MIPROv2 will optimise the instruction text — docstrings are minimal hints.

REGISTRY maps name → signature class.
DEFAULT is the name of the production-equivalent variant.
"""
from __future__ import annotations

from typing import Literal

import dspy

_ALLOWED_INTENTS = (
    "intake_documents, intake_goals, admissions_general_help, off_topic"
)

_ALLOWED_LITERAL = Literal[
    "intake_documents",
    "intake_goals",
    "admissions_general_help",
    "off_topic",
]


class IntentClassifierV1(dspy.Signature):
    """
    Determine which admissions-related stage the user is in.

    Allowed intent outputs:
    - intake_documents: user wants to upload or discuss their application documents
    - intake_goals: user is defining or discussing their post-MBA goals or career narrative
    - admissions_general_help: user has a general MBA admissions question
    - off_topic: message is unrelated to MBA admissions
    """

    message: str = dspy.InputField(
        desc="The user's raw message."
    )
    intent: str = dspy.OutputField(
        desc=f"One of: {_ALLOWED_INTENTS}"
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation for the chosen intent."
    )
    confidence: str = dspy.OutputField(
        desc="Confidence level: high, medium, or low."
    )


class IntentClassifierV2(dspy.Signature):
    """
    Classify the user's message into the correct admissions stage.

    Think step-by-step: identify whether the message mentions documents,
    career goals, general admissions questions, or something entirely
    unrelated to MBA admissions.
    """

    message: str = dspy.InputField(
        desc="The user's raw message."
    )
    reasoning: str = dspy.OutputField(
        desc=(
            "Step-by-step: (1) does the message mention documents or uploads? "
            "(2) does it discuss goals, narrative, or career direction? "
            "(3) is it a general admissions question? (4) is it off-topic?"
        )
    )
    intent: _ALLOWED_LITERAL = dspy.OutputField(  # type: ignore[valid-type]
        desc=f"Exactly one of: {_ALLOWED_INTENTS}"
    )


class IntentClassifierV3(dspy.Signature):
    """
    Classify the MBA admissions intent of the user's message. Return only the intent label.
    """

    message: str = dspy.InputField(
        desc="The user's raw message."
    )
    intent: _ALLOWED_LITERAL = dspy.OutputField(  # type: ignore[valid-type]
        desc=f"Exactly one of: {_ALLOWED_INTENTS}"
    )


REGISTRY: dict[str, type[dspy.Signature]] = {
    "v1_baseline": IntentClassifierV1,
    "v2_cot_literal": IntentClassifierV2,
    "v3_no_reasoning": IntentClassifierV3,
}

DEFAULT = "v1_baseline"
