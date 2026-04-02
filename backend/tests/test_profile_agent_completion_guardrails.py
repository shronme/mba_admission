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
        "motivation": "Need formal training to scale impact as a GM.",
        "core_tension": "Strong operator, limited formal finance toolkit.",
        "transferable_assets": "Building teams, GTM strategy, and analytics.",
    }


def test_run_profile_agent_does_not_mark_complete_with_missing_required_fields(monkeypatch) -> None:
    attrs = _minimal_attrs()
    assert "risks" not in attrs

    def _fake_run(*args, **kwargs):
        return dspy.Prediction(
            is_complete="true",
            completeness_score="100",
            gaps_json=json.dumps([], ensure_ascii=False),
            synthesized_attributes_json=json.dumps({}, ensure_ascii=False),
        )

    monkeypatch.setattr("app.dspy.profile_agent.run_dspy_module", _fake_run)

    is_complete, gaps, _, score = run_profile_agent(attrs, use_openai=True, min_score=0)

    assert is_complete is False
    assert "risks" in gaps
    assert score < 100


def test_run_profile_agent_caps_score_to_structural_progress(monkeypatch) -> None:
    attrs = _minimal_attrs()
    attrs["risks"] = ""

    def _fake_run(*args, **kwargs):
        return dspy.Prediction(
            is_complete="false",
            completeness_score="95",
            gaps_json=json.dumps(["risks"], ensure_ascii=False),
            synthesized_attributes_json=json.dumps({}, ensure_ascii=False),
        )

    monkeypatch.setattr("app.dspy.profile_agent.run_dspy_module", _fake_run)

    _, _, _, score = run_profile_agent(attrs, use_openai=True, min_score=0)

    # 8 / 9 required fields populated => 89%
    assert score == 89
