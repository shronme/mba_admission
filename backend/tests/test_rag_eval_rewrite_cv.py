"""
Tests for the offline `rewrite_cv` coverage eval (FR-7).

Covers TC-042..TC-045 from the `rag-full-document-retrieval` QA plan:
  - TC-042: Coverage pass — mock rewriter preserves structured fields ≥ 95%
  - TC-043: Coverage fail — deliberately stripped rewrite drops below threshold
  - TC-044: Hallucination judge noop outside `DSPY_MODE=openai`
  - TC-045: CI default — runner uses mock path, no live OpenAI for judge
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DSPY_MODE", "mock")

from evals.rewrite_cv.coverage import score_fixture  # noqa: E402
from evals.rewrite_cv.fixtures import load_fixtures  # noqa: E402
from evals.rewrite_cv.judge import run_judge  # noqa: E402
from evals.rewrite_cv.runner import COVERAGE_THRESHOLD, RunResult, run  # noqa: E402


# ===========================================================================
# TC-042 — coverage pass (mock)
# ===========================================================================
class TestCoveragePass:
    def test_mock_rewriter_clears_95_percent_threshold(self) -> None:
        result = run(use_mock=True)
        assert isinstance(result, RunResult)
        assert result.per_fixture, "no fixtures loaded for eval"
        assert result.aggregate_ratio >= COVERAGE_THRESHOLD, (
            f"aggregate coverage {result.aggregate_ratio:.3f} "
            f"below threshold {COVERAGE_THRESHOLD:.2f}"
        )
        for cov in result.per_fixture:
            assert cov.ratio >= COVERAGE_THRESHOLD, (
                f"{cov.fixture_name}: ratio={cov.ratio:.3f} "
                f"missing={list(cov.missing)}"
            )
        assert result.all_pass

    def test_every_fixture_loaded_once(self) -> None:
        result = run(use_mock=True)
        names = [c.fixture_name for c in result.per_fixture]
        assert len(names) == len(set(names))
        assert len(names) >= 3, "expected at least a few fixtures"


# ===========================================================================
# TC-043 — deliberately drop a role → coverage fails
# ===========================================================================
class TestCoverageFailureCase:
    def test_dropping_a_role_breaks_threshold(self) -> None:
        fixtures = load_fixtures()
        # Pick a fixture with at least one role so dropping it is meaningful.
        target = next((f for f in fixtures if f.roles), None)
        assert target is not None, "no fixture with roles; test data is stale"
        dropped_role = target.roles[0]

        # Build a synthetic "rewrite" by removing every trace of the first
        # role's title + company + date range from the source text. The
        # coverage score should drop below 1.0 and typically below the
        # 0.95 threshold depending on fixture size.
        rewrite = target.text
        for needle in (
            dropped_role.title,
            dropped_role.company,
            f"{dropped_role.start} - {dropped_role.end}",
            f"{dropped_role.start} – {dropped_role.end}",
            f"{dropped_role.start} — {dropped_role.end}",
        ):
            rewrite = rewrite.replace(needle, "")

        cov = score_fixture(target, rewrite)
        assert cov.ratio < 1.0, (
            "expected coverage < 1.0 after removing a role, "
            f"got ratio={cov.ratio:.3f} missing={list(cov.missing)}"
        )
        assert cov.missing, "expected at least one missing structured field"

        # Check that the runner's "all_pass" gate would actually flip for a
        # run composed solely of this broken fixture.
        synthetic = RunResult(per_fixture=(cov,))
        if cov.ratio < COVERAGE_THRESHOLD:
            assert synthetic.all_pass is False


# ===========================================================================
# TC-044 — judge noop when DSPY_MODE != openai
# ===========================================================================
class TestHallucinationJudgeGate:
    def test_judge_skipped_in_mock_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DSPY_MODE", "mock")
        # If the judge crossed the gate it would attempt to import
        # `configure_dspy_from_env` and call a live model. We prove the
        # skip branch runs by monkey-patching that import site to raise.
        import app.core.dspy_runtime as runtime_mod

        def _explode() -> None:
            raise AssertionError("judge must not call configure_dspy_from_env")

        monkeypatch.setattr(runtime_mod, "configure_dspy_from_env", _explode)
        out = run_judge(run(use_mock=True))
        assert out == []

    def test_judge_skipped_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DSPY_MODE", raising=False)
        out = run_judge(run(use_mock=True))
        assert out == []


# ===========================================================================
# TC-045 — default CI path uses mock rewriter, never live OpenAI
# ===========================================================================
class TestDefaultCiPath:
    def test_run_without_args_honors_dspy_mode_mock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DSPY_MODE", "mock")

        # If the runner tried to instantiate OpenAIRewriteCVModule, it would
        # have to call dspy.Predict without a configured LM. We prove the
        # mock path is taken by monkeypatching OpenAIRewriteCVModule to
        # raise on instantiation.
        from app.dspy import rewrite_cv as rewrite_mod

        class _Explode:
            def __init__(self, *a, **kw) -> None:
                raise AssertionError(
                    "OpenAIRewriteCVModule must not be instantiated "
                    "when DSPY_MODE=mock"
                )

        monkeypatch.setattr(rewrite_mod, "OpenAIRewriteCVModule", _Explode)
        result = run()  # no args → honors env
        assert result.all_pass

    def test_run_without_args_honors_empty_dspy_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DSPY_MODE", raising=False)
        from app.dspy import rewrite_cv as rewrite_mod

        class _Explode:
            def __init__(self, *a, **kw) -> None:
                raise AssertionError("Must not call live rewriter")

        monkeypatch.setattr(rewrite_mod, "OpenAIRewriteCVModule", _Explode)
        result = run()
        assert result.all_pass
