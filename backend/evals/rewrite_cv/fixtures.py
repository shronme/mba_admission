"""
Fixture loader for the offline `rewrite_cv` evaluation.

Reads the text files under `backend/evals/fixtures/cv/` and the sidecar
`metadata.json`, and returns a list of `CVFixture` dataclasses that the
runner can iterate over.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Role:
    title: str
    company: str
    start: str
    end: str


@dataclass(frozen=True)
class Education:
    institution: str
    degree: str
    year: str


@dataclass(frozen=True)
class CVFixture:
    name: str  # fixture filename, e.g. "fixture_01_short.txt"
    candidate_name: str
    text: str
    roles: tuple[Role, ...]
    education: tuple[Education, ...]


_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "cv"
_METADATA_PATH = _FIXTURES_DIR / "metadata.json"


def _load_metadata() -> dict[str, dict]:
    if not _METADATA_PATH.exists():
        raise FileNotFoundError(f"Missing metadata.json at {_METADATA_PATH}")
    return json.loads(_METADATA_PATH.read_text(encoding="utf-8"))


def load_fixtures() -> list[CVFixture]:
    """Load all CV fixtures + metadata into a deterministic ordered list."""
    metadata = _load_metadata()
    out: list[CVFixture] = []
    for name in sorted(metadata.keys()):
        meta = metadata[name]
        path = _FIXTURES_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Fixture text missing: {path}")
        text = path.read_text(encoding="utf-8")
        roles = tuple(
            Role(
                title=r["title"],
                company=r["company"],
                start=r["start"],
                end=r["end"],
            )
            for r in meta.get("roles", [])
        )
        education = tuple(
            Education(
                institution=e["institution"],
                degree=e["degree"],
                year=e["year"],
            )
            for e in meta.get("education", [])
        )
        out.append(
            CVFixture(
                name=name,
                candidate_name=meta.get("candidate_name", ""),
                text=text,
                roles=roles,
                education=education,
            )
        )
    return out


def iter_fixtures() -> Iterator[CVFixture]:
    yield from load_fixtures()
