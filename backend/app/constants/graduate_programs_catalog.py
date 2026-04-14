"""Graduate program offerings per school — loaded from dossier research output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

_CATALOG_PATH: Final[Path] = Path(__file__).resolve().parent / "graduate_programs_by_school.json"

# Synthetic row for intake when the candidate’s school is not in the catalog (paired with `target_schools_other`).
INTAKE_OTHER_SCHOOL_SENTINEL: Final[str] = "__intake_other__"


def _load_schools_map() -> dict[str, list[dict[str, Any]]]:
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("schools")
    if not isinstance(raw, dict):
        raise ValueError("graduate_programs_by_school.json: missing or invalid 'schools' object")
    out: dict[str, list[dict[str, Any]]] = {}
    for name, entries in raw.items():
        school = str(name).strip()
        if not school:
            continue
        if not isinstance(entries, list):
            continue
        out[school] = [e for e in entries if isinstance(e, dict)]
    return out


PROGRAMS_BY_SCHOOL: dict[str, list[dict[str, Any]]] = _load_schools_map()
ORDERED_SCHOOL_NAMES: list[str] = sorted(PROGRAMS_BY_SCHOOL.keys())
ALLOWED_INTAKE_SCHOOL_NAMES: frozenset[str] = frozenset(PROGRAMS_BY_SCHOOL.keys())


def _load_ranked_school_names(*, programs_by_school: dict[str, list[dict[str, Any]]]) -> list[str]:
    """
    Ranked schools come from `school_rankings.entries` in `graduate_programs_by_school.json`.
    Only schools present in `PROGRAMS_BY_SCHOOL` are returned.
    """
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    sr = data.get("school_rankings")
    if not isinstance(sr, dict):
        return []
    entries = sr.get("entries")
    if not isinstance(entries, dict):
        return []

    rows: list[tuple[int, str]] = []
    for school_name, payload in entries.items():
        if not isinstance(payload, dict):
            continue
        if not isinstance(school_name, str):
            continue
        school = school_name.strip()
        if not school:
            continue
        if school not in programs_by_school:
            continue
        rank_raw = payload.get("rank")
        try:
            rank = int(rank_raw)
        except (TypeError, ValueError):
            continue
        rows.append((rank, school))

    # Sort by rank asc; deterministic tie-breaker alphabetical.
    rows.sort(key=lambda t: (t[0], t[1]))
    return [s for _, s in rows]


RANKED_SCHOOL_NAMES: list[str] = _load_ranked_school_names(programs_by_school=PROGRAMS_BY_SCHOOL)


def ranked_schools_offering_program(program_slug: str) -> list[str]:
    slug = (program_slug or "").strip()
    if not slug:
        return []
    out: list[str] = []
    for school in RANKED_SCHOOL_NAMES:
        if any(str(e.get("slug") or "").strip() == slug for e in PROGRAMS_BY_SCHOOL.get(school, [])):
            out.append(school)
    return out


def program_slugs_for_schools(school_names: list[str]) -> frozenset[str]:
    found: set[str] = set()
    for raw_name in school_names:
        name = raw_name.strip()
        if not name:
            continue
        for entry in PROGRAMS_BY_SCHOOL.get(name, ()):
            slug = entry.get("slug")
            if isinstance(slug, str) and slug.strip():
                found.add(slug.strip())
    return frozenset(found)
