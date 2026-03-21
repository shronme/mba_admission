"""
Metric functions for all evaluated DSPy modules.

Each metric follows the DSPy convention:

    def metric(example: dspy.Example, pred: dspy.Prediction, trace=None) -> bool | float

- Return a bool for pass/fail metrics (dspy.Evaluate aggregates as accuracy).
- Return a float in [0, 1] for partial-credit metrics.

The `trace` parameter is passed by DSPy's optimizer during compilation — it
can be inspected for bootstrapped demonstrations but is not used here.
"""
from __future__ import annotations

import json
import logging

import dspy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification metrics (AnswerRelevance, DocumentClassifier, IntentClassifier)
# ---------------------------------------------------------------------------


def answer_relevance_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> bool:
    """Exact-match accuracy on the classification field."""
    expected = str(getattr(example, "classification", "")).strip().lower()
    actual = str(getattr(pred, "classification", "")).strip().lower()
    return expected == actual


def document_classifier_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> bool:
    """Exact-match accuracy on the document_type field."""
    expected = str(getattr(example, "document_type", "")).strip().lower()
    actual = str(getattr(pred, "document_type", "")).strip().lower()
    return expected == actual


def intent_classifier_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> bool:
    """Exact-match accuracy on the intent field."""
    expected = str(getattr(example, "intent", "")).strip().lower()
    actual = str(getattr(pred, "intent", "")).strip().lower()
    return expected == actual


# ---------------------------------------------------------------------------
# Intake interviewer metrics
# ---------------------------------------------------------------------------


def _parse_profile_json(raw: str) -> dict:
    """Parse profile_updates_json; return {} on failure."""
    try:
        result = json.loads(raw or "{}")
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def intake_profile_key_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> float:
    """
    Fraction of expected profile keys that appear in profile_updates_json.

    If expected_profile_keys is empty the example only tests that the JSON
    is valid (not that specific keys are extracted) — we grant full credit as
    long as profile_updates_json is parseable.
    """
    expected_keys: frozenset[str] = getattr(example, "expected_profile_keys", frozenset())
    raw_json: str = getattr(pred, "profile_updates_json", "{}")

    updates = _parse_profile_json(raw_json)

    # Unparseable JSON is always a failure
    if raw_json and raw_json.strip() not in ("{}", "") and not updates and not expected_keys:
        try:
            json.loads(raw_json)
        except (json.JSONDecodeError, ValueError):
            logger.debug("profile_updates_json parse failure: %s", raw_json[:200])
            return 0.0

    if not expected_keys:
        # No specific keys required — just check JSON validity
        try:
            json.loads(raw_json or "{}")
            return 1.0
        except (json.JSONDecodeError, ValueError):
            return 0.0

    found = sum(1 for k in expected_keys if k in updates and updates[k])
    return found / len(expected_keys)


def intake_response_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> bool:
    """The response field must be non-empty."""
    response = str(getattr(pred, "response", "")).strip()
    return bool(response)


def intake_composite_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> float:
    """
    Weighted composite metric for intake interviewer turns:

    - 70%: profile key extraction accuracy  (intake_profile_key_metric)
    - 30%: response presence                (intake_response_metric)

    Returns a float in [0, 1].
    """
    key_score = intake_profile_key_metric(example, pred, trace)
    response_score = float(intake_response_metric(example, pred, trace))
    return round(0.7 * key_score + 0.3 * response_score, 4)


# ---------------------------------------------------------------------------
# Profile agent metrics
# ---------------------------------------------------------------------------


def _parse_gaps_json(raw: str) -> frozenset[str]:
    """Parse gaps_json; return empty frozenset on failure."""
    try:
        result = json.loads(raw or "[]")
        return frozenset(result) if isinstance(result, list) else frozenset()
    except (json.JSONDecodeError, ValueError):
        return frozenset()


def profile_is_complete_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> bool:
    """Exact-match on is_complete ('true' or 'false')."""
    expected = str(getattr(example, "expected_is_complete", "")).strip().lower()
    actual = str(getattr(pred, "is_complete", "")).strip().lower()
    return expected == actual


def profile_gaps_f1_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> float:
    """
    F1 score between the expected gaps set and the predicted gaps set.

    Returns 1.0 when both sets are identical, 0.0 when they have no overlap.
    Gracefully handles parse failures (treats as empty set).
    """
    expected: frozenset[str] = getattr(example, "expected_gaps", frozenset())
    predicted: frozenset[str] = _parse_gaps_json(getattr(pred, "gaps_json", "[]"))

    if not expected and not predicted:
        return 1.0

    tp = len(expected & predicted)
    precision = tp / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = tp / len(expected) if expected else (1.0 if not predicted else 0.0)

    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def profile_synthesis_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> float:
    """
    Fraction of the 5 synthesized attributes that are present and non-empty
    in synthesized_attributes_json.
    """
    from app.dspy.profile_agent import SYNTHESIZED_ATTRIBUTES

    raw = getattr(pred, "synthesized_attributes_json", "{}")
    try:
        synthesized = json.loads(raw or "{}")
        if not isinstance(synthesized, dict):
            synthesized = {}
    except (json.JSONDecodeError, ValueError):
        synthesized = {}

    filled = sum(1 for k in SYNTHESIZED_ATTRIBUTES if synthesized.get(k, "").strip())
    return round(filled / len(SYNTHESIZED_ATTRIBUTES), 4)


def profile_composite_metric(
    example: dspy.Example, pred: dspy.Prediction, trace=None
) -> float:
    """
    Weighted composite metric for the profile agent:

    - 40%: is_complete correctness
    - 35%: gaps F1 score
    - 25%: synthesis completeness (fraction of 5 synthesized keys non-empty)

    Returns a float in [0, 1].
    """
    complete_score = float(profile_is_complete_metric(example, pred, trace))
    gaps_score = profile_gaps_f1_metric(example, pred, trace)
    synthesis_score = profile_synthesis_metric(example, pred, trace)
    return round(
        0.40 * complete_score + 0.35 * gaps_score + 0.25 * synthesis_score,
        4,
    )


# ---------------------------------------------------------------------------
# Registry — used by the CLI to look up metrics by module name
# ---------------------------------------------------------------------------

METRICS: dict[str, object] = {
    "answer_relevance": answer_relevance_metric,
    "document_classifier": document_classifier_metric,
    "intent_classifier": intent_classifier_metric,
    "intake_interviewer": intake_composite_metric,
    "profile_agent": profile_composite_metric,
}
