"""
ORM models — import this module so every table registers on Base.metadata (Alembic).
"""

from app.db.models.ai_run import AiRun
from app.db.models.audit import AuditEvent
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.chat import ChatMessage, ChatThread
from app.db.models.candidate_sessions import CandidateSession
from app.db.models.document_chunk import DocumentChunk
from app.db.models.essay import EssayDraft, EssayReview
from app.db.models.files import UploadedFile
from app.db.models.strategy import StrategyDecision
from app.db.models.tasks import TaskItem

__all__ = [
    "AiRun",
    "AuditEvent",
    "Candidate",
    "CandidateProfile",
    "ChatMessage",
    "ChatThread",
    "CandidateSession",
    "DocumentChunk",
    "EssayDraft",
    "EssayReview",
    "StrategyDecision",
    "TaskItem",
    "UploadedFile",
]
