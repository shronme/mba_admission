from __future__ import annotations

import json

import dspy

from app.dspy.profile_agent import (
    CANDIDATE_INPUT_ATTRIBUTES,
    PROFILE_ATTRIBUTE_SCHEMA,
    _ATTRIBUTE_SCHEMA_JSON,
)

# ---------------------------------------------------------------------------
# DSPy module — OpenAI
# ---------------------------------------------------------------------------


class ProfileAttributeExtractorSignature(dspy.Signature):
    """
    You are an expert MBA admissions analyst.

    Given extracted text from a candidate's document, identify and extract
    information that maps to the defined profile attributes.

    Rules:
    - Only extract what is clearly supported by the document text.
    - For each attribute, write a concise, specific value — not generic.
    - Write every attribute value in clear professional English. If the document
      is in another language, translate and summarize faithfully; do not paste
      untranslated source-language paragraphs as the stored value.
    - If a document attribute would IMPROVE on the existing profile value
      (more specific, more accurate, richer detail), include it even if
      that key already exists in the current profile.
    - Return {} if no relevant attribute information is found.
    - Do not fabricate or infer beyond what the document states.
    """

    document_text: str = dspy.InputField(
        desc="Full extracted text from the uploaded document."
    )
    document_type: str = dspy.InputField(
        desc="Classified type of the document (e.g. cv, life_story, recommendation_letter, grade_sheet)."
    )
    current_profile_json: str = dspy.InputField(
        desc="Existing profile attributes as JSON. Use this to understand what is already captured."
    )
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object mapping attribute keys to descriptions of what good content looks like."
    )

    attribute_updates_json: str = dspy.OutputField(
        desc=(
            "Valid JSON object with extracted/updated profile attribute values in English. "
            "Keys must be from the attribute schema. Return {} if nothing relevant found."
        )
    )


class OpenAIProfileAttributeExtractor(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(ProfileAttributeExtractorSignature)

    def forward(  # type: ignore[override]
        self,
        document_text: str,
        document_type: str,
        current_profile_json: str,
        attribute_schema_json: str,
    ) -> dspy.Prediction:
        return self._predict(
            document_text=document_text,
            document_type=document_type,
            current_profile_json=current_profile_json,
            attribute_schema_json=attribute_schema_json,
        )


# ---------------------------------------------------------------------------
# DSPy module — Mock (keyword heuristics)
# ---------------------------------------------------------------------------

_CV_KEYWORDS: dict[str, list[str]] = {
    "core_identity": ["senior", "director", "manager", "lead", "head of", "officer", "vp", "principal"],
    "domain_base": ["government", "public sector", "military", "ngo", "finance", "technology", "consulting", "healthcare"],
    "core_strengths": ["led", "managed", "built", "launched", "delivered", "drove", "achieved", "implemented"],
    "transferable_assets": ["strategic", "cross-functional", "stakeholder", "p&l", "budget", "team", "program"],
    "risks": ["gap", "pivot", "change"],
}

_LIFE_STORY_KEYWORDS: dict[str, list[str]] = {
    "core_identity": ["i am", "i've always", "my mission", "i believe"],
    "differentiation_layer": ["resilience", "adversity", "community", "values", "identity", "lgbtq", "family", "illness"],
    "motivation": ["why mba", "decided to", "realised", "realized", "turning point", "goal", "aspire"],
    "core_tension": ["pivot", "transition", "shift", "change direction", "leave behind", "move into"],
    "intellectual_working_style": ["analytical", "systematic", "evidence", "data-driven", "curious", "problem-solver"],
}


class MockProfileAttributeExtractor(dspy.Module):
    """
    Deterministic extractor for mock/test mode.

    Uses simple keyword heuristics to populate profile attributes from document text.
    Only fills keys not already present in the current profile.
    """

    def forward(  # type: ignore[override]
        self,
        document_text: str,
        document_type: str,
        current_profile_json: str,
        attribute_schema_json: str,
    ) -> dspy.Prediction:
        try:
            existing: dict = json.loads(current_profile_json) if current_profile_json else {}
        except (json.JSONDecodeError, ValueError):
            existing = {}

        text_lower = document_text.lower()
        updates: dict[str, str] = {}

        keyword_map = _CV_KEYWORDS if "cv" in document_type.lower() else _LIFE_STORY_KEYWORDS

        for attr_key, keywords in keyword_map.items():
            if any(kw in text_lower for kw in keywords):
                # Extract the first 300 chars of document as value for that attribute.
                snippet = document_text.strip()[:300]
                updates[attr_key] = snippet

        return dspy.Prediction(
            attribute_updates_json=json.dumps(updates, ensure_ascii=False),
        )


# ---------------------------------------------------------------------------
# Convenience runner (sync, used from Celery tasks)
# ---------------------------------------------------------------------------


def run_profile_attribute_extractor(
    document_text: str,
    document_type: str,
    current_attributes: dict | None,
    *,
    use_openai: bool = False,
) -> dict:
    """
    Extract profile attribute updates from a document.

    Returns a dict of attribute key → new value (may be empty).
    """
    from app.core.dspy_runtime import run_dspy_module

    current_json = json.dumps(current_attributes or {}, ensure_ascii=False)
    extractor = (
        OpenAIProfileAttributeExtractor() if use_openai else MockProfileAttributeExtractor()
    )
    pred = run_dspy_module(
        extractor,
        document_text=document_text,
        document_type=document_type,
        current_profile_json=current_json,
        attribute_schema_json=_ATTRIBUTE_SCHEMA_JSON,
    )

    raw = str(getattr(pred, "attribute_updates_json", "") or "")
    try:
        updates = json.loads(raw)
        if not isinstance(updates, dict):
            return {}
        # Restrict to valid attribute keys
        return {k: v for k, v in updates.items() if k in CANDIDATE_INPUT_ATTRIBUTES}
    except (json.JSONDecodeError, ValueError):
        return {}
