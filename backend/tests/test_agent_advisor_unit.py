"""
Unit tests for AgentAdvisorModule and related tool functions.

Covers TC-001 through TC-017 from the QA plan.

Run with:
    cd backend && DSPY_MODE=mock PYTHONPATH=. pytest tests/test_agent_advisor_unit.py -q
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import dspy
import pytest

# ---------------------------------------------------------------------------
# Ensure mock mode is set for all tests in this module.
# ---------------------------------------------------------------------------
os.environ.setdefault("DSPY_MODE", "mock")


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _dummy_fn(*args: Any, **kwargs: Any) -> str:
    return "dummy"


async def _async_dummy_fn(*args: Any, **kwargs: Any) -> str:
    return "dummy"


# ---------------------------------------------------------------------------
# TC-004 / TC-005 / TC-006 / TC-007 — MockAgentAdvisorModule
# ---------------------------------------------------------------------------

class TestMockAgentAdvisorModule:
    """
    TC-004: CV-related message returns cv_draft artifact.
    TC-005: Essay-related message returns essay_draft artifact.
    TC-006: Unrelated message returns generic response with no artifact.
    TC-007: aforward is awaitable and returns same result as forward.
    """

    def _make_module(self):
        """Import or define MockAgentAdvisorModule.

        If the real module exists use it; otherwise fall back to the spec
        reference implementation so the unit tests themselves are valid.

        Per FR-6 the mock now mirrors the four-tool contract of
        `AgentAdvisorModule`; construct it with four dummy async callables
        so the `self.tools` list is populated for introspection-style
        assertions without changing the observable forward/aforward
        behavior exercised by this test class.
        """
        try:
            from app.dspy.agent_advisor import MockAgentAdvisorModule
            return MockAgentAdvisorModule(
                retrieve_fn=_async_dummy_fn,
                save_fn=_async_dummy_fn,
                get_full_document_fn=_async_dummy_fn,
                rewrite_cv_fn=_async_dummy_fn,
                classify_intent_fn=_async_dummy_fn,
            )
        except ImportError:
            pass

        # Reference implementation from spec (used until real code is merged).
        class MockAgentAdvisorModule(dspy.Module):
            def forward(self, user_message: str, **kwargs) -> dspy.Prediction:
                msg = (user_message or "").lower()
                if "cv" in msg:
                    return dspy.Prediction(
                        response="[MOCK] Here is your improved CV.",
                        artifact_id="mock-cv-artifact-id",
                        artifact_type="cv_draft",
                    )
                if "essay" in msg:
                    return dspy.Prediction(
                        response="[MOCK] Here is your essay feedback.",
                        artifact_id="mock-essay-artifact-id",
                        artifact_type="essay_draft",
                    )
                return dspy.Prediction(response="[MOCK] How can I help you?")

            async def aforward(self, **kwargs) -> dspy.Prediction:
                return self.forward(**kwargs)

        return MockAgentAdvisorModule()

    # TC-004
    def test_cv_message_returns_cv_artifact(self) -> None:
        module = self._make_module()
        pred = module.forward(
            user_message="help me improve my CV",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        assert "[MOCK]" in pred.response
        assert pred.artifact_id == "00000000-0000-0000-0000-000000000001"
        assert pred.artifact_type == "cv_draft"

    def test_cv_uppercase_returns_cv_artifact(self) -> None:
        module = self._make_module()
        pred = module.forward(
            user_message="Improve my CV for Wharton",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        assert pred.artifact_type == "cv_draft"

    # TC-005
    def test_essay_message_returns_essay_artifact(self) -> None:
        module = self._make_module()
        pred = module.forward(
            user_message="review my essay",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        assert pred.artifact_type == "essay_draft"
        assert pred.artifact_id == "00000000-0000-0000-0000-000000000002"

    def test_essay_mixed_case(self) -> None:
        module = self._make_module()
        pred = module.forward(
            user_message="Essay review please",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        assert pred.artifact_type == "essay_draft"

    def test_cv_takes_precedence_over_essay(self) -> None:
        """When message contains both 'cv' and 'essay', cv check runs first."""
        module = self._make_module()
        pred = module.forward(
            user_message="cv and essay help",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        # cv keyword appears first in the implementation
        assert pred.artifact_type == "cv_draft"

    # TC-006
    def test_unrelated_message_returns_generic_response(self) -> None:
        module = self._make_module()
        pred = module.forward(
            user_message="what is the application deadline?",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        assert pred.response == "[MOCK] How can I help you?"
        assert not getattr(pred, "artifact_id", None)

    def test_empty_message_does_not_crash(self) -> None:
        module = self._make_module()
        pred = module.forward(
            user_message="",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        assert isinstance(pred.response, str)

    # TC-007
    @pytest.mark.asyncio
    async def test_aforward_is_awaitable(self) -> None:
        module = self._make_module()
        pred = await module.aforward(
            user_message="cv",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        assert pred.artifact_type == "cv_draft"

    @pytest.mark.asyncio
    async def test_aforward_and_forward_return_same_result(self) -> None:
        module = self._make_module()
        kwargs = dict(
            user_message="improve my CV",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        sync_pred = module.forward(**kwargs)
        async_pred = await module.aforward(**kwargs)
        assert sync_pred.response == async_pred.response
        assert sync_pred.artifact_type == async_pred.artifact_type


# ---------------------------------------------------------------------------
# TC-001 — AgentAdvisorModule instantiation (skipped if not yet implemented)
# ---------------------------------------------------------------------------

class TestAgentAdvisorModuleInstantiation:
    """TC-001: AgentAdvisorModule uses dspy.ReAct with max_iters=8."""

    def test_react_attribute_exists_with_correct_config(self) -> None:
        try:
            from app.dspy.agent_advisor import AgentAdvisorModule
        except ImportError:
            pytest.skip("AgentAdvisorModule not yet implemented")

        module = AgentAdvisorModule(
            retrieve_fn=_dummy_fn,
            save_artifact_fn=_dummy_fn,
            get_full_document_fn=_dummy_fn,
            rewrite_cv_fn=_dummy_fn,
            classify_intent_fn=_dummy_fn,
        )
        assert hasattr(module, "react"), "module.react must exist"
        assert isinstance(module.react, dspy.ReAct), "module.react must be dspy.ReAct"
        assert getattr(module.react, "max_iters", None) == 8, "max_iters must be 8"
        assert hasattr(module, "forward"), "module must expose forward"
        assert hasattr(module, "aforward"), "module must expose aforward"


# ---------------------------------------------------------------------------
# TC-002 — AgentAdvisorModule.forward delegates to ReAct.forward
# ---------------------------------------------------------------------------

class TestAgentAdvisorModuleForward:
    """TC-002: forward passes kwargs through to dspy.ReAct.forward."""

    def test_forward_delegates_to_react(self) -> None:
        try:
            from app.dspy.agent_advisor import AgentAdvisorModule
        except ImportError:
            pytest.skip("AgentAdvisorModule not yet implemented")

        fake_prediction = dspy.Prediction(response="test response")
        mock_react = MagicMock(return_value=fake_prediction)

        module = AgentAdvisorModule(
            retrieve_fn=_dummy_fn,
            save_artifact_fn=_dummy_fn,
            get_full_document_fn=_dummy_fn,
            rewrite_cv_fn=_dummy_fn,
            classify_intent_fn=_dummy_fn,
        )
        module.react = mock_react

        kwargs = dict(
            user_message="hello",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        result = module.forward(**kwargs)
        mock_react.assert_called_once_with(**kwargs)
        assert result is fake_prediction


# ---------------------------------------------------------------------------
# TC-003 — AgentAdvisorModule.aforward is async and delegates to react.aforward
# ---------------------------------------------------------------------------

class TestAgentAdvisorModuleAforward:
    """TC-003: aforward awaits react.aforward."""

    @pytest.mark.asyncio
    async def test_aforward_delegates_to_react_aforward(self) -> None:
        try:
            from app.dspy.agent_advisor import AgentAdvisorModule
        except ImportError:
            pytest.skip("AgentAdvisorModule not yet implemented")

        fake_prediction = dspy.Prediction(response="async response")
        mock_react_aforward = AsyncMock(return_value=fake_prediction)

        module = AgentAdvisorModule(
            retrieve_fn=_dummy_fn,
            save_artifact_fn=_dummy_fn,
            get_full_document_fn=_dummy_fn,
            rewrite_cv_fn=_dummy_fn,
            classify_intent_fn=_dummy_fn,
        )
        # Replace only the aforward method
        module.react = MagicMock()
        module.react.aforward = mock_react_aforward

        kwargs = dict(
            user_message="hello",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        result = await module.aforward(**kwargs)
        mock_react_aforward.assert_awaited_once_with(**kwargs)
        assert result is fake_prediction


# ---------------------------------------------------------------------------
# TC-008 / TC-009 — retrieve_candidate_context tool
# ---------------------------------------------------------------------------

class TestRetrieveCandidateContext:
    """
    TC-008: retrieve_candidate_context returns numbered chunk list with correct args.
    TC-009: Tool closure is scoped to candidate_id — no cross-candidate leakage.
    """

    @pytest.mark.asyncio
    async def test_returns_numbered_chunk_list(self) -> None:
        """TC-008: numbered list of up to 8 chunks; search_async called with correct args."""
        from app.dspy.agent_tools import build_agent_tools

        candidate_id = uuid.uuid4()
        mock_session = MagicMock()

        # Fake embedding response
        fake_embed_resp = MagicMock()
        fake_embed_resp.data = [MagicMock(embedding=[0.1] * 1536)]

        mock_openai = MagicMock()
        mock_openai.embeddings = MagicMock()
        mock_openai.embeddings.create = AsyncMock(return_value=fake_embed_resp)

        chunks = ["chunk one", "chunk two", "chunk three"]
        mock_search = AsyncMock(return_value=chunks)

        with patch("app.dspy.agent_tools.search_async", mock_search):
            retrieve_fn, _save_fn, _get_full, _rewrite_cv, _classify = build_agent_tools(
                mock_session, candidate_id, mock_openai
            )
            result = await retrieve_fn("my query")

        assert result == "[1] chunk one\n\n[2] chunk two\n\n[3] chunk three"
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs.get("candidate_id") == candidate_id
        assert call_kwargs.kwargs.get("top_k") == 8

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_chunks(self) -> None:
        from app.dspy.agent_tools import build_agent_tools

        candidate_id = uuid.uuid4()
        mock_session = MagicMock()

        fake_embed_resp = MagicMock()
        fake_embed_resp.data = [MagicMock(embedding=[0.0] * 1536)]
        mock_openai = MagicMock()
        mock_openai.embeddings.create = AsyncMock(return_value=fake_embed_resp)

        mock_search = AsyncMock(return_value=[])
        with patch("app.dspy.agent_tools.search_async", mock_search):
            retrieve_fn, *_ = build_agent_tools(mock_session, candidate_id, mock_openai)
            result = await retrieve_fn("empty query")

        # Should be empty or placeholder — not raise
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_candidate_isolation_different_candidate_ids(self) -> None:
        """TC-009: Each closure uses its own candidate_id; no cross-leakage."""
        from app.dspy.agent_tools import build_agent_tools

        id_a = uuid.uuid4()
        id_b = uuid.uuid4()

        captured_ids: list[uuid.UUID] = []

        async def mock_search(session, *, candidate_id, query_embedding, top_k=8):
            captured_ids.append(candidate_id)
            return []

        fake_embed_resp = MagicMock()
        fake_embed_resp.data = [MagicMock(embedding=[0.0] * 1536)]
        mock_openai = MagicMock()
        mock_openai.embeddings.create = AsyncMock(return_value=fake_embed_resp)

        with patch("app.dspy.agent_tools.search_async", mock_search):
            retrieve_a, *_ = build_agent_tools(MagicMock(), id_a, mock_openai)
            retrieve_b, *_ = build_agent_tools(MagicMock(), id_b, mock_openai)
            await retrieve_a("query")
            await retrieve_b("query")

        assert captured_ids[0] == id_a
        assert captured_ids[1] == id_b
        assert id_b not in [captured_ids[0]]  # A never used B's id


# ---------------------------------------------------------------------------
# TC-010 / TC-011 / TC-012 / TC-013 — save_artifact tool
# ---------------------------------------------------------------------------

class TestSaveArtifactTool:
    """
    TC-010: cv_draft type creates CVDraft row.
    TC-011: essay_draft type creates EssayDraft row with source='agent'.
    TC-012: Invalid artifact_type returns error string, no DB write.
    TC-013: download_url has correct format (/api/artifacts/{uuid}/download).
    """

    def _get_save_fn(self, candidate_id: uuid.UUID | None = None):
        from app.dspy.agent_tools import build_agent_tools

        if candidate_id is None:
            candidate_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_openai = MagicMock()
        _retrieve_fn, save_fn, _get_full_fn, _rewrite_cv_fn, _classify = build_agent_tools(
            mock_session, candidate_id, mock_openai
        )
        return save_fn, mock_session, candidate_id

    @pytest.mark.asyncio
    async def test_cv_draft_calls_cv_repository(self) -> None:
        """cv_draft is guarded: save_artifact rejects without rewrite_cv."""
        from app.dspy.agent_tools import build_agent_tools

        candidate_id = uuid.uuid4()
        mock_artifact_id = uuid.uuid4()
        mock_draft = MagicMock()
        mock_draft.id = mock_artifact_id

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=mock_draft)

        mock_session = MagicMock()
        mock_openai = MagicMock()

        with patch("app.dspy.agent_tools.CVDraftRepository", return_value=mock_repo):
            _retrieve, save_fn, _get_full, _rewrite_cv, _classify = build_agent_tools(
                mock_session, candidate_id, mock_openai
            )
            result = await save_fn("cv_draft", "Wharton CV", "<body>", "Wharton")

        parsed = json.loads(result)
        assert "error" in parsed
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_essay_draft_creates_row_with_source_agent(self) -> None:
        """TC-011: essay_draft type passes source='agent' to repository."""
        from app.dspy.agent_tools import build_agent_tools

        candidate_id = uuid.uuid4()
        mock_artifact_id = uuid.uuid4()
        mock_draft = MagicMock()
        mock_draft.id = mock_artifact_id

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=mock_draft)

        mock_session = MagicMock()
        mock_openai = MagicMock()

        with patch("app.dspy.agent_tools.EssayDraftRepository", return_value=mock_repo):
            _retrieve, save_fn, _get_full, _rewrite_cv, _classify = build_agent_tools(
                mock_session, candidate_id, mock_openai
            )
            result = await save_fn("essay_draft", "Booth Essay", "<feedback>", "Booth")

        parsed = json.loads(result)
        assert "artifact_id" in parsed
        # Verify source='agent' was passed
        create_kwargs = mock_repo.create.call_args
        kwargs = create_kwargs.kwargs if create_kwargs else {}
        # EssayDraftRepository.create accepts source as a keyword argument
        assert kwargs.get("source") == "agent", (
            f"Expected source='agent', got kwargs={kwargs}"
        )

    @pytest.mark.asyncio
    async def test_invalid_artifact_type_returns_error_string(self) -> None:
        """TC-012: Invalid artifact_type returns error, no DB write."""
        from app.dspy.agent_tools import build_agent_tools

        candidate_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_openai = MagicMock()
        _retrieve, save_fn, _get_full, _rewrite_cv, _classify = build_agent_tools(
            mock_session, candidate_id, mock_openai
        )

        for bad_type in ["malicious_type", "", "CV_DRAFT", "'; DROP TABLE--"]:
            result = await save_fn(bad_type, "Title", "Body", "School")
            # Must return a string (not raise), and must signal an error
            assert isinstance(result, str)
            lower = result.lower()
            assert "error" in lower or "invalid" in lower or "unknown" in lower, (
                f"Expected error string for artifact_type={bad_type!r}, got: {result!r}"
            )

    @pytest.mark.asyncio
    async def test_download_url_format(self) -> None:
        """TC-013: download_url = /api/artifacts/{uuid}/download (no host prefix)."""
        from app.dspy.agent_tools import build_agent_tools

        known_uuid = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")
        mock_draft = MagicMock()
        mock_draft.id = known_uuid

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=mock_draft)

        mock_session = MagicMock()
        mock_openai = MagicMock()
        candidate_id = uuid.uuid4()

        with patch("app.dspy.agent_tools.EssayDraftRepository", return_value=mock_repo):
            _retrieve, save_fn, _get_full, _rewrite_cv, _classify = build_agent_tools(
                mock_session, candidate_id, mock_openai
            )
            result = await save_fn("essay_draft", "My Essay", "<body>", "MIT")

        parsed = json.loads(result)
        url = parsed["download_url"]
        assert url.startswith("/api/artifacts/"), f"URL should start with /api/artifacts/, got: {url}"
        assert str(known_uuid) in url, "URL should contain the artifact UUID"
        assert not url.startswith("http"), "URL must be relative (no host prefix)"
        assert url.endswith("/download"), "URL should end with /download"


# ---------------------------------------------------------------------------
# TC-014 / TC-015 / TC-016 / TC-017 — Pipeline routing
# ---------------------------------------------------------------------------

class TestPipelineRouting:
    """
    TC-014: advisor stage routes to AgentAdvisorModule (mock mode).
    TC-015: intake stage does NOT route to AgentAdvisorModule.
    TC-016: essay guardrail does not fire for advisor stage.
    TC-017: essay guardrail still fires for intake stage.
    """

    async def _call_pipeline(self, user_message: str, thread_stage: str | None):
        from app.dspy.pipeline import generate_assistant_response
        return await generate_assistant_response(
            user_message=user_message,
            file_count=0,
            candidate_profile={"full_name": "Test", "attributes": {}},
            docs_snippets=[],
            recent_messages=[],
            profile_complete=False,
            current_completeness_score=0,
            thread_stage=thread_stage,
            selected_schools=[{"school": "Wharton", "program_slug": "mba"}],
            admission_evaluation_result=None,
            session=MagicMock(),
            candidate_id=uuid.uuid4(),
            openai_client=object(),
        )

    @pytest.mark.asyncio
    async def test_advisor_stage_routes_to_mock_agent(self) -> None:
        """TC-014: advisor-stage thread uses agent advisor (mock) — response is non-empty."""
        os.environ["DSPY_MODE"] = "mock"
        pred = await self._call_pipeline("help me with my CV", thread_stage="advisor")
        assert hasattr(pred, "response")
        assert str(getattr(pred, "response", "")).strip()

    @pytest.mark.asyncio
    async def test_intake_stage_does_not_use_advisor(self) -> None:
        """TC-015: intake-stage thread goes to intake module, not advisor."""
        os.environ["DSPY_MODE"] = "mock"
        text, updates, is_complete, score = await self._call_pipeline("hello", thread_stage="intake")
        assert isinstance(text, str)
        # Intake module produces profile updates; advisor returns empty dict
        # We just verify the call doesn't crash and returns a sensible response.
        assert text.strip()

    @pytest.mark.asyncio
    async def test_research_stage_does_not_use_advisor(self) -> None:
        """TC-015 variant: research-stage thread goes to research module."""
        os.environ["DSPY_MODE"] = "mock"
        # profile_complete=True triggers research agent
        from app.dspy.pipeline import generate_assistant_response
        text, _, _, _ = await generate_assistant_response(
            user_message="what schools should I apply to?",
            file_count=0,
            candidate_profile={"full_name": "Test", "attributes": {}},
            docs_snippets=[],
            recent_messages=[],
            profile_complete=True,
            current_completeness_score=100,
            thread_stage=None,
            selected_schools=None,
            admission_evaluation_result=None,
        )
        assert text.strip()

    @pytest.mark.asyncio
    async def test_essay_guardrail_does_not_fire_for_advisor(self) -> None:
        """TC-016: 'review my essay' in advisor stage reaches the agent (no guardrail block)."""
        os.environ["DSPY_MODE"] = "mock"
        pred = await self._call_pipeline("review my essay for Wharton", thread_stage="advisor")
        text = str(getattr(pred, "response", "") or "")
        # The guardrail response has specific wording about brainstorming/outlining.
        # For advisor stage, a different (agent) response is returned.
        guardrail_phrases = [
            "brainstorm, outline, and improve",
            "can't write a full essay",
            "i can help you brainstorm",
        ]
        text_lower = text.lower()
        for phrase in guardrail_phrases:
            assert phrase not in text_lower, (
                f"Guardrail fired unexpectedly for advisor stage. Response: {text!r}"
            )

    @pytest.mark.asyncio
    async def test_essay_guardrail_fires_for_intake_stage(self) -> None:
        """TC-017: 'write my essay' in intake stage triggers the guardrail."""
        os.environ["DSPY_MODE"] = "mock"
        text, _, _, score = await self._call_pipeline("write my essay", thread_stage="intake")
        # The guardrail returns score=-1 (sentinel) and a specific message
        assert score == -1
        assert "brainstorm" in text.lower() or "can't write" in text.lower() or "outline" in text.lower()

    @pytest.mark.asyncio
    async def test_essay_guardrail_fires_for_none_stage(self) -> None:
        """TC-017 variant: 'write an essay' with no stage also triggers guardrail."""
        os.environ["DSPY_MODE"] = "mock"
        text, _, _, score = await self._call_pipeline("write an essay", thread_stage=None)
        assert score == -1
