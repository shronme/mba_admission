# Development Tasks: Agent intent classification and rewrite-CV routing

## Status
COMPLETE

## Task Summary
Total tasks: 20 | Backend: 11 | Frontend: 0 | Infra: 0 | Test: 9 | Docs: 0

## Tasks

### TASK-001: Remove regex intent module and route-level full-document preload [backend]
- **Description**: Delete `backend/app/dspy/intent.py` (`_REWRITE_INTENT_RE`, `classify_rewrite_intent`). In `backend/app/api/routes/chat.py`, remove `from app.dspy.intent import classify_rewrite_intent` and the entire `if classify_rewrite_intent(user_message):` branch inside `_retrieve_doc_snippets` (currently loads CV/life story via `UploadedFileRepository.get_latest_full_text_by_document_type` and emits `[CV — full text]` / `[Life story — full text]` blocks). Remove associated logging (e.g. `chat_rewrite_intent_preload`). Update `_retrieve_doc_snippets` docstring so it describes **semantic top-k** when `OPENAI_API_KEY` is set, plus the existing no-key fallback (`UploadedFile` / `extracted_text` path), with **no** regex gate.
- **Files to create/modify**:
  - Delete: `backend/app/dspy/intent.py`
  - `backend/app/api/routes/chat.py` (`_retrieve_doc_snippets`, imports)
- **Acceptance criteria**:
  - [ ] `classify_rewrite_intent` and `app.dspy.intent` have no remaining importers in `backend/` (see TASK-012–013).
  - [ ] `_retrieve_doc_snippets` never branches on rewrite regex; behavior matches pre–FR-1 semantic + fallback pattern for all messages.
- **Enables test cases**: TC-001, TC-002
- **Depends on**: —

### TASK-002: Add Pydantic model and normalizer for classifier JSON [backend]
- **Description**: Introduce a strict model (e.g. `AgentAdvisorIntentOutput` or `ClassifyIntentResult`) with `task_kind`, `target_doc`, `emphasis`, `prior_feedback` per the product spec API contract; use `Literal` or `StrEnum` for allowed `task_kind` and `target_doc` values. Implement a `parse_intent_json(raw: str) -> AgentAdvisorIntentOutput | None` (or similar) that returns `None` or raises a controlled `ValidationError` so FR-11 can map to QA fallback at the tool boundary. Do **not** add `thread.stage` or `profile_json` to classifier inputs in v1.
- **Files to create/modify**:
  - New: `backend/app/schemas/agent_advisor_intent.py` (suggested) **or** a small module under `app/dspy/` if you prefer colocation with DSPy—keep validation reusable from tests.
- **Acceptance criteria**:
  - [ ] Only the four `task_kind` and four `target_doc` enumerants are accepted after normalization; invalid combinations feed FR-11 path.
- **Enables test cases**: TC-005, TC-006, TC-007, TC-015
- **Depends on**: —

### TASK-003: Implement `OpenAIIntentClassifier` (live / `DSPY_MODE!=mock`) [backend]
- **Description**: Add `OpenAIIntentClassifier` that performs a single LLM classification call (DSPy `Signature` + `Predict`/`ChainOfThought` or existing project pattern), consuming **only** the trimmed conversation window (TASK-005) and the current user message. Output must be a **JSON object string** matching TASK-002 before returning from the tool. On exceptions/timeouts, propagate to the tool layer for FR-11 handling (log + QA default).
- **Files to create/modify**:
  - New: `backend/app/dspy/intent_classifier.py` (suggested name)
- **Acceptance criteria**:
  - [ ] Classifier never receives more than the last 10 messages of history (plus current user message per tool design); no `thread.stage` / `profile_json`.
  - [ ] Logging on failure follows existing `logger` patterns in `agent_tools.py` / advisor code (TC-016 alignment in tests).
- **Enables test cases**: TC-005, TC-011 (live), TC-014, TC-016
- **Depends on**: TASK-002

### TASK-004: Implement `MockIntentClassifier` (`DSPY_MODE=mock`) [backend]
- **Description**: In the same module as TASK-003, add `MockIntentClassifier` with **deterministic keyword heuristics** that exercise **all four** `task_kind` values (`rewrite_cv`, `qa`, `smalltalk`, `other`). Document rule precedence in code (for overlap). No network calls.
- **Files to create/modify**:
  - `backend/app/dspy/intent_classifier.py`
- **Acceptance criteria**:
  - [ ] Identical inputs produce identical JSON output across runs (TC-009–TC-012).
  - [ ] At least one deterministic trigger string per `task_kind` (table-driven tests in TASK-018).
- **Enables test cases**: TC-009, TC-010, TC-011, TC-012, TC-013
- **Depends on**: TASK-002

### TASK-005: Add `classify_intent` tool and 10-message window helper in `build_agent_tools` [backend]
- **Description**: Extend `build_agent_tools` in `backend/app/dspy/agent_tools.py` to return a **5-tuple** in stable order: `(retrieve_candidate_context, save_artifact, get_full_document, rewrite_cv, classify_intent)` (fifth tool is `classify_intent` per FR-2). Implement an internal helper, e.g. `_last_n_messages_for_intent(history: str | list, n: int = 10)`, used by the classifier and unit-tested (TC-008). The `classify_intent` async closure should accept arguments consistent with how ReAct exposes tools (align field names with `AgentAdvisorSignature` / DSPy tool introspection). Return value: JSON **string** from classifier, or FR-11 default string built without raising into the user HTTP layer.
- **Files to create/modify**:
  - `backend/app/dspy/agent_tools.py` (`build_agent_tools`, new inner `classify_intent`, type hint on return `tuple[...]` currently ending at `rewrite_cv`)
- **Acceptance criteria**:
  - [ ] `DSPY_MODE=mock` uses `MockIntentClassifier`; otherwise `OpenAIIntentClassifier`.
  - [ ] Tool is the **fifth** callable in the returned tuple; all production call sites updated (pipeline + tests in later tasks).
- **Enables test cases**: TC-004, TC-005, TC-008, TC-013
- **Depends on**: TASK-003, TASK-004

### TASK-006: Trajectory state and `save_artifact` guard (match existing error surface) [backend]
- **Description**: Design per-request (per `build_agent_tools` invocation) mutable state in `agent_tools.py` closures, e.g. `rewrite_cv_ran: bool = False` set only when the **`rewrite_cv` tool** successfully completes its rewrite path (including internal persistence). Implement guard in the **`save_artifact` tool** (not the repository layer): when `artifact_type == \"cv_draft\"` and `rewrite_cv_ran` is false, **do not** call `CVDraftRepository.create`; return a **JSON string** using the same pattern as existing errors in this closure, e.g. `json.dumps({\"error\": \"...\"})` (see current `invalid artifact_type` handling in `save_artifact`). Message text must instruct the model to call `rewrite_cv` first, then retry `save_artifact` with the rewriter output (FR-6). **Critical**: the internal `await save_artifact(...)` inside `rewrite_cv` must either use a re-entrancy-safe path (e.g. `_persist_cv_draft` helper, or a `from_rewrite_cv=True` internal parameter, or set `rewrite_cv_ran` before internal save per agreed predicate) so legitimate rewriter persistence is never blocked (TC-017 vs happy path).
- **Files to create/modify**:
  - `backend/app/dspy/agent_tools.py` (`save_artifact`, `rewrite_cv`, shared state scoped to the tuple returned from `build_agent_tools`)
- **Acceptance criteria**:
  - [ ] Bypass `cv_draft` saves from the advisor without an in-trajectory `rewrite_cv` are rejected with JSON error, not silent success.
  - [ ] `rewrite_cv` → internal draft save still succeeds.
  - [ ] `essay_draft` and invalid `artifact_type` behavior unchanged aside from the new branch.
- **Enables test cases**: TC-017, TC-018, FR-5, FR-6
- **Depends on**: TASK-005

### TASK-007: Thread `prior_feedback` through `RewriteCVSignature` and rewriter modules [backend]
- **Description**: Add `prior_feedback: str` input to `RewriteCVSignature` in `backend/app/dspy/rewrite_cv.py` with default `\"\"` and prompt rules: apply bullets for tone/emphasis/**without** dropping CV facts. Update `OpenAIRewriteCVModule` and `MockRewriteCVModule` `forward` / `aforward` to accept and forward `prior_feedback` into the signature. Extend `MockRewriteCVModule` to surface `prior_feedback` in deterministic output (e.g. extra header lines) so TC-021 can assert threading without an LLM.
- **Files to create/modify**:
  - `backend/app/dspy/rewrite_cv.py` (`RewriteCVSignature`, `OpenAIRewriteCVModule`, `MockRewriteCVModule`)
  - `backend/app/dspy/agent_tools.py` (`rewrite_cv` tool: add `prior_feedback: str = \"\"`, pass into `module.aforward`)
- **Acceptance criteria**:
  - [ ] `rewrite_cv` tool forwards `prior_feedback` into the DSPy module call.
  - [ ] No code-level truncation of `prior_feedback` (spec: prompt-only concision).
- **Enables test cases**: TC-020, TC-021
- **Depends on**: TASK-005

### TASK-008: Update `AgentAdvisorSignature` copy — `classify_intent` first, semantic preload [backend]
- **Description**: Revise `AgentAdvisorSignature` docstring in `backend/app/dspy/agent_advisor.py`: add **`classify_intent`** to TOOLS with “call first each turn”; update `rewrite_cv` bullet to include `prior_feedback`. Remove or rewrite clauses that state `preloaded_document_snippets` is the **full** CV / tagged full text on rewrite turns (that was true only via the removed `chat.py` branch). Update RULES so routing for CV rewrites goes through `classify_intent` → `rewrite_cv` and does not encourage inline full CV in `response` for `task_kind == rewrite_cv` (FR-5 / TC-23).
- **Files to create/modify**:
  - `backend/app/dspy/agent_advisor.py` (`AgentAdvisorSignature`)
- **Acceptance criteria**:
  - [ ] RULES explicitly require `classify_intent` as the first tool call on a turn (TC-022).
  - [ ] `preloaded_document_snippets` description matches semantic snippet behavior from the route.
- **Enables test cases**: TC-022, TC-023
- **Depends on**: TASK-005

### TASK-009: Wire five tools and `max_iters=8` in `AgentAdvisorModule` [backend]
- **Description**: Update `AgentAdvisorModule.__init__` in `backend/app/dspy/agent_advisor.py` to accept `classify_intent_fn` and pass **five** tools into `dspy.ReAct(..., tools=[retrieve_fn, save_artifact_fn, get_full_document_fn, rewrite_cv_fn, classify_intent_fn], max_iters=8)`. Update comments that still say `max_iters=6`. FR-13: **8** replaces **6** everywhere this module configures ReAct (TC-019).
- **Files to create/modify**:
  - `backend/app/dspy/agent_advisor.py` (`AgentAdvisorModule`)
- **Acceptance criteria**:
  - [ ] `getattr(module.react, \"max_iters\", None) == 8`.
  - [ ] `len(module.react.tools) == 5` (or equivalent DSPy API).
- **Enables test cases**: TC-004, TC-019, TC-018
- **Depends on**: TASK-005, TASK-008

### TASK-010: `MockAgentAdvisorModule` five-tool parity [backend]
- **Description**: Add optional `classify_intent_fn` parameter; extend `self.tools` list to **five** entries in the same order as `build_agent_tools`. Update class docstring (“four-tool” → **five-tool** parity with `AgentAdvisorModule`). If integration tests rely on `self.tools` introspection, keep order stable.
- **Files to create/modify**:
  - `backend/app/dspy/agent_advisor.py` (`MockAgentAdvisorModule`)
- **Acceptance criteria**:
  - [ ] `len(module.tools) == 5` when all callables passed.
  - [ ] `pipeline.py` passes the fifth callable from `build_agent_tools` (TASK-011).
- **Enables test cases**: TC-024
- **Depends on**: TASK-005, TASK-009

### TASK-011: Advisor stage wiring in `pipeline.py` — unpack 5-tuple and refresh preload commentary [backend]
- **Description**: In `generate_assistant_response` advisor branch (`backend/app/dspy/pipeline.py`), change unpacking from four symbols to five from `build_agent_tools`. Pass `classify_intent_fn` into `AgentAdvisorModule` / `MockAgentAdvisorModule`. Update comments around `docs_snippets` / `preloaded_snippets_text` (lines ~277–297): after TASK-001, route-supplied snippets should be **semantic-only**; remove or narrow the “Full-document (FR-4)” preload shape if it is no longer produced by `chat._retrieve_doc_snippets`, while preserving correct formatting for semantic lists (`[1] ...`).
- **Files to create/modify**:
  - `backend/app/dspy/pipeline.py` (advisor-stage `build_agent_tools` unpack, module constructors, snippet join comments)
- **Acceptance criteria**:
  - [ ] No off-by-one unpack; advisor runs in both `DSPY_MODE=mock` and production wiring.
  - [ ] Comments reflect actual `chat` behavior post TASK-001.
- **Enables test cases**: TC-004, TC-020, TC-025
- **Depends on**: TASK-005, TASK-009, TASK-010, TASK-001

### TASK-012: Delete regex intent test module [test]
- **Description**: Delete `backend/tests/test_rag_rewrite_intent_regex.py` entirely (it imports `_REWRITE_INTENT_RE`, `classify_rewrite_intent` from `app.dspy.intent`). Verify no remaining references via search.
- **Files to create/modify**:
  - Delete: `backend/tests/test_rag_rewrite_intent_regex.py`
- **Acceptance criteria**:
  - [ ] `pytest` collection no longer imports removed symbols.
- **Enables test cases**: TC-001
- **Depends on**: TASK-001

### TASK-013: Replace `test_rag_tool_selection.py` — remove regex + route full-doc preload assertions [test]
- **Description**: Remove `from app.dspy.intent import classify_rewrite_intent` and tests that assert `classify_rewrite_intent` coverage (`REWRITE_SEEDS` / `QA_SEEDS` as regex classifier tests). Replace `test_rewrite_seeds_skip_semantic_search` / `— full text]` expectations with tests that **`_retrieve_doc_snippets` always uses the semantic / fallback path** (mock `search_async` or embedding path; assert `get_latest_full_text_by_document_type` is **not** called for rewrite phrasing). Keep file purpose aligned with TC-002/TC-003.
- **Files to create/modify**:
  - `backend/tests/test_rag_tool_selection.py`
- **Acceptance criteria**:
  - [ ] No imports from `app.dspy.intent`.
  - [ ] No assertion that rewrite phrasing injects `[CV — full text]` from the route.
- **Enables test cases**: TC-002, TC-003
- **Depends on**: TASK-001

### TASK-014: Rewrite `test_rag_chat_preload.py` for semantic-only route behavior [test]
- **Description**: Update or remove tests that expect `[CV — full text]` / `[Life story — full text]` from `_retrieve_doc_snippets` for messages like `please rewrite my CV` (see `test_rag_chat_preload.py` references to full-text blocks and `chat_rewrite_intent`). Align fixtures with semantic snippet shapes or fallback extraction. Update pipeline-join tests if they assumed route-delivered full-doc blocks.
- **Files to create/modify**:
  - `backend/tests/test_rag_chat_preload.py`
- **Acceptance criteria**:
  - [ ] Tests match TASK-001 behavior; no dependency on regex-driven preload.
- **Enables test cases**: TC-002, TC-003
- **Depends on**: TASK-001, TASK-011

### TASK-015: Update `test_rag_tool_wiring.py` for five tools and `max_iters == 8` [test]
- **Description**: `test_build_agent_tools_returns_four_callables` → **five** callables; update expected tool names (`classify_intent`). Refresh the repo grep test (`Stale build_agent_tools unpacks`) to expect **5**-tuple unpacks / `*_` patterns. `test_react_has_four_tools_and_max_iters_6` → **five** tools and **`max_iters == 8`**. Update `MockAgentAdvisorModule` construction in this file to pass five async dummies including `classify_intent`.
- **Files to create/modify**:
  - `backend/tests/test_rag_tool_wiring.py`
- **Acceptance criteria**:
  - [ ] TC-019 assertion matches production `AgentAdvisorModule` configuration.
  - [ ] Grep-based arity guard matches new tuple size.
- **Enables test cases**: TC-004, TC-019, TC-024
- **Depends on**: TASK-005, TASK-009, TASK-010

### TASK-016: Update `test_agent_advisor_unit.py` unpacks and ReAct expectations [test]
- **Description**: Every `build_agent_tools(...)` unpack adds the fifth symbol. Tests that construct `AgentAdvisorModule` / `MockAgentAdvisorModule` with explicit tool fakes must pass `classify_intent_fn`. Fix `test_agent_advisor_module_uses_react_with_max_iters` (currently asserts `max_iters == 6` and comments “max_iters=6”) to **`8`**. Update save_artifact / tool tests that assume a 4-tuple.
- **Files to create/modify**:
  - `backend/tests/test_agent_advisor_unit.py`
- **Acceptance criteria**:
  - [ ] No stale references to four-tool-only advisor.
  - [ ] `max_iters` assertion matches TASK-009.
- **Enables test cases**: TC-004, TC-019
- **Depends on**: TASK-005, TASK-009, TASK-010

### TASK-017: Update `test_rag_rewrite_cv_tool.py` and `test_rag_get_full_document.py` for 5-tuple + `prior_feedback` [test]
- **Description**: Extend all `build_agent_tools` unpacks to five variables. Add coverage that `rewrite_cv(..., prior_feedback=\"...\")` reaches `MockRewriteCVModule` (monkeypatch/spy on `MockRewriteCVModule.aforward` or inspect rewritten text for embedded marker from TASK-007).
- **Files to create/modify**:
  - `backend/tests/test_rag_rewrite_cv_tool.py`
  - `backend/tests/test_rag_get_full_document.py`
- **Acceptance criteria**:
  - [ ] All tests use the new `build_agent_tools` arity.
  - [ ] At least one test verifies `prior_feedback` propagation (TC-020/TC-021).
- **Enables test cases**: TC-020, TC-021
- **Depends on**: TASK-005, TASK-007

### TASK-018: New unit tests — mock classifier matrix, window size, FR-11 fallbacks [test]
- **Description**: Add tests (new file under `backend/tests/` or extend `test_rag_tool_wiring.py`) for: (1) table-driven `MockIntentClassifier` covering all four `task_kind` values (TC-013); (2) history trimming to **10** messages with distinct tokens in older messages (TC-008); (3) invalid JSON and forced exceptions from the classifier → tool returns QA default with `task_kind=qa` (TC-014, TC-015). Optionally `caplog` for TC-016.
- **Files to create/modify**:
  - New or existing: `backend/tests/test_intent_classifier.py` (suggested)
- **Acceptance criteria**:
  - [ ] All four `task_kind` values observed in CI via parameterized rows.
  - [ ] No network when `DSPY_MODE=mock`.
- **Enables test cases**: TC-008–TC-015, TC-013
- **Depends on**: TASK-002, TASK-004, TASK-005

### TASK-019: Integration tests — `save_artifact` guard and retry within iteration budget [test]
- **Description**: Add tests (prefer extending `backend/tests/test_agent_advisor_integration.py` or a focused `test_save_artifact_guard.py` with the existing ReAct harness patterns) that: (1) attempt `save_artifact` with `cv_draft` without `rewrite_cv` in the same trajectory and assert **JSON error** + **no** new `cv_drafts` row (TC-017); (2) simulate or drive guard → `rewrite_cv` → successful save with `max_iters=8` (TC-018). Use `DSPY_MODE=mock` and existing DB fixtures.
- **Files to create/modify**:
  - `backend/tests/test_agent_advisor_integration.py` and/or new test module
- **Acceptance criteria**:
  - [ ] Assertions bind to the implemented `save_artifact` error JSON shape (see QA “Hard-to-Test” note).
  - [ ] Happy-path recovery respects iteration cap.
- **Enables test cases**: TC-017, TC-018
- **Depends on**: TASK-006, TASK-009, TASK-011

### TASK-020: Integration / system tests — advisor streaming and non-rewrite turns [test]
- **Description**: Update `backend/tests/test_agent_advisor_integration.py` scenarios impacted by semantic-only preloads, mock `classify_intent`, and optional assertions on tool traces / artifacts (TC-025–TC-027, TC-023 where feasible with mock). Ensure Q&A/smalltalk messages still complete without erroneous guard failures (TC-026).
- **Files to create/modify**:
  - `backend/tests/test_agent_advisor_integration.py`
- **Acceptance criteria**:
  - [ ] CV rewrite request still yields a persisted draft when mock routing says `rewrite_cv` (TC-025).
  - [ ] Classifier degradation path does not hard-500 the stream if FR-11 is satisfied (TC-027).
- **Enables test cases**: TC-023, TC-025, TC-026, TC-027
- **Depends on**: TASK-011, TASK-018, TASK-019

## Implementation Order
1. TASK-001
2. TASK-002
3. TASK-003
4. TASK-004
5. TASK-005
6. TASK-006
7. TASK-007
8. TASK-008
9. TASK-009
10. TASK-010
11. TASK-011
12. TASK-012
13. TASK-013
14. TASK-014
15. TASK-015
16. TASK-016
17. TASK-017
18. TASK-018
19. TASK-019
20. TASK-020

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅

## Commands to run (backend — do not skip before merge)
From repo root or `backend/` as you usually do for this project:

```bash
cd backend
export PYTHONPATH=.
export DSPY_MODE=mock
# Integration tests: ensure DATABASE_URL points at your test Postgres when running advisor integration tests.
export DATABASE_URL=\"${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions}\"

pytest -q
pytest -q tests/test_rag_tool_selection.py tests/test_rag_chat_preload.py
pytest -q tests/test_rag_tool_wiring.py tests/test_agent_advisor_unit.py
pytest -q tests/test_rag_rewrite_cv_tool.py tests/test_rag_get_full_document.py
pytest -q tests/test_intent_classifier.py
pytest -q tests/test_agent_advisor_integration.py
```

Optional sanity: `rg classify_rewrite_intent backend/` should return no hits after TASK-001/TASK-012.

