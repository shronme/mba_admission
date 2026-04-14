"""
Admission evaluation: per-program research (Perplexity), optional OpenAI supplement,
structured evaluation JSON, and similar-program suggestions.

DSPy + LiteLLM; mock/offline output when API keys are not configured.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from typing import Any

import dspy

from app.constants.graduate_programs_catalog import (
    ORDERED_SCHOOL_NAMES,
    PROGRAMS_BY_SCHOOL,
    ranked_schools_offering_program,
)
from app.core.dspy_runtime import configure_dspy_from_env, run_dspy_module
from app.dspy.program_dossier_researcher import run_program_dossier_researcher

logger = logging.getLogger(__name__)


def program_display_label(school: str, program_slug: str) -> str:
    for e in PROGRAMS_BY_SCHOOL.get(school, []):
        if str(e.get("slug") or "") == program_slug:
            lab = e.get("label")
            return str(lab).strip() if lab else program_slug
    return program_slug.replace("_", " ").title()


def _configure_perplexity_lm() -> bool:
    api_key = (os.getenv("PERPLEXITY_API_KEY") or os.getenv("PERPLEXITYAI_API_KEY") or "").strip()
    if not api_key:
        return False
    model = (
        os.getenv("PERPLEXITY_MODEL")
        or os.getenv("DSPY_MODEL")
        or "perplexity/sonar-pro"
    )
    if not str(model).startswith("perplexity/"):
        model = "perplexity/sonar-pro"
    # Centralize LM configuration inside `app.core.dspy_runtime.configure_dspy_from_env()`.
    # Here we only ensure env vars are consistent for this run.
    os.environ["DSPY_MODE"] = "perplexity"
    os.environ["DSPY_MODEL"] = model
    return True


def _configure_openai_lm() -> bool:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return False
    model = os.getenv("OPENAI_EVAL_MODEL") or os.getenv("DSPY_MODEL") or "openai/gpt-4o-mini"
    if not str(model).startswith("openai/"):
        model = "openai/gpt-4o-mini"
    # Centralize LM configuration inside `app.core.dspy_runtime.configure_dspy_from_env()`.
    os.environ["DSPY_MODE"] = (os.getenv("DSPY_MODE") or "openai").strip() or "openai"
    os.environ["DSPY_MODEL"] = model
    return True


def dossier_sufficient(dossier: dict[str, Any]) -> bool:
    overview = str(dossier.get("overview") or "")
    ec = dossier.get("evaluation_criteria")
    return len(overview) > 180 and isinstance(ec, dict) and len(ec) >= 2


def research_program_dossier(*, school: str, program_label: str, cycle_year: int) -> dict[str, Any]:
    """Run Perplexity-backed dossier research; returns dossier dict."""
    if not _configure_perplexity_lm():
        logger.warning("admission_eval: Perplexity not configured; using mock dossier")
        return _mock_dossier(school, program_label, cycle_year)
    configure_dspy_from_env()
    try:
        pd = run_program_dossier_researcher(
            school=school, program=program_label, cycle_year=cycle_year
        )
        return pd.dossier
    except Exception as e:  # noqa: BLE001
        logger.exception("admission_eval: dossier research failed: %s", e)
        return _mock_dossier(school, program_label, cycle_year)


def supplement_with_openai(
    *,
    school: str,
    program_label: str,
    cycle_year: int,
    prior_summary: str,
) -> str:
    """Second-pass web-oriented research notes (OpenAI)."""
    if not _configure_openai_lm():
        return prior_summary + "\n\n[Supplement: mock — OpenAI not configured]"
    configure_dspy_from_env()

    class SupplementSig(dspy.Signature):
        """You are a graduate admissions researcher. Given partial notes, add concrete
        program-specific admissions criteria, class profile stats, and differentiators.
        Output plain text bullet summary (no JSON). Cite approximate sources in-line."""

        school: str = dspy.InputField()
        program: str = dspy.InputField()
        cycle_year: int = dspy.InputField()
        prior_notes: str = dspy.InputField()

        supplement_text: str = dspy.OutputField(desc="Plain text bullets")

    mod = dspy.Predict(SupplementSig)
    pred = run_dspy_module(
        mod,
        school=school,
        program=program_label,
        cycle_year=cycle_year,
        prior_notes=prior_summary[:12000],
    )
    return str(getattr(pred, "supplement_text", "") or "")


def _mock_dossier(school: str, program: str, cycle_year: int) -> dict[str, Any]:
    return {
        "school": school,
        "program": program,
        "cycle_year": cycle_year,
        "overview": f"Mock overview for {school} {program}. " * 15,
        "evaluation_criteria": {
            "academics": "Strong quantitative profile preferred.",
            "professional_experience": "Leadership and impact matter.",
            "goals_fit": "Clear post-program goals.",
        },
        "class_profile": {"avg_gmat": "720", "notes": "Selective cohort."},
        "sources": [],
        "notes": ["mock dossier"],
    }


def _safe_json_obj(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        o = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return o if isinstance(o, dict) else None


def evaluate_program_json(
    *,
    school: str,
    program_label: str,
    program_slug: str,
    dossier: dict[str, Any],
    candidate_profile_text: str,
    test_scores_text: str,
) -> dict[str, Any]:
    """Return evaluation dict aligned with consolidated results UI."""
    if not _configure_openai_lm():
        return _mock_evaluation(school, program_label, program_slug)

    configure_dspy_from_env()
    dossier_json = json.dumps(dossier, ensure_ascii=False)[:24000]

    class EvalSig(dspy.Signature):
        """You assess MBA/graduate admissions fit. Output valid JSON only (no markdown).

        JSON keys:
        - strengths: string[] (2-5 items)
        - weaknesses: string[] (2-5 items)
        - admission_chance_1_100: integer 1-100
        - admission_band: one of TARGET, PROBABLE, MODERATE, STRETCH (match score)
        - narrative_strategy: string (one paragraph)
        - priority_actions: string[] (2-4 short imperative items)
        """

        school: str = dspy.InputField()
        program: str = dspy.InputField()
        program_slug: str = dspy.InputField()
        dossier_json: str = dspy.InputField()
        candidate_profile: str = dspy.InputField()
        test_scores: str = dspy.InputField()

        evaluation_json: str = dspy.OutputField(desc="JSON object only")

    mod = dspy.Predict(EvalSig)
    pred = run_dspy_module(
        mod,
        school=school,
        program=program_label,
        program_slug=program_slug,
        dossier_json=dossier_json,
        candidate_profile=candidate_profile_text[:16000],
        test_scores=test_scores_text[:4000],
    )
    raw = str(getattr(pred, "evaluation_json", "") or "")
    parsed = _safe_json_obj(raw)
    if not parsed:
        return _mock_evaluation(school, program_label, program_slug)
    parsed.setdefault("school", school)
    parsed.setdefault("program_slug", program_slug)
    parsed.setdefault("program_display_name", program_label)
    return parsed


def _mock_evaluation(school: str, program_label: str, program_slug: str) -> dict[str, Any]:
    return {
        "school": school,
        "program_slug": program_slug,
        "program_display_name": program_label,
        "strengths": [f"Strong alignment with {school} peer set (mock).", "Clear professional trajectory (mock)."],
        "weaknesses": ["Narrative could be more specific (mock).", "Test optional context not shown (mock)."],
        "admission_chance_1_100": 72,
        "admission_band": "MODERATE",
        "narrative_strategy": "Emphasize leadership evidence and school-specific resources (mock).",
        "priority_actions": ["Tighten goals essay.", "Add quantified impact metrics.", "Connect to one research center."],
    }


def evaluate_extra_program_json(
    *,
    school: str,
    program_label: str,
    program_slug: str,
    dossier: dict[str, Any],
    candidate_profile_text: str,
) -> dict[str, Any]:
    if not _configure_openai_lm():
        return {
            "school": school,
            "program_display_name": program_label,
            "program_slug": program_slug,
            "key_match": "Mock alignment with your background.",
            "action_item": "Reach out to a student club in this area (mock).",
            "match_strength_1_100": 75,
            "admission_chance_1_100": 78,
            "meta": "Mock meta",
        }

    configure_dspy_from_env()
    dossier_json = json.dumps(dossier, ensure_ascii=False)[:12000]

    class ExtraSig(dspy.Signature):
        """Alternative program suggestion evaluation. JSON only, no markdown.

        Keys:
        - key_match: string
        - action_item: string
        - match_strength_1_100: int (1-100)
        - admission_chance_1_100: int (1-100)
        - meta: short location/format string
        """

        school: str = dspy.InputField()
        program: str = dspy.InputField()
        program_slug: str = dspy.InputField()
        dossier_json: str = dspy.InputField()
        candidate_profile: str = dspy.InputField()

        extra_json: str = dspy.OutputField(desc="JSON object only")

    mod = dspy.Predict(ExtraSig)
    pred = run_dspy_module(
        mod,
        school=school,
        program=program_label,
        program_slug=program_slug,
        dossier_json=dossier_json,
        candidate_profile=candidate_profile_text[:12000],
    )
    raw = str(getattr(pred, "extra_json", "") or "")
    parsed = _safe_json_obj(raw)
    if not parsed:
        return {
            "school": school,
            "program_display_name": program_label,
            "program_slug": program_slug,
            "key_match": "Could not parse model output (mock).",
            "action_item": "Review official program page (mock).",
            "match_strength_1_100": 70,
            "admission_chance_1_100": 70,
            "meta": "",
        }
    parsed.setdefault("school", school)
    parsed.setdefault("program_display_name", program_label)
    parsed.setdefault("program_slug", program_slug)
    return parsed


def pick_similar_programs(
    *,
    primary_evaluations: list[dict[str, Any]],
    selected_keys: set[tuple[str, str]],
    max_programs: int = 3,
) -> list[dict[str, str]]:
    """
    Deterministic fallback: for any primary program with chance < 85, suggest same program_slug
    at other schools from catalog until max_programs.
    """
    weak_slugs: set[str] = set()
    for row in primary_evaluations:
        try:
            ch = int(row.get("admission_chance_1_100") or 0)
        except (TypeError, ValueError):
            ch = 0
        if ch < 85:
            slug = str(row.get("program_slug") or "").strip()
            if slug:
                weak_slugs.add(slug)

    if not weak_slugs:
        return []

    out: list[dict[str, str]] = []
    for school in ORDERED_SCHOOL_NAMES:
        for slug in weak_slugs:
            key = (school, slug)
            if key in selected_keys or key in {(o["school"], o["program_slug"]) for o in out}:
                continue
            if not any(str(e.get("slug")) == slug for e in PROGRAMS_BY_SCHOOL.get(school, [])):
                continue
            label = program_display_label(school, slug)
            out.append({"school": school, "program_slug": slug, "program_display_name": label})
            if len(out) >= max_programs:
                return out
    return out


def ranked_random_program_candidates(
    *,
    program_slug: str,
    selected_keys: set[tuple[str, str]],
    rng: random.Random | None = None,
    max_programs: int | None = None,
) -> list[dict[str, str]]:
    """
    Build a randomized list of candidate (school, program_slug) from ranked schools that
    offer the given program, excluding any already-selected (school, slug) pairs.
    """
    slug = (program_slug or "").strip()
    if not slug:
        return []

    schools = list(ranked_schools_offering_program(slug))
    schools = [s for s in schools if (s, slug) not in selected_keys]
    if not schools:
        return []

    (rng or random).shuffle(schools)

    if isinstance(max_programs, int) and max_programs > 0:
        schools = schools[:max_programs]

    return [
        {
            "school": school,
            "program_slug": slug,
            "program_display_name": program_display_label(school, slug),
        }
        for school in schools
    ]


def format_profile_snapshot(attributes: dict[str, Any] | None) -> str:
    if not attributes:
        return ""
    safe = {k: v for k, v in attributes.items() if k not in ("admission_evaluation_job", "admission_evaluation_result")}
    try:
        return json.dumps(safe, ensure_ascii=False, indent=0)[:20000]
    except (TypeError, ValueError):
        return str(safe)[:20000]


def format_test_scores(attributes: dict[str, Any] | None) -> str:
    raw = (attributes or {}).get("intake_test_scores")
    if raw is None:
        return ""
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False)
    return str(raw)
