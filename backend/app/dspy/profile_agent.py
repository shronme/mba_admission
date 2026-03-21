from __future__ import annotations

import json

import dspy

# ---------------------------------------------------------------------------
# Shared attribute schema
# ---------------------------------------------------------------------------

# The 9 attributes that must be filled through candidate interaction (interview
# answers and/or uploaded documents).
CANDIDATE_INPUT_ATTRIBUTES: list[str] = [
    "core_identity",
    "domain_base",
    "core_strengths",
    "differentiation_layer",
    "intellectual_working_style",
    "motivation",
    "core_tension",
    "transferable_assets",
    "risks",
]

# The 5 attributes synthesized by the Profile Agent from the candidate-input data.
SYNTHESIZED_ATTRIBUTES: list[str] = [
    "strategy",
    "narrative_direction",
    "key_positioning",
    "emphasis_areas",
    "downplay_areas",
]

ALL_ATTRIBUTES: list[str] = CANDIDATE_INPUT_ATTRIBUTES + SYNTHESIZED_ATTRIBUTES

# Descriptions drive both the interviewer (what to ask about) and the
# completeness checker (what "good" looks like for each attribute).
PROFILE_ATTRIBUTE_SCHEMA: dict[str, str] = {
    "core_identity": (
        "Your professional identity — who you are as an operator, leader, or builder. "
        "A 1–2 sentence summary that captures your essence beyond your job title."
    ),
    "domain_base": (
        "Your primary professional domain, industry, and functional background. "
        "Include sector, seniority context, and breadth of exposure."
    ),
    "core_strengths": (
        "Your 3–6 key professional strengths with concrete evidence. "
        "Must be specific, not generic buzzwords."
    ),
    "differentiation_layer": (
        "What makes you distinctly human — personal resilience, values, community "
        "involvement, moral courage, or unique life experience beyond your professional record."
    ),
    "intellectual_working_style": (
        "How you think and work: your analytical style, decision-making approach, "
        "cross-domain thinking, and how you engage with complex problems."
    ),
    "motivation": (
        "Your core, authentic reason for pursuing an MBA now — specific, grounded "
        "in your story, not generic prestige or salary motives."
    ),
    "core_tension": (
        "The central tension or pivot in your trajectory — the gap between where you "
        "are and where you want to go. Should be honest and specific, not vague."
    ),
    "transferable_assets": (
        "Skills, experiences, and capabilities from your background that directly "
        "transfer to your target field or post-MBA goal."
    ),
    "risks": (
        "Honest risks in your application — credibility gaps, pivot concerns, profile "
        "weaknesses, or narratives that could undermine your case."
    ),
    "strategy": (
        "The recommended application strategy (e.g. Upgrade, Purpose Pivot, Hybrid) derived "
        "from the full profile. Should name the approach and explain the rationale."
    ),
    "narrative_direction": (
        "The through-line narrative that ties your past, current pivot, and future "
        "goals into one compelling arc."
    ),
    "key_positioning": (
        "How to position you against MBA applicant pools — a 1–2 sentence "
        "positioning statement that consultants would lead with."
    ),
    "emphasis_areas": (
        "What to amplify and lead with in essays and interviews — themes, stories, and "
        "proof points that should be front and centre."
    ),
    "downplay_areas": (
        "What to de-emphasise or handle carefully in the application to avoid undermining "
        "the overall narrative."
    ),
}

_ATTRIBUTE_SCHEMA_JSON: str = json.dumps(PROFILE_ATTRIBUTE_SCHEMA, ensure_ascii=False)


def get_profile_gaps(attributes: dict | None) -> list[str]:
    """
    Return candidate-input attribute keys that are absent or empty in `attributes`.

    This is a fast, no-LLM check used to steer the interviewer each turn.
    The LLM-backed ProfileAgent is called separately for a quality-aware
    completeness decision.
    """
    attrs = attributes or {}
    return [key for key in CANDIDATE_INPUT_ATTRIBUTES if not attrs.get(key)]


# ---------------------------------------------------------------------------
# DSPy module — OpenAI
# ---------------------------------------------------------------------------


class ProfileCompletenessSignature(dspy.Signature):
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

    is_complete: str = dspy.OutputField(desc="'true' if the profile is complete, 'false' otherwise.")
    completeness_score: str = dspy.OutputField(
        desc="Integer 0–100 representing overall profile quality. 100 means all 9 attributes are fully articulated."
    )
    gaps_json: str = dspy.OutputField(
        desc="JSON array of candidate-input attribute keys that are missing or insufficient. Empty array [] if complete."
    )
    synthesized_attributes_json: str = dspy.OutputField(
        desc=(
            "JSON object with synthesized values for: strategy, narrative_direction, "
            "key_positioning, emphasis_areas, downplay_areas. Base synthesis on whatever "
            "profile data is available."
        )
    )


class OpenAIProfileAgent(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(ProfileCompletenessSignature)

    def forward(  # type: ignore[override]
        self,
        profile_attributes_json: str,
        attribute_schema_json: str,
    ) -> dspy.Prediction:
        return self._predict(
            profile_attributes_json=profile_attributes_json,
            attribute_schema_json=attribute_schema_json,
        )


# ---------------------------------------------------------------------------
# DSPy module — Mock
# ---------------------------------------------------------------------------


class MockProfileAgent(dspy.Module):
    """
    Deterministic completeness checker for mock/test mode.

    - Marks complete when all 9 candidate-input keys are non-empty.
    - Synthesizes placeholder values for the 5 derived attributes from whatever
      data is present, so callers always receive the full expected structure.
    """

    def forward(  # type: ignore[override]
        self,
        profile_attributes_json: str,
        attribute_schema_json: str,
    ) -> dspy.Prediction:
        try:
            attrs: dict = json.loads(profile_attributes_json) if profile_attributes_json else {}
        except (json.JSONDecodeError, ValueError):
            attrs = {}

        # Exclude reserved internal keys from gap/score calculations.
        attrs = {k: v for k, v in attrs.items() if not k.startswith("_")}

        gaps = [key for key in CANDIDATE_INPUT_ATTRIBUTES if not attrs.get(key)]
        is_complete = len(gaps) == 0

        # Score: 11 points per filled attribute (9 attrs × 11 = 99, rounded to 100 when complete).
        filled_count = len(CANDIDATE_INPUT_ATTRIBUTES) - len(gaps)
        score = min(100, round(filled_count / len(CANDIDATE_INPUT_ATTRIBUTES) * 100))

        synthesized: dict[str, str] = {}
        if attrs.get("core_identity") or attrs.get("domain_base"):
            synthesized["strategy"] = "Upgrade strategy based on existing domain expertise."
            synthesized["narrative_direction"] = (
                "Operator with strong domain foundation pivoting toward broader impact."
            )
            synthesized["key_positioning"] = (
                "High-accountability leader with transferable systems-building capability."
            )
            synthesized["emphasis_areas"] = "Leadership scale, measurable impact, values, resilience."
            synthesized["downplay_areas"] = "Generic impact statements, prestige-driven motives."
        else:
            for key in SYNTHESIZED_ATTRIBUTES:
                synthesized[key] = ""

        return dspy.Prediction(
            is_complete="true" if is_complete else "false",
            completeness_score=str(score),
            gaps_json=json.dumps(gaps, ensure_ascii=False),
            synthesized_attributes_json=json.dumps(synthesized, ensure_ascii=False),
        )


# ---------------------------------------------------------------------------
# Convenience runner (sync, used from pipeline + Celery tasks)
# ---------------------------------------------------------------------------


def run_profile_agent(
    attributes: dict | None,
    *,
    use_openai: bool = False,
) -> tuple[bool, list[str], dict, int]:
    """
    Run the ProfileAgent and return (is_complete, gaps, synthesized_attrs, completeness_score).

    completeness_score is an integer 0–100 reflecting overall profile quality.
    Uses OpenAI when `use_openai=True` and OPENAI_API_KEY is set, otherwise mock.
    """
    from app.core.dspy_runtime import run_dspy_module

    # Strip internal reserved keys (e.g. _completeness_score) before sending to
    # the LLM so they don't pollute the completeness assessment.
    clean_attrs = {k: v for k, v in (attributes or {}).items() if not k.startswith("_")}
    attrs_json = json.dumps(clean_attrs, ensure_ascii=False)
    agent = OpenAIProfileAgent() if use_openai else MockProfileAgent()
    pred = run_dspy_module(agent, profile_attributes_json=attrs_json, attribute_schema_json=_ATTRIBUTE_SCHEMA_JSON)

    raw_complete = str(getattr(pred, "is_complete", "false")).strip().lower()
    is_complete = raw_complete == "true"

    try:
        score = int(str(getattr(pred, "completeness_score", "0")).strip())
        score = max(0, min(100, score))
    except (ValueError, TypeError):
        # Fallback: proportion of filled candidate-input attributes.
        filled = sum(1 for k in CANDIDATE_INPUT_ATTRIBUTES if (attributes or {}).get(k))
        score = min(100, round(filled / len(CANDIDATE_INPUT_ATTRIBUTES) * 100))

    try:
        gaps: list[str] = json.loads(getattr(pred, "gaps_json", "[]") or "[]")
        if not isinstance(gaps, list):
            gaps = []
    except (json.JSONDecodeError, ValueError):
        gaps = get_profile_gaps(attributes)

    try:
        synthesized: dict = json.loads(getattr(pred, "synthesized_attributes_json", "{}") or "{}")
        if not isinstance(synthesized, dict):
            synthesized = {}
    except (json.JSONDecodeError, ValueError):
        synthesized = {}

    return is_complete, gaps, synthesized, score
