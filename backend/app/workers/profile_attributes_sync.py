"""Sync merge of CandidateProfile.attributes for Celery workers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.candidate import CandidateProfile


def merge_profile_attributes_sync(
    session: Session,
    candidate_id: uuid.UUID,
    updates: dict[str, Any],
    *,
    overwrite: bool = False,
) -> CandidateProfile:
    result = session.execute(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id),
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = CandidateProfile(candidate_id=candidate_id, attributes={})
        session.add(profile)

    existing: dict[str, Any] = dict(profile.attributes or {})
    # Match CandidateRepository.merge_profile_attributes
    if overwrite:
        profile.attributes = {**existing, **updates}
    else:
        profile.attributes = {**updates, **existing}
    session.flush()
    return profile
