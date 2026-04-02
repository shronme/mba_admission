#!/usr/bin/env python3
"""
Seed one realistic **grad** candidate plus related rows (profile, chat, file, strategy, tasks, essay, AI run, audit).

Usage (from `backend/`):

  export PYTHONPATH=.
  export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions
  python scripts/seed_task002_demo.py

Requires schema applied: `alembic upgrade head`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid

# Ensure `backend/` is on path when run as `python scripts/seed_task002_demo.py`
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.enums import (
    AiRunStatus,
    AiRunType,
    AuditActorType,
    CandidateStatus,
    ChatThreadStatus,
    EssayStatus,
    FileStatus,
    MessageRole,
    ProgramType,
    ReviewerType,
    StrategyStatus,
    StrategyType,
    TaskStatus,
)
from app.db.models.ai_run import AiRun
from app.db.models.audit import AuditEvent
from app.db.models.candidate import Candidate
from app.db.models.essay import EssayDraft, EssayReview
from app.db.models.files import UploadedFile
from app.db.models.strategy import StrategyDecision
from app.db.models.tasks import TaskItem
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.chat_repo import ChatRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("seed_task002")


async def main() -> uuid.UUID:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            logger.info("Seeding demo candidate and related rows…")
            cid = await _seed(session)
            await session.commit()
            logger.info("Done. Seeded candidate id=%s", cid)
            return cid
    finally:
        await engine.dispose()


async def _seed(session: AsyncSession) -> uuid.UUID:
    c_repo = CandidateRepository(session)
    chat_repo = ChatRepository(session)

    logger.info("Creating candidate and profile…")
    candidate = await c_repo.create_candidate(
        full_name="Jordan Park",
        email="jordan.park.demo@example.com",
        program_type=ProgramType.GRAD,
        status=CandidateStatus.ACTIVE,
        extra={"target_cycle": "Fall 2026", "region_pref": "Northeast US"},
    )
    await c_repo.upsert_profile(
        candidate.id,
        headline="Aspiring product leader pivoting from engineering",
        summary="5 years in backend infra; targeting MBA programs with strong tech clubs.",
        attributes={
            "undergrad": "State University",
            "gpa_band": "3.5–3.7",
            "target_schools": ["Sloan", "Tuck", "Ross"],
        },
    )

    logger.info("Creating chat thread and messages…")
    thread = await chat_repo.create_thread(
        candidate.id,
        title="Kickoff — goals & timeline",
        status=ChatThreadStatus.ACTIVE,
        extra={"channel": "web"},
    )
    await chat_repo.add_message(
        thread.id,
        role=MessageRole.USER,
        content="I want a realistic 6-month roadmap before Round 1.",
    )
    await chat_repo.add_message(
        thread.id,
        role=MessageRole.ASSISTANT,
        content="Let's anchor on your target schools and story pillars first…",
        extra={"model_stub": "seed"},
    )

    logger.info("Adding file, strategy, tasks, essay, AI run, audit…")
    session.add(
        UploadedFile(
            candidate_id=candidate.id,
            original_filename="resume_draft.pdf",
            content_type="application/pdf",
            byte_size=245_000,
            storage_uri=f"s3://demo-bucket/candidates/{candidate.id}/resume_draft.pdf",
            status=FileStatus.READY,
            extra={"source": "seed"},
        )
    )

    session.add(
        StrategyDecision(
            candidate_id=candidate.id,
            strategy_type=StrategyType.NARRATIVE,
            status=StrategyStatus.ACTIVE,
            payload={
                "pillars": ["builder", "mentor", "global"],
                "risks": ["quant coursework gap"],
            },
        )
    )

    session.add(
        TaskItem(
            candidate_id=candidate.id,
            title="Finalize school shortlist (8 → 5)",
            description="Weight fit vs scholarship vs geography.",
            status=TaskStatus.IN_PROGRESS,
            position=10,
            extra={"due_soon": True},
        )
    )
    session.add(
        TaskItem(
            candidate_id=candidate.id,
            title="Draft career goals paragraph",
            status=TaskStatus.TODO,
            position=20,
        )
    )

    essay = EssayDraft(
        candidate_id=candidate.id,
        school_name="MIT Sloan",
        prompt_text="Tell us about a time you led without authority.",
        title="Leading a cross-team incident response",
        body="Last year our payments pipeline stalled during peak load…",
        status=EssayStatus.DRAFT,
        extra={"word_count_target": 300},
    )
    session.add(essay)
    await session.flush()

    session.add(
        EssayReview(
            essay_draft_id=essay.id,
            reviewer_type=ReviewerType.AI,
            summary="Strong technical detail; add explicit leadership outcome.",
            scores={"structure": 7, "impact": 6, "voice": 8},
            feedback={"suggestions": ["Quantify business impact", "Tie to MBA goals"]},
        )
    )

    session.add(
        AiRun(
            candidate_id=candidate.id,
            run_type=AiRunType.CLASSIFICATION,
            status=AiRunStatus.SUCCEEDED,
            request={"text": "User asked for a roadmap"},
            response={"label": "planning", "confidence": 0.86},
            model_name="seed-stub",
        )
    )

    session.add(
        AuditEvent(
            actor_type=AuditActorType.SYSTEM,
            action="seed_demo_insert",
            entity_type="candidate",
            entity_id=candidate.id,
            context={"script": "seed_task002_demo.py"},
        )
    )

    # Exercise ORM relationships
    await session.refresh(candidate, ["profile", "chat_threads"])
    assert candidate.profile is not None
    assert len(candidate.chat_threads) >= 1
    loaded = await chat_repo.get_thread_with_messages(thread.id)
    assert loaded is not None and len(loaded.messages) == 2

    return candidate.id


if __name__ == "__main__":
    asyncio.run(main())
