"""Curated US MBA programs for intake school selection."""

from __future__ import annotations

# Two ordered groups: first block is listed before the second in API/UI ordering.
TIER_1_US_TARGET_SCHOOLS: tuple[str, ...] = (
    "Harvard Business School",
    "Stanford Graduate School of Business",
    "Wharton School (University of Pennsylvania)",
    "MIT Sloan School of Management",
    "Kellogg School of Management (Northwestern University)",
    "Chicago Booth School of Business",
    "Columbia Business School",
    "Haas School of Business (UC Berkeley)",
    "Yale School of Management",
    "Tuck School of Business (Dartmouth College)",
    "Fuqua School of Business (Duke University)",
    "NYU Stern School of Business",
    "Ross School of Business (University of Michigan)",
    "Darden School of Business (University of Virginia)",
    "UCLA Anderson School of Management",
)

TIER_2_US_TARGET_SCHOOLS: tuple[str, ...] = (
    "Johnson Graduate School of Management (Cornell University)",
    "Tepper School of Business (Carnegie Mellon University)",
    "Marshall School of Business (USC)",
    "McCombs School of Business (University of Texas at Austin)",
    "Kenan-Flagler Business School (UNC Chapel Hill)",
    "Kelley School of Business (Indiana University)",
    "Wisconsin School of Business (University of Wisconsin–Madison)",
    "McDonough School of Business (Georgetown University)",
    "Jones Graduate School of Business (Rice University)",
    "Owen Graduate School of Management (Vanderbilt University)",
    "Goizueta Business School (Emory University)",
    "Foster School of Business (University of Washington)",
    "Scheller College of Business (Georgia Institute of Technology)",
    "Simon Business School (University of Rochester)",
    "Mendoza College of Business (University of Notre Dame)",
    "Carroll School of Management (Boston College)",
    "Questrom School of Business (Boston University)",
    "Warrington College of Business (University of Florida)",
    "SMU Cox School of Business",
    "Herbert Business School (University of Miami)",
)

ALL_TARGET_US_SCHOOLS: tuple[str, ...] = TIER_1_US_TARGET_SCHOOLS + TIER_2_US_TARGET_SCHOOLS

ALLOWED_TARGET_US_SCHOOLS: frozenset[str] = frozenset(ALL_TARGET_US_SCHOOLS)

# Must match `CandidateIntakeUpdate.target_schools` max length and API `max_selections`.
INTAKE_TARGET_SCHOOLS_MAX_SELECTIONS = 24
