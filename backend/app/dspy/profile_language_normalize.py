from __future__ import annotations

import json

import dspy

from app.dspy.profile_agent import CANDIDATE_INPUT_ATTRIBUTES, SYNTHESIZED_ATTRIBUTES

# All string profile fields we keep in canonical English in the database.
PROFILE_ENGLISH_KEYS: frozenset[str] = frozenset(
    [*CANDIDATE_INPUT_ATTRIBUTES, *SYNTHESIZED_ATTRIBUTES, "target_programs"]
)


class ProfileEnglishNormalizeSignature(dspy.Signature):
    """
    You normalize MBA candidate profile attribute values to clear professional English.

    You receive a JSON object: keys are profile fields, values are prose (possibly
    Hebrew, Arabic, Spanish, etc., or already English).

    Return a JSON object with exactly the same keys. Each value must faithfully
    reflect the input in English — translate where needed; if already good English,
    keep meaning and tone with light editing only. Preserve proper nouns (people,
    schools, employers) in conventional English spelling when well known.

    Do not add or remove keys. Do not invent facts. Do not return empty strings
    unless the input was empty or whitespace-only.
    """

    attributes_subset_json: str = dspy.InputField(
        desc="JSON object: profile field keys to string values that need English normalization."
    )
    normalized_json: str = dspy.OutputField(
        desc="JSON object with the same keys as input; every value must be English prose."
    )


class OpenAIProfileEnglishNormalizer(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(ProfileEnglishNormalizeSignature)

    def forward(self, attributes_subset_json: str) -> dspy.Prediction:  # type: ignore[override]
        return self._predict(attributes_subset_json=attributes_subset_json)


def _subset_for_normalize(attributes: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in attributes.items():
        if k.startswith("_"):
            continue
        if k not in PROFILE_ENGLISH_KEYS:
            continue
        if isinstance(v, str) and v.strip():
            out[k] = v
    return out


def _parse_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def run_profile_attributes_english_normalize(
    attributes: dict | None,
    *,
    use_openai: bool = False,
) -> dict:
    """
    Return a copy of `attributes` with PROFILE_ENGLISH_KEYS string values in English.

    When `use_openai` is False or there is nothing to normalize, returns a shallow
    merge copy unchanged for those keys.
    """
    result: dict = {**(attributes or {})}
    subset = _subset_for_normalize(result)
    if not subset or not use_openai:
        return result

    from app.core.dspy_runtime import run_dspy_module

    module = OpenAIProfileEnglishNormalizer()
    pred = run_dspy_module(
        module,
        attributes_subset_json=json.dumps(subset, ensure_ascii=False),
    )
    normalized = _parse_json_object(str(getattr(pred, "normalized_json", "") or ""))
    if not normalized:
        return result

    for key in subset:
        val = normalized.get(key)
        if isinstance(val, str) and val.strip():
            result[key] = val.strip()
    return result
