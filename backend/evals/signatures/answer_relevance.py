"""
Signature variants for AnswerRelevanceClassifier.

Variants differ in field structure (output fields, type constraints, ordering).
MIPROv2 will optimise the instruction text within each variant — the docstrings
here are minimal starting hints, not the final prompts.

REGISTRY maps name → signature class.
DEFAULT is the name of the production-equivalent variant.
"""
from __future__ import annotations

from typing import Literal

import dspy


class AnswerRelevanceV1(dspy.Signature):
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


class AnswerRelevanceV2(dspy.Signature):
    """
    Classify whether a candidate's reply addresses the interviewer's question.

    Think step-by-step before classifying: consider the question asked, what a
    direct answer would look like, and how the candidate's message compares.
    """

    last_question_asked: str = dspy.InputField(
        desc="The exact question the interviewer asked in the previous turn."
    )
    user_message: str = dspy.InputField(
        desc="The candidate's latest message."
    )
    reasoning: str = dspy.OutputField(
        desc=(
            "Step-by-step reasoning: (1) what does a direct answer to the question look like? "
            "(2) does the candidate's message match? (3) is the candidate asking their own question?"
        )
    )
    classification: Literal["relevant", "irrelevant", "candidate_question"] = dspy.OutputField(
        desc="Exactly one of the three allowed values."
    )


class AnswerRelevanceV3(dspy.Signature):
    """
    Determine how the candidate's message relates to the last interview question.
    Do not output reasoning — return only the classification label.
    """

    last_question_asked: str = dspy.InputField(
        desc="The most recent question the interviewer asked."
    )
    user_message: str = dspy.InputField(
        desc="The candidate's response."
    )
    classification: Literal["relevant", "irrelevant", "candidate_question"] = dspy.OutputField(
        desc="Exactly one of: relevant, irrelevant, candidate_question."
    )


REGISTRY: dict[str, type[dspy.Signature]] = {
    "v1_baseline": AnswerRelevanceV1,
    "v2_cot_literal": AnswerRelevanceV2,
    "v3_no_reasoning": AnswerRelevanceV3,
}

DEFAULT = "v1_baseline"
