"""
ORM models — import this module so every table registers on Base.metadata (Alembic).
"""

from app.db.models.admin import Admin
from app.db.models.ai_run import AiRun
from app.db.models.audit import AuditEvent
from app.db.models.candidate import Candidate, CandidateProfile
from app.db.models.chat import ChatMessage, ChatThread
from app.db.models.candidate_sessions import CandidateSession  # kept for migration tracking
from app.db.models.cv_draft import CVDraft
from app.db.models.document_chunk import DocumentChunk
from app.db.models.knowledge_chunk import KnowledgeChunk
from app.db.models.essay import EssayDraft, EssayReview
from app.db.models.files import UploadedFile
from app.db.models.strategy import StrategyDecision
from app.db.models.tasks import TaskItem
from app.db.models.user import User
from app.db.models.user_session import UserSession

__all__ = [
    "Admin",
    "AiRun",
    "AuditEvent",
    "Candidate",
    "CandidateProfile",
    "CandidateSession",
    "ChatMessage",
    "ChatThread",
    "CVDraft",
    "DocumentChunk",
    "KnowledgeChunk",
    "EssayDraft",
    "EssayReview",
    "StrategyDecision",
    "TaskItem",
    "UploadedFile",
    "User",
    "UserSession",
]
