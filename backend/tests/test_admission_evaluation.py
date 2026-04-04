"""Admission evaluation service unit tests."""

from __future__ import annotations

import pytest

from app.dspy import admission_evaluation as aes


def test_dossier_sufficient_requires_overview_and_criteria() -> None:
    assert not aes.dossier_sufficient({})
    assert not aes.dossier_sufficient({"overview": "x" * 200})
    assert aes.dossier_sufficient(
        {
            "overview": "x" * 200,
            "evaluation_criteria": {"a": "1", "b": "2"},
        },
    )


def test_pick_similar_programs_empty_when_scores_high() -> None:
    primary = [{"program_slug": "mba_full_time", "admission_chance_1_100": 90}]
    out = aes.pick_similar_programs(
        primary_evaluations=primary,
        selected_keys={("Harvard University", "mba_full_time")},
        max_programs=3,
    )
    assert out == []


def test_pick_similar_programs_returns_catalog_alternates() -> None:
    primary = [{"program_slug": "mba_full_time", "admission_chance_1_100": 50}]
    selected = {("Stanford University", "mba_full_time")}
    out = aes.pick_similar_programs(
        primary_evaluations=primary,
        selected_keys=selected,
        max_programs=2,
    )
    assert len(out) >= 1
    assert all("school" in r and "program_slug" in r for r in out)
    assert all(r["program_slug"] == "mba_full_time" for r in out)
