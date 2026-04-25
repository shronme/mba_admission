from __future__ import annotations

import json
import os
import uuid
from unittest.mock import MagicMock

import pytest

from app.dspy.agent_tools import build_agent_tools
from app.dspy.intent_classifier import MockIntentClassifier, last_n_messages_text
from app.schemas.agent_advisor_intent import (
    AdvisorTaskKind,
    AdvisorTargetDoc,
    parse_intent_json,
)


class TestMockIntentClassifierMatrix:
    @pytest.mark.parametrize(
        ("msg", "expected_kind"),
        [
            ("Please rewrite my CV for Wharton", AdvisorTaskKind.REWRITE_CV),
            ("Hi there", AdvisorTaskKind.SMALLTALK),
            ("What is my GMAT percentile?", AdvisorTaskKind.QA),
            ("Let's plan next steps for my application timeline", AdvisorTaskKind.OTHER),
        ],
    )
    def test_classify_json_covers_all_task_kinds(
        self, msg: str, expected_kind: AdvisorTaskKind
    ) -> None:
        raw = MockIntentClassifier().classify_json(conversation_history="", user_message=msg)
        parsed = parse_intent_json(raw)
        assert parsed.task_kind == expected_kind


class TestLastNMessagesWindow:
    def test_sequence_history_is_trimmed_to_last_10_messages(self) -> None:
        history = [{"role": "user", "content": f"m{i}"} for i in range(12)]
        out = last_n_messages_text(history, n=10)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        # m0 and m1 should be trimmed out (check whole-line tokens to avoid
        # substring collisions like "m1" in "m10").
        assert not any(ln.endswith("m0") for ln in lines)
        assert not any(ln.endswith("m1") for ln in lines)
        # last 10 should remain
        for i in range(2, 12):
            assert f"m{i}" in out

    def test_string_history_is_trimmed_to_last_10_lines(self) -> None:
        history = "\n".join([f"USER: line{i}" for i in range(12)])
        out = last_n_messages_text(history, n=10)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        assert not any(ln.endswith("line0") for ln in lines)
        assert not any(ln.endswith("line1") for ln in lines)
        for i in range(2, 12):
            assert f"line{i}" in out


class TestClassifyIntentToolFallbacks:
    @pytest.mark.asyncio
    async def test_invalid_json_from_classifier_falls_back_to_qa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        os.environ["DSPY_MODE"] = "mock"
        session = MagicMock()
        candidate_id = uuid.uuid4()
        openai_client = MagicMock()

        *_, classify_intent = build_agent_tools(session, candidate_id, openai_client)

        def _bad_json(self, *, conversation_history: str, user_message: str) -> str:  # noqa: ARG001
            return "not-json"

        monkeypatch.setattr(MockIntentClassifier, "classify_json", _bad_json, raising=True)
        raw = await classify_intent(user_message="hello", conversation_history=[])
        parsed = parse_intent_json(raw)
        assert parsed.task_kind == AdvisorTaskKind.QA
        assert parsed.target_doc == AdvisorTargetDoc.OTHER

    @pytest.mark.asyncio
    async def test_exception_from_classifier_falls_back_to_qa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        os.environ["DSPY_MODE"] = "mock"
        session = MagicMock()
        candidate_id = uuid.uuid4()
        openai_client = MagicMock()

        *_, classify_intent = build_agent_tools(session, candidate_id, openai_client)

        def _boom(self, *, conversation_history: str, user_message: str) -> str:  # noqa: ARG001
            raise RuntimeError("boom")

        monkeypatch.setattr(MockIntentClassifier, "classify_json", _boom, raising=True)
        raw = await classify_intent(user_message="hello", conversation_history=[])
        parsed = parse_intent_json(raw)
        assert parsed.task_kind == AdvisorTaskKind.QA


class TestIntentJsonSchema:
    def test_parse_intent_json_rejects_unknown_enum_values(self) -> None:
        with pytest.raises(Exception):
            parse_intent_json(
                json.dumps(
                    {
                        "task_kind": "rewriting",
                        "target_doc": "cv",
                        "emphasis": "",
                        "prior_feedback": "",
                    }
                )
            )

