"""
Tests for FR-6: `build_agent_tools` return arity, advisor module wiring,
and `MockAgentAdvisorModule`.

Covers TC-038..TC-041 from the `rag-full-document-retrieval` QA plan:
  - TC-038: `build_agent_tools` returns five callables in the expected order
  - TC-039: every unpack site uses five callables (grep-based regression)
  - TC-040: `MockAgentAdvisorModule` accepts the five tools / wiring works
  - TC-041: `AgentAdvisorModule.react.max_iters == 8` for rewrite trajectory
"""

from __future__ import annotations

import inspect
import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import dspy
import pytest

os.environ.setdefault("DSPY_MODE", "mock")

from app.dspy.agent_advisor import (  # noqa: E402
    AgentAdvisorModule,
    MockAgentAdvisorModule,
)
from app.dspy.agent_tools import build_agent_tools  # noqa: E402


# ===========================================================================
# TC-038 — arity + order
# ===========================================================================
class TestBuildAgentToolsArity:
    def test_returns_four_callables_in_fixed_order(self) -> None:
        session = MagicMock()
        candidate_id = uuid.uuid4()
        openai_client = MagicMock()

        tools = build_agent_tools(session, candidate_id, openai_client)
        assert isinstance(tools, tuple)
        assert len(tools) == 5, f"expected 5 tools, got {len(tools)}"
        for t in tools:
            assert callable(t), f"tool {t!r} must be callable"

        names = [getattr(t, "__name__", "") for t in tools]
        assert names == [
            "retrieve_candidate_context",
            "save_artifact",
            "get_full_document",
            "rewrite_cv",
            "classify_intent",
        ], f"tool order mismatch: {names}"


# ===========================================================================
# TC-039 — no stale 2/3-tuple unpacks in the backend code tree
# ===========================================================================
class TestNoStaleUnpackSites:
    """
    Grep-based regression: every `build_agent_tools` unpack in
    `backend/app` and `backend/tests` should destructure four callables
    (or use positional index access). We accept both:
      `a, b, c, d = build_agent_tools(...)`
      `tools = build_agent_tools(...)` + `tools[0]` / etc.
    We reject stale two- or three-callable unpacks.
    """

    def test_no_two_or_three_tuple_unpacks(self) -> None:
        backend_root = Path(__file__).resolve().parent.parent
        this_file = Path(__file__).resolve()
        hits: list[tuple[Path, int, str]] = []
        for py in list(backend_root.rglob("*.py")):
            if ".venv" in py.parts or "__pycache__" in py.parts:
                continue
            if py.resolve() == this_file:
                continue
            try:
                lines = py.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "build_agent_tools(" not in stripped:
                    continue
                if "=" not in stripped:
                    continue
                # e.g. "retrieve_fn, save_fn = build_agent_tools(...)"
                lhs, _, _rhs = stripped.partition("=")
                lhs = lhs.strip()
                if "," not in lhs:
                    continue
                names = [p.strip() for p in lhs.strip("()").split(",") if p.strip()]
                # Star-unpacks like `a, *_ = build_agent_tools(...)` are fine;
                # they forward to four callables without relying on exact arity
                # at the LHS.
                if any(n.startswith("*") for n in names):
                    continue
                if len(names) in (2, 3, 4):
                    hits.append((py.relative_to(backend_root), i, stripped))
        assert not hits, (
            "Stale build_agent_tools unpacks detected (expected 5 callables): "
            f"{hits}"
        )


# ===========================================================================
# TC-040 — MockAgentAdvisorModule accepts optional save_artifact_fn
# ===========================================================================
class TestMockAgentAdvisorModule:
    def test_constructs_without_args(self) -> None:
        module = MockAgentAdvisorModule()
        assert isinstance(module, dspy.Module)

    def test_constructs_with_all_five_tool_kwargs(self) -> None:
        async def fake_retrieve(*_a, **_kw) -> str:
            return ""

        async def fake_save(
            artifact_type: str, title: str, body: str, school_name: str | None
        ) -> str:
            return "{}"

        async def fake_get_doc(*_a, **_kw) -> str:
            return ""

        async def fake_rewrite(*_a, **_kw) -> str:
            return ""

        async def fake_classify(*_a, **_kw) -> str:
            return "{}"

        module = MockAgentAdvisorModule(
            retrieve_fn=fake_retrieve,
            save_fn=fake_save,
            get_full_document_fn=fake_get_doc,
            rewrite_cv_fn=fake_rewrite,
            classify_intent_fn=fake_classify,
        )
        assert module is not None

    def test_mock_init_accepts_five_tool_kwargs(self) -> None:
        sig = inspect.signature(MockAgentAdvisorModule.__init__)
        params = [p for p in sig.parameters.keys() if p != "self"]
        assert set(params) == {
            "retrieve_fn",
            "save_fn",
            "get_full_document_fn",
            "rewrite_cv_fn",
            "classify_intent_fn",
        }, f"unexpected MockAgentAdvisorModule init params: {params}"

    @pytest.mark.asyncio
    async def test_aforward_returns_prediction_for_cv_request(self) -> None:
        module = MockAgentAdvisorModule()
        pred = await module.aforward(
            user_message="help me with my cv",
            profile_attributes_json="{}",
            selected_schools_json="[]",
            conversation_history="",
        )
        assert getattr(pred, "artifact_type", "") == "cv_draft"


# ===========================================================================
# TC-041 — AgentAdvisorModule.react.max_iters = 6
# ===========================================================================
class TestAgentAdvisorMaxIters:
    def _noop_async_tool(self, name: str):
        async def _fn(*_args, **_kwargs) -> str:  # pragma: no cover — not invoked
            return ""

        _fn.__name__ = name
        return _fn

    def test_react_has_five_tools_and_max_iters_8(self) -> None:
        module = AgentAdvisorModule(
            retrieve_fn=self._noop_async_tool("retrieve_candidate_context"),
            save_artifact_fn=self._noop_async_tool("save_artifact"),
            get_full_document_fn=self._noop_async_tool("get_full_document"),
            rewrite_cv_fn=self._noop_async_tool("rewrite_cv"),
            classify_intent_fn=self._noop_async_tool("classify_intent"),
        )
        assert isinstance(module.react, dspy.ReAct)
        assert getattr(module.react, "max_iters", None) == 8

    def test_constructor_accepts_exactly_five_tool_kwargs(self) -> None:
        sig = inspect.signature(AgentAdvisorModule.__init__)
        params = [p for p in sig.parameters.keys() if p != "self"]
        assert set(params) == {
            "retrieve_fn",
            "save_artifact_fn",
            "get_full_document_fn",
            "rewrite_cv_fn",
            "classify_intent_fn",
        }, f"unexpected AgentAdvisorModule init params: {params}"
