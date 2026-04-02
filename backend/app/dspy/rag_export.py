from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:32]


def _json_compact(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(obj)


def dossier_to_rag_records(
    dossier: dict[str, Any],
    *,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Split a program dossier dict into section-sized records suitable for embedding (RAG).

    Each record: {"id", "text", "metadata"} where metadata merges the caller's metadata with
    section-specific keys.
    """
    school = str(dossier.get("school") or metadata.get("school") or "")
    program = str(dossier.get("program") or metadata.get("program_label") or "")
    base_meta = {**metadata, "school": school, "program": program}

    sections: list[tuple[str, Any]] = [
        ("overview", dossier.get("overview")),
        ("application_components", dossier.get("application_components")),
        ("evaluation_criteria", dossier.get("evaluation_criteria")),
        ("class_profile", dossier.get("class_profile")),
        ("costs_and_funding", dossier.get("costs_and_funding")),
        ("outcomes", dossier.get("outcomes")),
        ("fit_signals", dossier.get("fit_signals")),
        ("international_applicants", dossier.get("international_applicants")),
        ("sources", dossier.get("sources")),
        ("notes", dossier.get("notes")),
    ]

    records: list[dict[str, Any]] = []
    for section_key, content in sections:
        if content is None:
            continue
        if isinstance(content, str) and not content.strip():
            continue
        if isinstance(content, (list, dict)) and not content:
            continue

        if isinstance(content, str):
            text_body = content.strip()
        else:
            text_body = _json_compact(content)

        if not text_body:
            continue

        text = f"{section_key.replace('_', ' ').title()}\n\n{text_body}"
        rid = _stable_id(school, program, section_key, text_body[:2000])
        rec_meta = {**base_meta, "section": section_key}
        records.append({"id": rid, "text": text, "metadata": rec_meta})

    return records
