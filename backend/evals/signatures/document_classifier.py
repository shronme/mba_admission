"""
Signature variants for DocumentClassifier.

Variants differ in field structure, type constraints, and output field presence.
MIPROv2 will optimise the instruction text — docstrings are minimal starting hints.

REGISTRY maps name → signature class.
DEFAULT is the name of the production-equivalent variant.
"""
from __future__ import annotations

from typing import Literal

import dspy

_ALLOWED_TYPES = "cv, life_story, recommendation_letter, grade_sheet, irrelevant, unclassified"

_ALLOWED_LITERAL = Literal[
    "cv",
    "life_story",
    "recommendation_letter",
    "grade_sheet",
    "irrelevant",
    "unclassified",
]


class DocumentClassifierV1(dspy.Signature):
    """
    Classify an uploaded admissions document into exactly one of the allowed types.

    Allowed document_type values:
    - cv: résumé or CV listing work experience, education, skills
    - life_story: personal statement, autobiographical narrative, life essay
    - recommendation_letter: letter written by a third party recommending the applicant
    - grade_sheet: academic transcript, grade report, or similar academic record
    - irrelevant: document unrelated to a graduate-school application
    - unclassified: cannot be determined from the text
    """

    document_text: str = dspy.InputField(
        desc="Full or partial text extracted from the document."
    )
    document_type: str = dspy.OutputField(
        desc=f"One of: {_ALLOWED_TYPES}"
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation of the classification decision."
    )


class DocumentClassifierV2(dspy.Signature):
    """
    Classify an admissions document into one of six types.

    Think step-by-step: identify the author (self vs. third party), the content
    structure (list vs. narrative vs. table), and the dominant purpose before
    outputting the type.
    """

    document_text: str = dspy.InputField(
        desc="Full or partial text extracted from the document."
    )
    reasoning: str = dspy.OutputField(
        desc=(
            "Step-by-step reasoning: (1) who authored the document? "
            "(2) what is the dominant structure and purpose? "
            "(3) which type does that map to?"
        )
    )
    document_type: _ALLOWED_LITERAL = dspy.OutputField(  # type: ignore[valid-type]
        desc=f"Exactly one of: {_ALLOWED_TYPES}"
    )


class DocumentClassifierV3(dspy.Signature):
    """
    Classify an admissions document. Return only the type label, no reasoning.
    """

    document_text: str = dspy.InputField(
        desc="Full or partial text extracted from the document."
    )
    document_type: _ALLOWED_LITERAL = dspy.OutputField(  # type: ignore[valid-type]
        desc=f"Exactly one of: {_ALLOWED_TYPES}"
    )


REGISTRY: dict[str, type[dspy.Signature]] = {
    "v1_baseline": DocumentClassifierV1,
    "v2_cot_literal": DocumentClassifierV2,
    "v3_no_reasoning": DocumentClassifierV3,
}

DEFAULT = "v1_baseline"
