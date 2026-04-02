from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import dspy

from app.constants.grad_program_focus import ALLOWED_GRAD_PROGRAM_FOCUS

# Slugs excluded from per-school discovery (undergrad, meta, or non-degree).
_DOSSIER_DISCOVERY_EXCLUDE: frozenset[str] = frozenset(
    {
        "bs_ba_undergraduate",
        "transfer_undergraduate",
        "other_undergraduate",
        "still_deciding",
        "other_graduate",
        "postbac_premed",
    }
)

DOSSIER_DISCOVERY_SLUGS: frozenset[str] = frozenset(
    sorted(ALLOWED_GRAD_PROGRAM_FOCUS - _DOSSIER_DISCOVERY_EXCLUDE)
)


def _safe_json_loads_any(raw: str) -> Any | None:
    """Parse JSON object or array; strip common markdown fences."""
    text = (raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


@dataclass(frozen=True)
class SchoolProgramOffering:
    slug: str
    label: str
    confidence: str
    notes: str | None


class SchoolProgramOfferingsSignature(dspy.Signature):
    """
    You are an expert on U.S. graduate admissions and university program catalogs.

    Given a school (university or named professional school) and a closed list of program-focus
    slugs (stable API identifiers), decide which slugs represent graduate programs that school
    plausibly offers or is widely known for (degree-granting: master's, PhD, JD, MD, etc., as
    applicable to each slug).

    Rules:
    - Output MUST be valid JSON (no markdown fences): a JSON array only.
    - Include ONLY slugs from the provided list that the school offers or strongly plausibly offers.
    - For each included slug, set "label" to a concise human display name (e.g. "MBA (Full-time)").
    - Set "confidence" to one of: "high", "medium", "low". Omit uncertain slugs or use "low" sparingly.
    - Set "notes" to a short string or null (e.g. joint-degree caveat).
    - If the input is a business school name, still consider STEM/policy/etc. slugs only if that
      school or its parent university clearly offers them under the same umbrella you were given.
    - Prefer official program pages in your reasoning; do not invent slugs.

    JSON array element shape:
    {"slug": string, "label": string, "confidence": "high"|"medium"|"low", "notes": string|null}
    """

    school: str = dspy.InputField(desc="School name, e.g. 'MIT Sloan School of Management'.")
    cycle_year: int = dspy.InputField(desc="Admissions cycle year for context.")
    slugs_json: str = dspy.InputField(
        desc='JSON array of allowed slug strings, e.g. ["mba_full_time","ms_finance"].'
    )

    programs_json: str = dspy.OutputField(desc="JSON array only (no markdown).")


class SchoolProgramOfferingsResearcher(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(SchoolProgramOfferingsSignature)

    def forward(  # type: ignore[override]
        self, *, school: str, cycle_year: int, slugs_json: str
    ) -> dspy.Prediction:
        return self._predict(school=school, cycle_year=cycle_year, slugs_json=slugs_json)


def _normalize_offerings(
    raw: list[Any],
    *,
    allowed: frozenset[str],
) -> list[SchoolProgramOffering]:
    out: list[SchoolProgramOffering] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug or slug not in allowed or slug in seen:
            continue
        label = str(item.get("label") or "").strip() or slug
        conf = str(item.get("confidence") or "medium").strip().lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        notes_val = item.get("notes")
        notes = None if notes_val is None else str(notes_val).strip() or None
        seen.add(slug)
        out.append(
            SchoolProgramOffering(slug=slug, label=label, confidence=conf, notes=notes)
        )
    return out


def run_school_program_offerings(
    *,
    school: str,
    cycle_year: int,
    allowed_slugs: frozenset[str] | None = None,
) -> list[SchoolProgramOffering]:
    """
    Run the DSPy module and return validated offerings (slugs ⊆ allowed_slugs).
    """
    allow = allowed_slugs if allowed_slugs is not None else DOSSIER_DISCOVERY_SLUGS
    slugs_json = json.dumps(sorted(allow), ensure_ascii=False)

    from app.core.dspy_runtime import run_dspy_module

    module = SchoolProgramOfferingsResearcher()
    pred = run_dspy_module(
        module,
        school=school,
        cycle_year=int(cycle_year),
        slugs_json=slugs_json,
    )
    raw_text = str(getattr(pred, "programs_json", "") or "")
    parsed = _safe_json_loads_any(raw_text)
    if parsed is None:
        return []
    if isinstance(parsed, dict) and "programs" in parsed:
        inner = parsed.get("programs")
        raw_list = inner if isinstance(inner, list) else []
    elif isinstance(parsed, list):
        raw_list = parsed
    else:
        raw_list = []

    return _normalize_offerings(raw_list, allowed=allow)


def run_school_program_offerings_openai(
    *,
    school: str,
    cycle_year: int,
    model: str,
    api_key: str,
    allowed_slugs: frozenset[str] | None = None,
) -> list[SchoolProgramOffering]:
    """
    Same discovery as `run_school_program_offerings`, using a temporary OpenAI (LiteLLM) LM.

    Restores the previous `dspy.settings.lm` and `DSPY_MODEL` env after the call.
    """
    prev_lm = getattr(dspy.settings, "lm", None)
    prev_dspy_model = os.environ.get("DSPY_MODEL")
    try:
        lm = dspy.LM(model, api_key=api_key)
        dspy.configure(lm=lm)
        os.environ["DSPY_MODEL"] = model
        return run_school_program_offerings(
            school=school,
            cycle_year=cycle_year,
            allowed_slugs=allowed_slugs,
        )
    finally:
        if prev_lm is not None:
            dspy.configure(lm=prev_lm)
        if prev_dspy_model is not None:
            os.environ["DSPY_MODEL"] = prev_dspy_model
        else:
            os.environ.pop("DSPY_MODEL", None)
