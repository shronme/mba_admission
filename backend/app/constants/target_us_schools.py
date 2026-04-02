"""Curated US graduate programs for intake school selection (catalog-backed)."""

from __future__ import annotations

from app.constants.graduate_programs_catalog import (
    ALLOWED_INTAKE_SCHOOL_NAMES,
    INTAKE_OTHER_SCHOOL_SENTINEL,
    ORDERED_SCHOOL_NAMES,
)

# Research / scripts: catalog names only (no synthetic intake token).
ALL_TARGET_US_SCHOOLS: list[str] = ORDERED_SCHOOL_NAMES

ALLOWED_TARGET_US_SCHOOLS: frozenset[str] = ALLOWED_INTAKE_SCHOOL_NAMES | frozenset({INTAKE_OTHER_SCHOOL_SENTINEL})

# Must match `CandidateIntakeUpdate.target_schools` max length and API `max_selections`.
INTAKE_TARGET_SCHOOLS_MAX_SELECTIONS = 100
