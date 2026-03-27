"""Slugs for intake "target program" — mapped to coarse `ProgramType` on the candidate row."""

from __future__ import annotations

from app.db.enums import ProgramType

# Keys are stored in `candidate_profiles.grad_program_focus` (stable API contract).
GRAD_PROGRAM_FOCUS_TO_TYPE: dict[str, ProgramType] = {
    # MBA / business master’s
    "mba_full_time": ProgramType.MBA,
    "mba_part_time": ProgramType.MBA,
    "executive_mba": ProgramType.MBA,
    "online_mba": ProgramType.MBA,
    "deferred_mba": ProgramType.MBA,
    "dual_mba": ProgramType.MBA,
    "master_in_management": ProgramType.GRAD,
    "mim_europe": ProgramType.GRAD,
    "ms_business_analytics": ProgramType.GRAD,
    "ms_finance": ProgramType.GRAD,
    "mfin_quant": ProgramType.GRAD,
    "master_of_accounting": ProgramType.GRAD,
    "ms_marketing": ProgramType.GRAD,
    "ms_supply_chain": ProgramType.GRAD,
    "ms_real_estate": ProgramType.GRAD,
    "ms_healthcare_administration": ProgramType.GRAD,
    "ms_management": ProgramType.GRAD,
    # Engineering / CS / data (master’s)
    "ms_computer_science": ProgramType.GRAD,
    "ms_data_science": ProgramType.GRAD,
    "ms_ai_ml": ProgramType.GRAD,
    "ms_engineering_general": ProgramType.GRAD,
    "meng": ProgramType.GRAD,
    "ms_electrical_engineering": ProgramType.GRAD,
    "ms_mechanical_engineering": ProgramType.GRAD,
    "ms_civil_engineering": ProgramType.GRAD,
    "ms_chemical_engineering": ProgramType.GRAD,
    "ms_biomedical_engineering": ProgramType.GRAD,
    "ms_aerospace_engineering": ProgramType.GRAD,
    "ms_materials_science": ProgramType.GRAD,
    "ms_industrial_engineering": ProgramType.GRAD,
    "ms_environmental_engineering": ProgramType.GRAD,
    "ms_energy": ProgramType.GRAD,
    "ms_statistics": ProgramType.GRAD,
    "ms_applied_math": ProgramType.GRAD,
    # Sciences & research master’s
    "ms_bioinformatics": ProgramType.GRAD,
    "ms_biotechnology": ProgramType.GRAD,
    "ms_physics": ProgramType.GRAD,
    "ms_chemistry": ProgramType.GRAD,
    "ms_neuroscience": ProgramType.GRAD,
    "ms_public_health_non_mph": ProgramType.GRAD,
    # PhD
    "phd_stem": ProgramType.PHD,
    "phd_engineering": ProgramType.PHD,
    "phd_computer_science": ProgramType.PHD,
    "phd_life_sciences": ProgramType.PHD,
    "phd_physical_sciences": ProgramType.PHD,
    "phd_social_sciences": ProgramType.PHD,
    "phd_humanities": ProgramType.PHD,
    "phd_business": ProgramType.PHD,
    "phd_economics": ProgramType.PHD,
    "phd_education": ProgramType.PHD,
    "phd_public_policy": ProgramType.PHD,
    # Policy, public affairs, professional master’s
    "mpp": ProgramType.GRAD,
    "mpa": ProgramType.GRAD,
    "mph": ProgramType.GRAD,
    "msw": ProgramType.GRAD,
    "mfa": ProgramType.GRAD,
    "ma_humanities": ProgramType.GRAD,
    "ma_social_sciences": ProgramType.GRAD,
    "med_education": ProgramType.GRAD,
    "ms_architecture": ProgramType.GRAD,
    "m_urban_planning": ProgramType.GRAD,
    "llm": ProgramType.OTHER,
    "jd": ProgramType.OTHER,
    "md": ProgramType.OTHER,
    "dental": ProgramType.OTHER,
    "pharmd": ProgramType.OTHER,
    "nursing_msn": ProgramType.GRAD,
    "dnp": ProgramType.GRAD,
    "postbac_premed": ProgramType.OTHER,
    # Undergraduate
    "bs_ba_undergraduate": ProgramType.UNDERGRAD,
    "transfer_undergraduate": ProgramType.UNDERGRAD,
    "other_undergraduate": ProgramType.UNDERGRAD,
    # Catch-all
    "other_graduate": ProgramType.OTHER,
    "still_deciding": ProgramType.OTHER,
}

ALLOWED_GRAD_PROGRAM_FOCUS: frozenset[str] = frozenset(GRAD_PROGRAM_FOCUS_TO_TYPE.keys())
