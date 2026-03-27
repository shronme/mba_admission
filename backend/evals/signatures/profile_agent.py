"""
Signature variants for ProfileAgent (ProfileCompletenessSignature).

Variants differ in how the scoring rubric is surfaced, whether the
completeness_score field is present, and how the synthesis output is
described. MIPROv2 optimises the instruction text within each variant.

REGISTRY maps name → signature class.
DEFAULT is the name of the production-equivalent variant.
"""
from __future__ import annotations

import dspy

from app.dspy.profile_agent import SYNTHESIZED_ATTRIBUTES

_SYNTHESIZED_KEYS = ", ".join(SYNTHESIZED_ATTRIBUTES)


class ProfileAgentV1(dspy.Signature):
    """
    You are a senior MBA admissions consultant evaluating whether a candidate's
    profile has sufficient information to proceed to school research.

    A profile is COMPLETE when ALL 9 candidate-input attributes have meaningful,
    specific content — not vague summaries, single words, or placeholders.

    Additionally, synthesize the 5 derived attributes (strategy, narrative_direction,
    key_positioning, emphasis_areas, downplay_areas) from the existing profile data.

    Return:
    - is_complete: 'true' or 'false'
    - completeness_score: integer 0–100 representing overall profile quality.
      Score each of the 9 candidate-input attributes from 0–11 (11 points each,
      total 99 + 1 rounding point = 100 max):
        0  = attribute is absent
        4  = present but vague (single sentence, generic, no specifics)
        8  = good content but could be richer or more specific
        11 = excellent: specific, concrete, well-articulated
      Sum the scores across all 9 attributes. 100 = truly complete and polished.
    - gaps_json: JSON array of candidate-input attribute keys that are missing or
      too thin. Empty array [] if complete.
    - synthesized_attributes_json: JSON object with values for all 5 synthesized
      attributes, derived from the available profile data. Provide best-effort
      synthesis even when the profile is incomplete.
    """

    profile_attributes_json: str = dspy.InputField(
        desc="Current profile attributes as a JSON object."
    )
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object mapping each attribute key to a description of what good content looks like."
    )

    is_complete: str = dspy.OutputField(
        desc="'true' if the profile is complete, 'false' otherwise."
    )
    completeness_score: str = dspy.OutputField(
        desc="Integer 0–100 representing overall profile quality. 100 means all 9 attributes are fully articulated."
    )
    gaps_json: str = dspy.OutputField(
        desc="JSON array of candidate-input attribute keys that are missing or insufficient. Empty array [] if complete."
    )
    synthesized_attributes_json: str = dspy.OutputField(
        desc=(
            f"JSON object with synthesized values for: {_SYNTHESIZED_KEYS}. "
            "Base synthesis on whatever profile data is available."
        )
    )


class ProfileAgentV2(dspy.Signature):
    """
    Evaluate a candidate's MBA profile for completeness and synthesize strategic insights.

    Step 1 — Score each of the 9 candidate-input attributes 0–11:
      0  = absent
      4  = vague / single word / placeholder
      8  = solid but not fully specific
      11 = excellent: concrete evidence, specific details, well-articulated
    Sum to get completeness_score (0–100). Mark is_complete='true' only if score ≥ 88.

    Step 2 — List any attribute with score < 8 in gaps_json.

    Step 3 — Synthesize the 5 strategy attributes from whatever data is present.
    Even for an incomplete profile, provide best-effort synthesis.
    """

    profile_attributes_json: str = dspy.InputField(
        desc="Current profile attributes as a JSON object."
    )
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object mapping each attribute key to a description of what good content looks like."
    )

    completeness_score: str = dspy.OutputField(
        desc="Integer 0–100. Score each of the 9 attributes 0–11 and sum."
    )
    is_complete: str = dspy.OutputField(
        desc="'true' if completeness_score >= 88 and no gaps remain, 'false' otherwise."
    )
    gaps_json: str = dspy.OutputField(
        desc=(
            "JSON array of candidate-input attribute keys scoring below 8. "
            "Must be a valid JSON array. Use [] if no gaps."
        )
    )
    synthesized_attributes_json: str = dspy.OutputField(
        desc=(
            f"Valid JSON object with exactly these keys: {_SYNTHESIZED_KEYS}. "
            "Synthesize from available profile data; do not leave any key empty."
        )
    )


class ProfileAgentV3(dspy.Signature):
    """
    Evaluate an MBA candidate profile for completeness.

    Return is_complete, gaps_json listing any thin or absent attributes,
    and synthesized_attributes_json with strategic synthesis. Omit the
    completeness_score to keep the output concise.
    """

    profile_attributes_json: str = dspy.InputField(
        desc="Current profile attributes as a JSON object."
    )
    attribute_schema_json: str = dspy.InputField(
        desc="JSON object: attribute_key → description of what good content looks like."
    )

    is_complete: str = dspy.OutputField(
        desc="'true' if all 9 candidate-input attributes have specific, meaningful content."
    )
    gaps_json: str = dspy.OutputField(
        desc="JSON array of attribute keys that are absent or too thin. Use [] if none."
    )
    synthesized_attributes_json: str = dspy.OutputField(
        desc=(
            f"JSON object with keys: {_SYNTHESIZED_KEYS}. "
            "Derive from available profile data."
        )
    )


REGISTRY: dict[str, type[dspy.Signature]] = {
    "v1_baseline": ProfileAgentV1,
    "v2_threshold_explicit": ProfileAgentV2,
    "v3_no_score": ProfileAgentV3,
}

DEFAULT = "v2_threshold_explicit"
