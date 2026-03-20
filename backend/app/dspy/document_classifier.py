"""
Document type classification — two implementations:

- ``OpenAIDocumentClassifier``: DSPy + LLM (DSPY_MODE=openai)
- ``StaticDocumentClassifier``:  keyword heuristics, no LLM (DSPY_MODE=mock)
"""

from __future__ import annotations

import dspy

from app.db.enums import DocumentType

_ALLOWED_TYPES = ", ".join(t.value for t in DocumentType)


class DocumentClassificationSignature(dspy.Signature):
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

    document_text = dspy.InputField(desc="Full or partial text extracted from the document")
    document_type = dspy.OutputField(desc=f"One of: {_ALLOWED_TYPES}")
    reasoning = dspy.OutputField(desc="Brief explanation of the classification decision")


class OpenAIDocumentClassifier(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(DocumentClassificationSignature)

    def forward(self, document_text: str) -> dspy.Prediction:  # type: ignore[override]
        return self._predict(document_text=document_text)


# ---------------------------------------------------------------------------
# Keyword heuristics for mock / offline mode
# ---------------------------------------------------------------------------

_CV_KEYWORDS = frozenset(
    [
        "resume",
        "curriculum vitae",
        "work experience",
        "employment history",
        "professional experience",
        "skills",
        "bachelor",
        "master of",
        "university of",
        "gpa",
    ]
)
_LIFE_STORY_KEYWORDS = frozenset(
    [
        "personal statement",
        "statement of purpose",
        "life story",
        "my journey",
        "growing up",
        "i was born",
        "my childhood",
        "who i am",
        "my passion",
        "motivated me",
    ]
)
_REC_KEYWORDS = frozenset(
    [
        "recommendation",
        "to whom it may concern",
        "dear admissions",
        "i have known",
        "i have had the pleasure",
        "pleased to recommend",
        "letter of recommendation",
        "referee",
        "sincerely",
        "this letter",
    ]
)
_GRADE_KEYWORDS = frozenset(
    [
        "transcript",
        "academic record",
        "grade point average",
        "cumulative gpa",
        "semester",
        "credits",
        "course",
        "grade",
        "pass",
        "fail",
    ]
)


def _keyword_score(text_lower: str, keywords: frozenset[str]) -> int:
    return sum(1 for kw in keywords if kw in text_lower)


class StaticDocumentClassifier:
    """Deterministic keyword-based fallback used when DSPY_MODE=mock."""

    def __call__(self, *, document_text: str) -> DocumentType:
        t = (document_text or "").lower()
        scores: dict[DocumentType, int] = {
            DocumentType.CV: _keyword_score(t, _CV_KEYWORDS),
            DocumentType.LIFE_STORY: _keyword_score(t, _LIFE_STORY_KEYWORDS),
            DocumentType.RECOMMENDATION_LETTER: _keyword_score(t, _REC_KEYWORDS),
            DocumentType.GRADE_SHEET: _keyword_score(t, _GRADE_KEYWORDS),
        }
        best_type = max(scores, key=lambda k: scores[k])
        return best_type if scores[best_type] > 0 else DocumentType.UNCLASSIFIED
