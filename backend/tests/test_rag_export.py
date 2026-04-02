from __future__ import annotations

from app.dspy.rag_export import dossier_to_rag_records


def test_dossier_to_rag_records_sections_and_metadata() -> None:
    dossier = {
        "school": "Test School",
        "program": "MBA (Full-time)",
        "cycle_year": 2026,
        "overview": "Short overview text.",
        "evaluation_criteria": {"academics": "Strong GPA preferred."},
        "fit_signals": {"strong_fit": ["Quant background"]},
        "notes": ["Extra note"],
    }
    meta = {"program_slug": "mba_full_time", "source_file": "/tmp/x.json"}
    records = dossier_to_rag_records(dossier, metadata=meta)
    sections = {r["metadata"]["section"] for r in records}
    assert "overview" in sections
    assert "evaluation_criteria" in sections
    assert "fit_signals" in sections
    assert "notes" in sections
    assert all(r["id"] for r in records)
    first = records[0]
    assert first["metadata"]["program_slug"] == "mba_full_time"
    assert first["metadata"]["school"] == "Test School"


def test_dossier_to_rag_records_skips_empty() -> None:
    dossier = {"school": "X", "program": "Y", "overview": "", "evaluation_criteria": {}}
    records = dossier_to_rag_records(dossier, metadata={})
    texts = [r["text"] for r in records]
    assert not any(t.strip() == "" for t in texts)
