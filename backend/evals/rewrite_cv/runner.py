"""
Runner for the offline `rewrite_cv` coverage eval (FR-7).

For each fixture under `backend/evals/fixtures/cv/`:
  1. Instantiate the mock rewriter (`MockRewriteCVModule`) — default for CI.
  2. Invoke it with the fixture CV text (no life story / profile / dossier).
  3. Score the rewrite against the structured metadata (roles, companies,
     date ranges, education) via `score_fixture`.
  4. Aggregate per-fixture coverage and fail when any fixture scores below
     the `COVERAGE_THRESHOLD`.

When `DSPY_MODE=openai`, an additional LLM-judge pass runs to flag
hallucinations (see `judge.py`). Without the env var set, the judge logs a
"skipped" line and exits successfully.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from evals.rewrite_cv.coverage import FixtureCoverage, score_fixture
from evals.rewrite_cv.fixtures import load_fixtures

logger = logging.getLogger(__name__)

COVERAGE_THRESHOLD = 0.95


@dataclass(frozen=True)
class RunResult:
    per_fixture: tuple[FixtureCoverage, ...]

    @property
    def all_pass(self) -> bool:
        return all(c.ratio >= COVERAGE_THRESHOLD for c in self.per_fixture)

    @property
    def aggregate_ratio(self) -> float:
        if not self.per_fixture:
            return 1.0
        total = sum(c.total_fields for c in self.per_fixture)
        found = sum(c.found_fields for c in self.per_fixture)
        return (found / total) if total else 1.0


def run(*, use_mock: bool | None = None) -> RunResult:
    """
    Run the coverage eval across all fixtures.

    When `use_mock` is None (default), honors `DSPY_MODE`: mock unless the
    env var is explicitly `openai`. The mock rewriter preserves the source
    CV verbatim, which is what the ≥95% field-coverage gate expects.
    """
    # Local import so module-level `import evals.rewrite_cv` doesn't eagerly
    # load DSPy before `configure_dspy_from_env()` has run in the parent
    # process.
    from app.dspy.rewrite_cv import MockRewriteCVModule, OpenAIRewriteCVModule

    if use_mock is None:
        use_mock = (os.getenv("DSPY_MODE") or "").lower() != "openai"

    module = MockRewriteCVModule() if use_mock else OpenAIRewriteCVModule()

    results: list[FixtureCoverage] = []
    for fixture in load_fixtures():
        pred = module(
            cv_text=fixture.text,
            life_story="",
            profile_json="",
            school_dossier="",
            target_school="",
            emphasis="",
        )
        rewrite = str(getattr(pred, "rewritten_cv", "") or "")
        cov = score_fixture(fixture, rewrite)
        results.append(cov)
        logger.info(
            "rewrite_cv_eval fixture=%s coverage=%.3f missing=%s",
            cov.fixture_name,
            cov.ratio,
            list(cov.missing),
        )

    return RunResult(per_fixture=tuple(results))


def print_report(result: RunResult) -> None:
    """Pretty-print a per-fixture coverage report suitable for CI logs."""
    print()
    print(f"rewrite_cv coverage eval — threshold = {COVERAGE_THRESHOLD:.2f}")
    print("-" * 60)
    for cov in result.per_fixture:
        mark = "PASS" if cov.ratio >= COVERAGE_THRESHOLD else "FAIL"
        print(
            f"[{mark}] {cov.fixture_name:<34} "
            f"coverage={cov.ratio:.3f} ({cov.found_fields}/{cov.total_fields})"
        )
        if cov.missing:
            for m in cov.missing:
                print(f"        missing: {m}")
    print("-" * 60)
    print(f"aggregate coverage: {result.aggregate_ratio:.3f}")
    print(f"overall: {'PASS' if result.all_pass else 'FAIL'}")
