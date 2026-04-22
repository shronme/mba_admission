"""
LLM-judge hallucination pass for the offline `rewrite_cv` eval (FR-7, T-15).

This is **gated** behind `DSPY_MODE=openai`. In the default CI mode
(`DSPY_MODE=mock` or unset) the judge is a no-op and simply logs that it
was skipped. When enabled, it runs a DSPy `Predict` that inspects each
(source, rewrite) pair and returns a JSON list of ungrounded facts, which
the runner surfaces in the CLI output.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import dspy

from evals.rewrite_cv.fixtures import load_fixtures
from evals.rewrite_cv.runner import RunResult

logger = logging.getLogger(__name__)


class _HallucinationJudgeSignature(dspy.Signature):
    """
    Compare an MBA candidate's source CV to a rewrite and list any facts in
    the rewrite that are NOT grounded in the source.

    A "fact" is a concrete, checkable claim: role title, company, date
    range, education entry, award, quantitative metric, or location. Do NOT
    flag rephrasings, tone changes, or reordering. Only flag claims whose
    factual content is absent from or contradicted by the source.

    Output: a JSON array of short strings, each describing one ungrounded
    claim. Output `[]` when the rewrite is fully grounded.
    """

    source_text: str = dspy.InputField(desc="The original CV body.")
    rewrite_text: str = dspy.InputField(desc="The rewritten CV body.")
    hallucinated_facts_json: str = dspy.OutputField(
        desc='JSON array of ungrounded claims, e.g. [] or ["Invented MBA from Stanford"].'
    )


@dataclass(frozen=True)
class FixtureJudgeResult:
    fixture_name: str
    hallucinated_facts: tuple[str, ...]


def _judge_enabled() -> bool:
    return (os.getenv("DSPY_MODE") or "").lower() == "openai"


def run_judge(result: RunResult) -> list[FixtureJudgeResult]:
    """
    Run the LLM judge on each fixture when enabled. Returns the per-fixture
    list of ungrounded facts, or an empty list (with a skip log line) when
    `DSPY_MODE != openai`.
    """
    if not _judge_enabled():
        logger.info("LLM judge skipped (DSPY_MODE != openai)")
        return []

    # Local imports so enabling the judge doesn't pull DSPy LM config into
    # the default mock-mode runner path.
    from app.core.dspy_runtime import configure_dspy_from_env
    from app.dspy.rewrite_cv import OpenAIRewriteCVModule

    configure_dspy_from_env()
    judge = dspy.Predict(_HallucinationJudgeSignature)
    rewriter = OpenAIRewriteCVModule()

    out: list[FixtureJudgeResult] = []
    for fixture in load_fixtures():
        pred = rewriter(
            cv_text=fixture.text,
            life_story="",
            profile_json="",
            school_dossier="",
            target_school="",
            emphasis="",
        )
        rewrite = str(getattr(pred, "rewritten_cv", "") or "")
        verdict = judge(source_text=fixture.text, rewrite_text=rewrite)
        raw = str(getattr(verdict, "hallucinated_facts_json", "[]") or "[]")
        try:
            facts_raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "rewrite_cv_judge parse_failure fixture=%s raw=%r",
                fixture.name,
                raw[:200],
            )
            facts_raw = []
        facts = tuple(str(f) for f in facts_raw if isinstance(f, (str, int, float)))
        logger.info(
            "rewrite_cv_judge fixture=%s hallucinations=%s",
            fixture.name,
            list(facts),
        )
        out.append(FixtureJudgeResult(fixture_name=fixture.name, hallucinated_facts=facts))

    # Only use `result` indirectly — the judge may eventually cross-check
    # against the coverage output (e.g. elevate missed-but-not-hallucinated
    # signal), but for now we just ensure the import is meaningful for the
    # signature and avoids "unused parameter" lint noise.
    _ = result
    return out
