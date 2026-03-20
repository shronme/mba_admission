from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PrimaryIntent(StrEnum):
    INTAKE_DOCS = "intake_docs"
    INTAKE_GOALS = "intake_goals"
    ADMISSIONS_HELP = "admissions_help"
    OFF_TOPIC = "off_topic"


class SecondaryFlag(StrEnum):
    DISALLOWED_FULL_ESSAY = "disallowed_full_essay"
    NEEDS_DOC_UPLOAD = "needs_doc_upload"
    NEEDS_GOALS_CLARIFICATION = "needs_goals_clarification"


class IntentRoutingOutput(BaseModel):
    """
    Strict classification/routing contract for DSPy pipeline modules.

    Used for guardrails + choosing the response strategy.
    """

    model_config = ConfigDict(extra="forbid")

    primary_intent: PrimaryIntent
    secondary_flags: list[SecondaryFlag] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    recommended_agent: str
    requires_clarification: bool = False

