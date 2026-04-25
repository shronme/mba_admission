# QA Test Plan: Agent intent classification and rewrite-CV routing

## Status
COMPLETE

## Coverage Summary
- Unit tests: 10
- Integration tests: 14
- System/E2E tests: 3

## Test Cases

### TC-001: No `classify_rewrite_intent` or regex intent module remains
- **Type**: Unit
- **Requirement**: FR-1
- **Preconditions**: Codebase after refactor; optional static search in CI or test that greps forbidden symbols.
- **Steps**:
  1. Search the repo for `classify_rewrite_intent`, `intent.classify_rewrite`, and removed `app/dspy/intent.py` symbols.
  2. Confirm no imports or call sites remain in `chat`, pipeline, or agent wiring.
- **Expected Result**: Zero references; any dead test imports fail visibly until removed.
- **Edge Cases / Variants**: Re-export shims or deprecated aliases must not exist (per spec: delete, not deprecate).

### TC-002: `_retrieve_doc_snippets` uses semantic RAG only (no regex-driven full-doc branch)
- **Type**: Integration
- **Requirement**: FR-1
- **Preconditions**: RAG fixtures or mocked retriever; `DSPY_MODE=mock` acceptable; no reliance on tagged full-text injection from the route.
- **Steps**:
  1. Invoke `chat._retrieve_doc_snippets` (or the smallest public wrapper) with user text that previously triggered regex “rewrite” preload.
  2. Assert retrieval uses only semantic top-k (and documented no-API-key fallbacks if applicable).
  3. Assert no code path injects full CV text or `[CV — full text]`-style tagged preload from regex matching.
- **Expected Result**: Snippets behave like pre–regex semantic behavior; no full-document preload tied to intent regex.
- **Edge Cases / Variants**: Empty corpus; missing API key fallback path still does not add regex full-doc preload.

### TC-003: RAG / chat tests do not assert full-text preload for “rewrite” phrasing
- **Type**: Integration
- **Requirement**: FR-1
- **Preconditions**: Updated or replaced tests that formerly expected route-level full CV in context.
- **Steps**:
  1. Review tests touching `chat`, RAG, and agent advisor integration for expectations of full CV in snippet payload from the route.
  2. Replace assertions with semantic snippet shape (top-k, chunk boundaries) per product intent.
- **Expected Result**: No test depends on tagged `[CV — full text]` preloads or regex-triggered full document from `_retrieve_doc_snippets`.
- **Edge Cases / Variants**: Tests that intentionally use `get_full_document` or rewriter fixtures are allowed; they must not conflate route preload with those tools.

### TC-004: `build_agent_tools` registers five tools including `classify_intent`
- **Type**: Integration
- **Requirement**: FR-2
- **Preconditions**: Import `build_agent_tools` and unpack return value in test.
- **Steps**:
  1. Call `build_agent_tools` in mock and non-mock configurations as applicable.
  2. Assert return is a **5-tuple** (or documented structure) with fifth tool named / identifiable as `classify_intent`.
  3. Assert pipeline / agent module unpacks five tools without regression.
- **Expected Result**: Five-tool parity; no off-by-one unpack errors.
- **Edge Cases / Variants**: Mock vs production tool factories both expose five tools.

### TC-005: `classify_intent` tool output is a parseable JSON string with required fields
- **Type**: Integration
- **Requirement**: FR-2, FR-4
- **Preconditions**: `DSPY_MODE=mock` with deterministic inputs; optional schema validator in test.
- **Steps**:
  1. Call the `classify_intent` tool with `user_message` and `conversation_history` per agent conventions.
  2. `json.loads` the return value.
  3. Assert presence and types of `task_kind`, `target_doc`, `emphasis`, `prior_feedback` (string).
- **Expected Result**: Valid JSON object; field names exact per API contract.
- **Edge Cases / Variants**: `prior_feedback` may be `""`; `emphasis` short string.

### TC-006: `task_kind` restricted to `rewrite_cv|qa|smalltalk|other`
- **Type**: Unit
- **Requirement**: FR-4, FR-9
- **Preconditions**: Shared enum, Literal, or Pydantic model used for classifier output validation; or test of allowed set in mock/production normalizer.
- **Steps**:
  1. For each allowed value, assert acceptance after parse/normalize.
  2. For disallowed values (e.g. `rewrite`, `cv_update`), assert rejection, coercion, or fallback per engineering choice — **spec intent**: only the four literals are valid product outputs; invalid should align with FR-11 (safe default) when applicable.
- **Expected Result**: Only the four allowed strings appear as normalized `task_kind` from the tool in happy path; garbage maps to QA fallback when applicable (see TC-017–TC-018).
- **Edge Cases / Variants**: Case sensitivity; whitespace trimming.

### TC-007: `target_doc` restricted to `cv|life_story|essay|other`
- **Type**: Unit
- **Requirement**: FR-4, FR-10
- **Preconditions**: Same as TC-006 for `target_doc` enumeration.
- **Steps**:
  1. Assert all four enumerants are accepted in schema validation.
  2. Assert unknown values trigger validation failure or safe default consistent with FR-11.
- **Expected Result**: Enumeration enforced at parse/validation layer; forward-compatible values not outside the four.
- **Edge Cases / Variants**: `rewrite_cv` with `target_doc` other than `cv` — v1 may not spin a new rewriter but JSON must still validate.

### TC-008: Classifier input uses only last 10 messages (+ current user message as designed)
- **Type**: Unit
- **Requirement**: FR-3
- **Preconditions**: Construct a thread with >10 prior messages with distinct markers in content.
- **Steps**:
  1. Build conversation history of length 15 with unique tokens in oldest messages.
  2. Pass history into the classifier input builder (or tool pre-processing).
  3. Assert the payload seen by `OpenAIIntentClassifier` / `MockIntentClassifier` contains only the last 10 (and not `thread.stage` or `profile_json`).
- **Expected Result**: Window size 10; no extra structured context beyond spec.
- **Edge Cases / Variants**: Fewer than 10 messages; system messages if present in history — behavior documented and stable.

### TC-009: `MockIntentClassifier` — deterministic `rewrite_cv`
- **Type**: Unit
- **Requirement**: FR-12
- **Preconditions**: `DSPY_MODE=mock`; fixed `user_message` and history triggering rewrite heuristic.
- **Steps**:
  1. Run classifier twice with identical inputs.
  2. Assert identical JSON string or parsed dict equality for `task_kind` and stable fields.
- **Expected Result**: No network; bitwise or logical equality across runs.
- **Edge Cases / Variants**: Parallel test execution does not share mutable global state.

### TC-010: `MockIntentClassifier` — deterministic `qa`
- **Type**: Unit
- **Requirement**: FR-12
- **Preconditions**: Keywords / fixtures mapped to `qa` in mock.
- **Steps**: Same as TC-009 with QA-triggering input.
- **Expected Result**: `task_kind == "qa"` deterministically.
- **Edge Cases / Variants**: Default path when no other keyword matches if that is mock behavior.

### TC-011: `MockIntentClassifier` — deterministic `smalltalk`
- **Type**: Unit
- **Requirement**: FR-12
- **Preconditions**: Keywords / fixtures mapped to `smalltalk`.
- **Steps**: Same as TC-009 with smalltalk-triggering input.
- **Expected Result**: `task_kind == "smalltalk"` deterministically.
- **Edge Cases / Variants**: Overlap priority between mock rules documented in test name.

### TC-012: `MockIntentClassifier` — deterministic `other`
- **Type**: Unit
- **Requirement**: FR-12
- **Preconditions**: Keywords / fixtures mapped to `other`.
- **Steps**: Same as TC-009 with other-triggering input.
- **Expected Result**: `task_kind == "other"` deterministically.
- **Edge Cases / Variants**: Table-driven test combining TC-009–TC-012 is acceptable as TC-013.

### TC-013: Table-driven mock coverage for all four `task_kind` values
- **Type**: Integration
- **Requirement**: FR-12
- **Preconditions**: Parameterized test with four rows (one per `task_kind`).
- **Steps**:
  1. For each row, invoke mock classifier with agreed fixture.
  2. Assert `task_kind` matches row expectation and JSON schema holds.
- **Expected Result**: At least one passing path per `task_kind`; CI proves all four are covered.
- **Edge Cases / Variants**: Single test file vs distributed tests; coverage report must show all four branches executed.

### TC-014: Classifier exception / tool failure — fallback `task_kind=qa`
- **Type**: Integration
- **Requirement**: FR-11
- **Preconditions**: Monkeypatch `OpenAIIntentClassifier` or underlying LM to raise; or inject failure in mock layer’s “failure mode” hook if provided.
- **Steps**:
  1. Trigger classifier error before valid JSON is produced.
  2. Observe tool or advisor behavior: user-visible path continues as Q&A; returned default includes `task_kind=qa` and minimal other fields.
- **Expected Result**: No unhandled exception to user; safe default applied.
- **Edge Cases / Variants**: Different exception types (timeout, rate limit, connection error).

### TC-015: Invalid JSON from classifier — fallback `task_kind=qa`
- **Type**: Integration
- **Requirement**: FR-11
- **Preconditions**: Force classifier or post-processor to return non-JSON string.
- **Steps**:
  1. Call parsing layer with garbage string.
  2. Assert fallback to QA with logging (log assertion optional if log capture is flaky).
- **Expected Result**: Parse failure absorbed; QA path.
- **Edge Cases / Variants**: Partial JSON; wrong types for fields.

### TC-016: Classifier failure logging does not violate PII norms
- **Type**: Integration (or manual checklist)
- **Requirement**: FR-11
- **Preconditions**: Log capture fixture; representative thread with synthetic PII-like tokens.
- **Steps**:
  1. Induce classifier failure with conversation context present.
  2. Inspect log lines for policy: correlation ids / message ids vs raw full user content (align with existing logging tests).
- **Expected Result**: Sufficient debug context without new PII dumps beyond repo norms.
- **Edge Cases / Variants**: Structured vs string logs.

### TC-017: `save_artifact` guard — reject `cv_draft` without in-trajectory `rewrite_cv`
- **Type**: Integration
- **Requirement**: FR-5, FR-6
- **Preconditions**: ReAct loop with `max_iters=8`; mock advisor or forced tool sequence that calls `save_artifact` for `cv_draft` before `rewrite_cv`.
- **Steps**:
  1. Simulate or drive a trajectory where `classify_intent` indicated `rewrite_cv` if the guard is conditional on that, or apply the agreed predicate: **reject `cv_draft` unless `rewrite_cv` ran in-trajectory**.
  2. Call `save_artifact` with `cv_draft` body without `rewrite_cv` in the same trajectory.
  3. Assert structured failure / error string per existing `save_artifact` patterns; assert no DB row or artifact persistence for that bypass attempt.
- **Expected Result**: Hard rejection; no silent save.
- **Edge Cases / Variants**: Non-`cv_draft` kinds unaffected; `rewrite_cv` in a prior user turn must not count if guard is per current turn only (match engineering predicate).

### TC-018: Guard retry — `rewrite_cv` then `save_artifact` succeeds within `max_iters=8`
- **Type**: Integration
- **Requirement**: FR-6, FR-13
- **Preconditions**: Advisor test harness that counts ReAct iterations; `max_iters=8`.
- **Steps**:
  1. First `save_artifact` `cv_draft` triggers guard.
  2. Agent receives error signal instructing to call `rewrite_cv` first.
  3. Subsequent `rewrite_cv` then `save_artifact` completes successfully.
  4. Assert total iterations ≤ 8 and successful artifact persistence.
- **Expected Result**: Recovery within budget; happy path trace documented.
- **Edge Cases / Variants**: Agent needs `get_full_document` before `rewrite_cv` — still must finish within 8.

### TC-019: `max_iters` configuration is 8 for ReAct advisor
- **Type**: Unit
- **Requirement**: FR-13
- **Preconditions**: Constant or settings object exposed to test.
- **Steps**:
  1. Import or read advisor ReAct configuration.
  2. Assert `max_iters == 8` (or named equivalent).
- **Expected Result**: Regression catch if reverted to 6.
- **Edge Cases / Variants**: Env override disabled or explicitly documented.

### TC-020: `prior_feedback` threaded from classifier JSON into `rewrite_cv` tool
- **Type**: Integration
- **Requirement**: FR-7, FR-8
- **Preconditions**: Mock classifier returns non-empty `prior_feedback`; spy or capture on `rewrite_cv` entry.
- **Steps**:
  1. Run a full advisor turn with `task_kind=rewrite_cv` in mock.
  2. Assert `rewrite_cv` invoked with `prior_feedback` string matching classifier output (or normalized substring).
- **Expected Result**: End-to-end parameter threading through agent tool dispatch.
- **Edge Cases / Variants**: Empty `prior_feedback` omits or passes `""` per signature default.

### TC-021: `prior_feedback` reaches `RewriteCVSignature` and mock rewriter module
- **Type**: Integration
- **Requirement**: FR-7, FR-8
- **Preconditions**: `MockRewriteCVModule` records inputs or embeds `prior_feedback` in deterministic output for assertion.
- **Steps**:
  1. Call rewriter module directly with and without `prior_feedback`.
  2. In agent integration, assert module saw the same string as tool.
- **Expected Result**: Signature field populated; module behavior reflects bullets (e.g., echoed marker in mock output for test).
- **Edge Cases / Variants**: Very long `prior_feedback` — no code-level truncation; test uses moderate length.

### TC-022: `AgentAdvisorSignature` RULES reference `classify_intent` first
- **Type**: Unit
- **Requirement**: FR-2
- **Preconditions**: Access to signature docstring / instructions string.
- **Steps**:
  1. Load RULES text.
  2. Assert mention of calling `classify_intent` first on each turn (wording flexible).
- **Expected Result**: Prompt contract documented in tests to prevent drift.
- **Edge Cases / Variants**: None critical.

### TC-023: CV rewrite turn does not use free-text `response` as primary CV delivery (policy alignment)
- **Type**: Integration
- **Requirement**: FR-5
- **Preconditions**: Mock or constrained LM; inspect final assistant message and artifacts.
- **Steps**:
  1. Execute rewrite flow with `task_kind=rewrite_cv`.
  2. Assert full CV body is delivered via artifact / `rewrite_cv` path, not as ad-hoc pasted CV in violation of RULES (heuristic: no full reconstructed CV in streaming narrative beyond short acknowledgment — exact assertion may mirror existing tests).
- **Expected Result**: Aligns with “must not bypass with inline CV in `response`” where testably enforceable.
- **Edge Cases / Variants**: Hard to assert with free-form LLM in non-mock mode — prefer mock deterministic advisor.

### TC-024: Five-tool parity — `MockAgentAdvisorModule` vs `AgentAdvisorModule`
- **Type**: Integration
- **Requirement**: NFR Testability / mock
- **Preconditions**: Both modules constructable in tests.
- **Steps**:
  1. Compare tool count and names between mock and production wiring.
  2. Run a minimal turn in both modes with `DSPY_MODE=mock`.
- **Expected Result**: No tool mismatch between mock and prod lists.
- **Edge Cases / Variants**: Optional tools behind flags must be documented.

### TC-025: End-to-end — CV rewrite request through chat stream produces draft artifact
- **Type**: System
- **Requirement**: User story 1, Flow 1
- **Preconditions**: Full stack or backend integration with DB; `DSPY_MODE=mock`; authenticated candidate fixture.
- **Steps**:
  1. POST user message requesting CV update (natural language, non-regex-specific phrasing).
  2. Consume stream to completion.
  3. Verify artifact of type CV draft exists and content reflects rewriter output.
- **Expected Result**: User-visible success; artifact retrievable via existing APIs.
- **Edge Cases / Variants**: Follow-up “apply what we discussed” referencing prior turns.

### TC-026: End-to-end — Q&A / smalltalk turn does not force `rewrite_cv`
- **Type**: System
- **Requirement**: User story 3, Flow 2
- **Preconditions**: Same as TC-025; message classified as `qa` or `smalltalk` in mock.
- **Steps**:
  1. Send general admissions question or greeting.
  2. Observe no requirement for `rewrite_cv` in successful completion; no erroneous `save_artifact` guard failures for `cv_draft`.
- **Expected Result**: Smooth response; tool trace optional if instrumented.
- **Edge Cases / Variants**: `task_kind=other`.

### TC-027: End-to-end — classifier degradation path still returns coherent reply
- **Type**: System
- **Requirement**: User story 3, Flow 3
- **Preconditions**: Fault injection in classifier only for this test environment, or mock mode simulating failure.
- **Steps**:
  1. Force classifier failure while rest of stack healthy.
  2. User receives normal assistant reply (QA-style) without hard 500 where avoidable per spec.
- **Expected Result**: Matches FR-11 reliability goal.
- **Edge Cases / Variants**: Verify HTTP status and error body match existing chat error contract.

## Test Data Requirements
- Synthetic chat threads: **>10 messages** for window tests; **<10** for boundary tests.
- Distinct markers in message bodies to prove truncation/windowing.
- Mock keyword fixtures: one minimal input per `task_kind` (`rewrite_cv`, `qa`, `smalltalk`, `other`) for deterministic `MockIntentClassifier`.
- CV sample text and existing document fixtures used by `rewrite_cv` / RAG tests.
- Optional: candidate + thread IDs for system tests; file uploads if full CV requires `get_full_document`.

## Environment Requirements
- **`DSPY_MODE=mock`** for deterministic CI (classifier + rewriter mocks; no network for LLM).
- **Database**: existing test DB for integration/system tests that persist artifacts.
- **Env vars**: `OPENAI_API_KEY` absent or irrelevant when mock tests are isolated; document which tests require key.
- **Fixtures**: ReAct harness or existing `test_agent_advisor_integration.py` patterns for tool traces and iteration counts.
- **Logging**: caplog or equivalent for TC-016 where used.

## Hard-to-Test Areas
- **Production LLM non-determinism (`DSPY_MODE=openai`)**: OpenAI responses may skip tools or wording varies; mitigate with mock-heavy CI and rare smoke tests with retries.
- **Exact narrative shape of assistant message (no inline CV)**: Free-text output is fuzzy; mitigate with mock advisor, substring heuristics, or structured telemetry if added later.
- **`save_artifact` error surface contract**: Spec leaves string vs structured alignment to code review; tests should bind to the implemented return shape and snapshot stable error prefixes if needed.
- **~300 ms added latency**: Not practically asserted in unit tests; use metrics/monitoring post-deploy (NFR).
- **Prior feedback “themes” in prose**: Spec mentions manual spot-checks; automated tests can only use mock rewriter echoes or embedding similarity with caution.

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅

