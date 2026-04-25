from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

import dspy

logger = logging.getLogger(__name__)


class AgentAdvisorSignature(dspy.Signature):
    """
    You are an MBA admissions advisor helping a specific candidate.

    CONTEXT YOU ALREADY HAVE
    - `profile_attributes_json`: structured facts the candidate provided during intake
      (work history, test scores, target programs, career goals, etc.).
    - `selected_schools_json`: the schools/programs the candidate is applying to.
    - `available_documents_json`: the list of documents the candidate has ALREADY
      uploaded. Every document listed here is indexed and retrievable.
    - `preloaded_document_snippets`: passages from the candidate's documents that
      were already retrieved for you using their latest message as the query. In
      most cases this is all the document context you need — read these before
      calling any tool. These are semantic snippets (top-k passages), not full
      documents.

    TOOLS
    - `classify_intent(user_message, conversation_history)`: returns a JSON object
      string with `task_kind`, `target_doc`, `emphasis`, and `prior_feedback`. Call
      this FIRST on every user turn, then route your behavior based on the result.
    - `retrieve_candidate_context(query)`: returns ranked snippets across all of
      the candidate's uploaded documents. Good for Q&A ("what did they say about
      leadership"). NOT sufficient for rewrites — it may omit sections, formatting,
      or tail content.
    - `get_full_document(document_type)`: returns the **full** extracted text of
      the latest uploaded document of the given type. Valid types: `cv`,
      `life_story`, `recommendation_letter`, `grade_sheet`. Use this when you
      need complete content (e.g. rewriting a CV, grounding an essay in the life
      story) and the preload does not already contain a tagged full-text block.
    - `rewrite_cv(target_school="", emphasis="", prior_feedback="")`: produce a rewritten CV and
      persist it as a `cv_draft` automatically. Use this when the candidate
      asks you to rewrite / polish / redraft their CV. You do not need to call
      `save_artifact` after it — it persists the draft internally and returns
      the rewritten text.
    - `save_artifact(artifact_type, title, body, school_name)`: persist a
      deliverable (essay draft, CV draft you built yourself, etc.) so the
      candidate can download it. Do NOT call it for advice or outlines.

    RULES
    0. On EVERY user turn, call `classify_intent` first. Use the returned JSON to
       decide what to do next.
    1. NEVER ask the candidate to paste or re-send content that appears in
       `available_documents_json`. If they uploaded a "cv", you already have their
       CV.
    2. After `classify_intent`, start by reading `preloaded_document_snippets`.
       If it already contains what you need for a Q&A / smalltalk response, answer
       directly WITHOUT calling any additional tool.
    3. For rewrite / redraft of a **specific uploaded document** (CV, life story,
       essay), prefer full text — either the tagged full block already in
       `get_full_document` call. Do NOT rely on `retrieve_candidate_context` alone
       for those tasks; ranked snippets can omit roles, dates, or education entries.
    4. Only call `retrieve_candidate_context` when `preloaded_document_snippets`
       is insufficient AND you can articulate what specific additional content
       you need. Call it AT MOST ONCE per turn, using a single broad query that
       covers everything you need in one shot. Do NOT re-query with refined
       wording — you will get similar results and waste time.
    5. Only ask the candidate for information that is genuinely not in their
       profile, selected schools, or documents (e.g. a new essay prompt, a target
       word count, which of their listed schools to prioritize this iteration).
    6. If the candidate has more than one selected school and hasn't specified
       which to tailor this iteration for, it IS reasonable to ask — that is not
       in any document.
    7. When you produce a concrete artifact other than via `rewrite_cv`, persist
       it with `save_artifact` and reference the returned download link in your
       response. `rewrite_cv` already persists internally — do not double-save.
    8. When `classify_intent.task_kind == "rewrite_cv"`, do NOT paste a full CV
       in your free-text response. Use `rewrite_cv` + artifact persistence.

    Keep responses concise and focused on the next concrete step.
    """

    profile_attributes_json: str = dspy.InputField(
        desc="Candidate profile attributes as JSON."
    )
    selected_schools_json: str = dspy.InputField(
        desc="Schools the candidate is applying to as JSON."
    )
    available_documents_json: str = dspy.InputField(
        desc=(
            "JSON array of documents the candidate has already uploaded. Each item "
            "has `document_type` (e.g. 'cv', 'grade_sheet', 'recommendation_letter', "
            "'life_story') and `original_filename`. Treat every document here as "
            "content you already have access to — DO NOT ask the candidate to paste it."
        )
    )
    preloaded_document_snippets: str = dspy.InputField(
        desc=(
            "Passages from the candidate's uploaded documents, pre-retrieved using "
            "their latest message as the query. Read these FIRST. If they answer "
            "your needs, do not call any retrieval tool."
        )
    )
    conversation_history: str = dspy.InputField(
        desc="Full conversation history, newest last."
    )
    user_message: str = dspy.InputField(desc="The candidate's latest message.")

    response: str = dspy.OutputField(desc="The advisor's response to the candidate.")


class AgentAdvisorModule(dspy.Module):
    def __init__(
        self,
        retrieve_fn: Callable,
        save_artifact_fn: Callable,
        get_full_document_fn: Callable,
        rewrite_cv_fn: Callable,
        classify_intent_fn: Callable,
    ) -> None:
        super().__init__()
        # max_iters=8: allows the full rewrite trajectory (e.g. classify_intent ->
        # `get_full_document` -> `rewrite_cv` -> final response)
        # without timing out. Previous value 4 was tuned to (retrieve +
        # save_artifact + response) and is too tight once `rewrite_cv` can
        # appear in the same turn.
        self.react = dspy.ReAct(
            AgentAdvisorSignature,
            tools=[
                retrieve_fn,
                save_artifact_fn,
                get_full_document_fn,
                rewrite_cv_fn,
                classify_intent_fn,
            ],
            max_iters=8,
        )

    def forward(self, **kwargs) -> dspy.Prediction:  # type: ignore[override]
        return self.react(**kwargs)

    async def aforward(self, **kwargs) -> dspy.Prediction:
        return await self.react.aforward(**kwargs)


class MockAgentAdvisorModule(dspy.Module):
    """
    Deterministic stand-in for the real ReAct advisor used when
    `DSPY_MODE=mock`.

    Per FR-6/FR-2 the mock MUST mirror the five-tool surface of
    `AgentAdvisorModule` — `retrieve_candidate_context`, `save_artifact`,
    `get_full_document`, `rewrite_cv`, and `classify_intent` — so tests can
    assert the mock holds the full tool contract even though the trajectory
    is simulated rather than executed via `dspy.ReAct`.

    When constructed with a `save_fn` (the async tool closure built by
    `build_agent_tools`), a CV/essay-flavored turn will actually persist a
    real `cv_drafts` / `essay_drafts` row and surface the real UUID on the
    returned `dspy.Prediction`. This keeps the end-to-end mock pipeline
    honest — the emitted `artifact_id` is a valid UUID that the
    `GET /artifacts/{artifact_id}/download` endpoint (which validates
    `uuid.UUID`) can resolve.

    If `save_fn` is omitted or persistence fails (e.g. unit tests that pass
    a `MagicMock` session), we fall back to hard-coded placeholder IDs so
    those tests continue to pass.
    """

    def __init__(
        self,
        retrieve_fn: Callable[..., Awaitable[str]] | None = None,
        save_fn: Callable[[str, str, str, str | None], Awaitable[str]]
        | None = None,
        get_full_document_fn: Callable[..., Awaitable[str]] | None = None,
        rewrite_cv_fn: Callable[..., Awaitable[str]] | None = None,
        classify_intent_fn: Callable[..., Awaitable[str]] | None = None,
    ) -> None:
        super().__init__()
        self._retrieve_fn = retrieve_fn
        self._save_artifact_fn = save_fn
        self._get_full_document_fn = get_full_document_fn
        self._rewrite_cv_fn = rewrite_cv_fn
        self._classify_intent_fn = classify_intent_fn
        # Expose the full five-tool surface for introspection parity with
        # `AgentAdvisorModule.react.tools` (FR-6 / TC-040). Entries may be
        # None when the mock is constructed bare (e.g. legacy unit tests);
        # order matches `build_agent_tools` return tuple.
        self.tools = [
            retrieve_fn,
            save_fn,
            get_full_document_fn,
            rewrite_cv_fn,
            classify_intent_fn,
        ]

    def forward(self, user_message: str, **kwargs) -> dspy.Prediction:  # type: ignore[override]
        msg = (user_message or "").lower()
        if "cv" in msg:
            return dspy.Prediction(
                response="[MOCK] Here is your improved CV.",
                # Keep this parseable as a UUID because some integration tests
                # hit `/artifacts/{artifact_id}/download` even in mock mode.
                artifact_id="00000000-0000-0000-0000-000000000001",
                artifact_type="cv_draft",
            )
        if "essay" in msg:
            return dspy.Prediction(
                response="[MOCK] Here is your essay feedback.",
                artifact_id="00000000-0000-0000-0000-000000000002",
                artifact_type="essay_draft",
            )
        return dspy.Prediction(response="[MOCK] How can I help you?")

    async def aforward(self, user_message: str = "", **kwargs) -> dspy.Prediction:
        msg = (user_message or "").lower()
        if "cv" in msg:
            artifact_id, download_url = await self._maybe_persist(
                artifact_type="cv_draft",
                title="Mock CV Draft",
                body="[MOCK] Generated CV body.",
                school_name=None,
            )
            return dspy.Prediction(
                response="[MOCK] Here is your improved CV.",
                artifact_id=artifact_id or "00000000-0000-0000-0000-000000000001",
                artifact_type="cv_draft",
                download_url=download_url or "",
            )
        if "essay" in msg:
            artifact_id, download_url = await self._maybe_persist(
                artifact_type="essay_draft",
                title="Mock Essay Draft",
                body="[MOCK] Generated essay feedback body.",
                school_name=None,
            )
            return dspy.Prediction(
                response="[MOCK] Here is your essay feedback.",
                artifact_id=artifact_id or "00000000-0000-0000-0000-000000000002",
                artifact_type="essay_draft",
                download_url=download_url or "",
            )
        return dspy.Prediction(response="[MOCK] How can I help you?")

    async def _maybe_persist(
        self,
        *,
        artifact_type: str,
        title: str,
        body: str,
        school_name: str | None,
    ) -> tuple[str | None, str | None]:
        """
        Invoke the injected save_artifact tool closure (if any) and parse its
        JSON return value. Any failure (no closure, mock session, DB error)
        is swallowed so the mock module still returns a usable Prediction.
        """
        if self._save_artifact_fn is None:
            return None, None
        try:
            raw = await self._save_artifact_fn(artifact_type, title, body, school_name)
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("artifact_id"):
                return parsed.get("artifact_id"), parsed.get("download_url")
        except Exception:
            logger.exception(
                "mock_advisor_save_artifact_failed artifact_type=%s", artifact_type
            )
        return None, None
