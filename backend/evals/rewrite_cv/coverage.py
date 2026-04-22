"""
Coverage metric for `rewrite_cv`: does the rewritten CV still contain the key
structured fields from the source? (FR-7)

This is intentionally simple and deterministic — a normalized substring match
per field, with a small set of equivalence rules (e.g. em-dash vs hyphen,
collapsed whitespace, case-insensitive) so the coverage check is stable under
mock-mode rewrites that preserve the full source text.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from evals.rewrite_cv.fixtures import CVFixture


def _normalize(s: str) -> str:
    """Lowercase, NFKD-normalize, collapse whitespace, unify dashes."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    # Unify en-dash / em-dash / hyphen variants so "Mar 2021 – Dec 2022" and
    # "Mar 2021 - Dec 2022" score the same.
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\u2012", "-")
    s = re.sub(r"\s+", " ", s.strip().lower())
    return s


def _contains(hay: str, needle: str) -> bool:
    """Case-insensitive, whitespace-tolerant substring match."""
    h = _normalize(hay)
    n = _normalize(needle)
    if not n:
        return True
    return n in h


@dataclass(frozen=True)
class FixtureCoverage:
    fixture_name: str
    total_fields: int
    found_fields: int
    missing: tuple[str, ...]

    @property
    def ratio(self) -> float:
        if self.total_fields == 0:
            return 1.0
        return self.found_fields / self.total_fields


def score_fixture(fixture: CVFixture, rewrite: str) -> FixtureCoverage:
    """Check how many structured fields from `fixture` appear in `rewrite`."""
    expected: list[tuple[str, str]] = []

    for role in fixture.roles:
        expected.append((f"role_title::{role.title}", role.title))
        expected.append((f"role_company::{role.title}@{role.company}", role.company))
        # Compact date range representation that tolerates dash variants.
        expected.append(
            (
                f"role_dates::{role.title}::{role.start}-{role.end}",
                f"{role.start} - {role.end}",
            )
        )

    for edu in fixture.education:
        expected.append((f"edu_institution::{edu.institution}", edu.institution))
        expected.append((f"edu_degree::{edu.institution}::{edu.degree}", edu.degree))
        expected.append((f"edu_year::{edu.institution}::{edu.year}", edu.year))

    missing: list[str] = []
    found = 0
    for label, needle in expected:
        if _contains(rewrite, needle):
            found += 1
        else:
            missing.append(label)

    return FixtureCoverage(
        fixture_name=fixture.name,
        total_fields=len(expected),
        found_fields=found,
        missing=tuple(missing),
    )
