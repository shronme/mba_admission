from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    CANDIDATE = "candidate"
    ADMIN = "admin"


class CandidateStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    PROSPECT = "prospect"


class CandidateStage(StrEnum):
    INTAKE = "intake"
    DIAGNOSIS = "diagnosis"
    PROGRAM_RESEARCH = "program_research"
    STRATEGY = "strategy"
    NARRATIVE = "narrative"
    SCHOOL_LIST = "school_list"
    APPLICATION_WORK = "application_work"
    ITERATION = "iteration"
    INTERVIEW_PREPARATION = "interview_preparation"


class ProgramType(StrEnum):
    UNDERGRAD = "undergrad"
    GRAD = "grad"
    MBA = "mba"
    PHD = "phd"
    OTHER = "other"


class ChatThreadStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class FileStatus(StrEnum):
    UPLOADING = "uploading"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class DocumentType(StrEnum):
    CV = "cv"
    LIFE_STORY = "life_story"
    RECOMMENDATION_LETTER = "recommendation_letter"
    GRADE_SHEET = "grade_sheet"
    IRRELEVANT = "irrelevant"
    UNCLASSIFIED = "unclassified"


class StrategyType(StrEnum):
    SCHOOL_SELECTION = "school_selection"
    TIMELINE = "timeline"
    NARRATIVE = "narrative"
    ESSAY_PLAN = "essay_plan"
    OTHER = "other"


class StrategyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class EssayStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ARCHIVED = "archived"


class ReviewerType(StrEnum):
    AI = "ai"
    HUMAN = "human"


class AiRunType(StrEnum):
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    GENERATION = "generation"
    REVIEW = "review"
    OTHER = "other"


class AiRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    AI = "ai"
