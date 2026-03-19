from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.enums import CandidateStatus, ProgramType
from app.db.models.candidate import Candidate, CandidateProfile
from app.repositories.base import BaseRepository


class CandidateRepository(BaseRepository):
    async def create_candidate(
        self,
        *,
        full_name: str,
        email: str | None = None,
        program_type: ProgramType = ProgramType.GRAD,
        status: CandidateStatus = CandidateStatus.ACTIVE,
        extra: dict | None = None,
    ) -> Candidate:
        c = Candidate(
            full_name=full_name,
            email=email,
            program_type=program_type,
            status=status,
            extra=extra,
        )
        self.session.add(c)
        await self.session.flush()
        return c

    async def upsert_profile(
        self,
        candidate_id: uuid.UUID,
        *,
        headline: str | None = None,
        summary: str | None = None,
        attributes: dict | None = None,
    ) -> CandidateProfile:
        result = await self.session.execute(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id),
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = CandidateProfile(candidate_id=candidate_id)
            self.session.add(profile)
        profile.headline = headline
        profile.summary = summary
        profile.attributes = attributes
        await self.session.flush()
        return profile

    async def get_by_id(self, candidate_id: uuid.UUID) -> Candidate | None:
        result = await self.session.execute(
            select(Candidate).where(Candidate.id == candidate_id),
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, candidate_id: uuid.UUID) -> Candidate | None:
        result = await self.session.execute(
            select(Candidate)
            .options(
                selectinload(Candidate.profile),
                selectinload(Candidate.chat_threads),
                selectinload(Candidate.uploaded_files),
                selectinload(Candidate.task_items),
            )
            .where(Candidate.id == candidate_id),
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Candidate | None:
        result = await self.session.execute(select(Candidate).where(Candidate.email == email))
        return result.scalar_one_or_none()
