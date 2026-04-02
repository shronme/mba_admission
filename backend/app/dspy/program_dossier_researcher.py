from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import dspy


def _safe_json_loads(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    # Common failure mode: model wraps JSON in markdown fences.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


@dataclass(frozen=True)
class ProgramDossier:
    school: str
    program: str
    dossier: dict[str, Any]


class ProgramDossierResearchSignature(dspy.Signature):
    """
    You are an expert graduate admissions consultant and researcher.

    Given a school and a specific graduate degree/program target, produce a compact but complete
    "program dossier" containing the information an admissions consultant needs to assess fit.

    Requirements:
    - Output MUST be valid JSON (no markdown fences).
    - Prefer official sources (school/program admissions pages) when possible.
    - Include citations as URLs in `sources`.
    - If a detail is unknown or varies by track, set the value to null and note it in `notes`.
    - Be explicit about: admissions criteria, process, deadlines/rounds, tests, essays, LORs,
      interview, prerequisites, class profile/selection signals, costs, scholarships, and
      any international applicant specifics.

    JSON shape:
    {
      "school": string,
      "program": string,
      "cycle_year": number | null,
      "overview": string,
      "application_components": {
        "application_portal": string | null,
        "deadlines": [{"round": string, "date": string | null, "notes": string | null}],
        "requirements": {
          "transcripts": string | null,
          "resume": string | null,
          "essays": [{"name": string, "prompt_summary": string | null, "word_limit": string | null}],
          "recommendations": {"count": number | null, "who": string | null, "notes": string | null},
          "test_scores": {"gre": string | null, "gmat": string | null, "toefl_ielts": string | null, "waivers": string | null},
          "interview": {"format": string | null, "by_invitation": boolean | null, "notes": string | null},
          "prerequisites": [{"topic": string, "details": string | null}]
        }
      },
      "evaluation_criteria": {
        "academics": string | null,
        "professional_experience": string | null,
        "leadership_impact": string | null,
        "goals_fit": string | null,
        "community_culture_fit": string | null,
        "research_fit": string | null,
        "other": [string]
      },
      "class_profile": {
        "cohort_size": number | null,
        "avg_gpa": string | null,
        "avg_gre": string | null,
        "avg_gmat": string | null,
        "work_experience": string | null,
        "demographics": string | null,
        "notes": string | null
      },
      "costs_and_funding": {
        "tuition": string | null,
        "fees": string | null,
        "estimated_total_cost": string | null,
        "scholarships": string | null,
        "assistantships": string | null,
        "loans": string | null
      },
      "outcomes": {
        "career_outcomes": string | null,
        "internships": string | null,
        "placements": string | null
      },
      "fit_signals": {
        "strong_fit": [string],
        "weak_fit_risks": [string],
        "how_to_position": [string]
      },
      "international_applicants": {
        "language_requirements": string | null,
        "visa_i20_support": string | null,
        "notes": string | null
      },
      "sources": [{"title": string | null, "url": string}],
      "notes": [string]
    }
    """

    school: str = dspy.InputField(desc="School name, e.g. 'Harvard Business School'.")
    program: str = dspy.InputField(desc="Specific program/degree name, e.g. 'MBA (Full-time)' or 'MS in Data Science'.")
    cycle_year: int = dspy.InputField(desc="Admissions cycle year (e.g. 2026). Use current year if uncertain.")

    program_dossier_json: str = dspy.OutputField(desc="Valid JSON only (no markdown).")


class ProgramDossierResearcher(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self._predict = dspy.Predict(ProgramDossierResearchSignature)

    def forward(  # type: ignore[override]
        self, *, school: str, program: str, cycle_year: int
    ) -> dspy.Prediction:
        return self._predict(school=school, program=program, cycle_year=cycle_year)


def run_program_dossier_researcher(
    *,
    school: str,
    program: str,
    cycle_year: int,
) -> ProgramDossier:
    """
    Run the DSPy module and return a validated best-effort dossier dict.

    Notes:
    - Validation is intentionally light: we only require a JSON object and patch in `school`/`program`.
    - Callers should still persist raw text if they want for debugging.
    """
    from app.core.dspy_runtime import run_dspy_module

    module = ProgramDossierResearcher()
    pred = run_dspy_module(module, school=school, program=program, cycle_year=int(cycle_year))
    raw = str(getattr(pred, "program_dossier_json", "") or "")
    obj = _safe_json_loads(raw) or {}
    obj.setdefault("school", school)
    obj.setdefault("program", program)
    if "cycle_year" not in obj:
        obj["cycle_year"] = int(cycle_year)
    return ProgramDossier(school=school, program=program, dossier=obj)

