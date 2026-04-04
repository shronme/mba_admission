import json

import dspy

from app.dspy.profile_agent import run_profile_agent


def _minimal_attrs() -> dict[str, str]:
    return {
        "core_identity": "I lead product teams in fintech.",
        "domain_base": "8 years in payments product management.",
        "core_strengths": "Execution and cross-functional leadership.",
        "differentiation_layer": "First-gen college graduate mentoring founders.",
        "intellectual_working_style": "Structured, hypothesis-driven decision making.",
        "core_tension": "Strong operator, limited formal finance toolkit.",
        "transferable_assets": "Building teams, GTM strategy, and analytics.",
        # Intentionally omit motivation — structural guardrails must still catch it.
    }


def test_run_profile_agent_does_not_mark_complete_with_missing_required_fields(monkeypatch) -> None:
    attrs = _minimal_attrs()
    assert "motivation" not in attrs

    def _fake_run(*args, **kwargs):
        return dspy.Prediction(
            is_complete="true",
            completeness_score="100",
            gaps_json=json.dumps([], ensure_ascii=False),
            synthesized_attributes_json=json.dumps({}, ensure_ascii=False),
        )

    monkeypatch.setattr("app.core.dspy_runtime.run_dspy_module", _fake_run)

    is_complete, gaps, _, score = run_profile_agent(attrs, use_openai=True, min_score=0)

    assert is_complete is False
    assert "motivation" in gaps
    assert score < 100


def test_run_profile_agent_caps_score_to_structural_progress(monkeypatch) -> None:
    attrs = _minimal_attrs()
    attrs["motivation"] = ""

    def _fake_run(*args, **kwargs):
        return dspy.Prediction(
            is_complete="false",
            completeness_score="95",
            gaps_json=json.dumps(["motivation"], ensure_ascii=False),
            synthesized_attributes_json=json.dumps({}, ensure_ascii=False),
        )

    monkeypatch.setattr("app.core.dspy_runtime.run_dspy_module", _fake_run)

    _, _, _, score = run_profile_agent(attrs, use_openai=True, min_score=0)

    # 7 / 8 required fields populated => 88%
    assert score == 88


def test_run_profile_agent_ignores_non_candidate_gap_keys_from_model(monkeypatch) -> None:
    """LLM may list schema keys like target_programs; step-4 only surfaces the 8 input attrs."""
    attrs = {**_minimal_attrs(), "motivation": "Authentic story about impact and timing."}

    def _fake_run(*args, **kwargs):
        return dspy.Prediction(
            is_complete="false",
            completeness_score="88",
            gaps_json=json.dumps(["target_programs"], ensure_ascii=False),
            synthesized_attributes_json=json.dumps({}, ensure_ascii=False),
        )

    monkeypatch.setattr("app.core.dspy_runtime.run_dspy_module", _fake_run)

    is_complete, gaps, _, _ = run_profile_agent(attrs, use_openai=True, min_score=0)

    assert is_complete is True
    assert gaps == []
