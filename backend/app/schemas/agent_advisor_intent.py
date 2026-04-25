from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AdvisorTaskKind(StrEnum):
    REWRITE_CV = "rewrite_cv"
    QA = "qa"
    SMALLTALK = "smalltalk"
    OTHER = "other"


class AdvisorTargetDoc(StrEnum):
    CV = "cv"
    LIFE_STORY = "life_story"
    ESSAY = "essay"
    OTHER = "other"


class AgentAdvisorIntentOutput(BaseModel):
    """
    Strict JSON contract returned by the `classify_intent` tool.
    """

    model_config = ConfigDict(extra="forbid")

    task_kind: AdvisorTaskKind
    target_doc: AdvisorTargetDoc
    emphasis: str = ""
    prior_feedback: str = ""


def _normalize_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_enum_value(value: Any) -> str:
    return _normalize_str(value).lower()


def parse_intent_json(raw: str) -> AgentAdvisorIntentOutput:
    """
    Parse and validate classifier output JSON.

    Raises `ValueError` for JSON parse errors and `ValidationError` for schema errors.
    """
    if not isinstance(raw, str):
        raise ValueError("Intent output must be a JSON string")
    try:
        payload = json.loads(raw)
    except Exception as exc:  # json.JSONDecodeError is a ValueError subclass
        raise ValueError("Intent output was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Intent output JSON must be an object")

    normalized = {
        "task_kind": _normalize_enum_value(payload.get("task_kind")),
        "target_doc": _normalize_enum_value(payload.get("target_doc")),
        "emphasis": _normalize_str(payload.get("emphasis")),
        "prior_feedback": _normalize_str(payload.get("prior_feedback")),
    }
    return AgentAdvisorIntentOutput.model_validate(normalized)


def qa_fallback_intent_json() -> str:
    """
    Safe default used when classification fails (FR-11).
    """
    return json.dumps(
        {
            "task_kind": AdvisorTaskKind.QA.value,
            "target_doc": AdvisorTargetDoc.OTHER.value,
            "emphasis": "",
            "prior_feedback": "",
        }
    )

