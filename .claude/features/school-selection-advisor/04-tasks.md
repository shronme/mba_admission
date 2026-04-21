# Development Tasks: School Selection Advisor

## Status
COMPLETE

## Task Summary
Total tasks: 16 | Backend: 8 | Frontend: 6 | Infra: 0 | Test: 2 | Docs: 0

## Tasks

### TASK-001: Extract reusable `StreamingChat` component [frontend]
- **Description**: Create a reusable streaming chat component that encapsulates all stream consumption, message list state, error handling, and submission UI. This is a hard prerequisite (FR-1) to avoid duplicating streaming logic on the new `/advisor` page.
- **Files to create/modify**:
  - `apps/web/src/components/StreamingChat.tsx` (new)
  - `apps/web/src/components/CandidateIntakeForm.tsx`
  - (optional) `apps/web/src/lib/api.ts` (if intake chat helpers should live there)
- **Acceptance criteria**:
  - [ ] `StreamingChat.tsx` exists and exports `StreamingChat(props: StreamingChatProps)`
  - [ ] Component implements the public API specified in the product spec (prefill + onPrefillConsumed)
  - [ ] The component loads message history on mount via `GET /chat/threads/{id}/messages`
  - [ ] The component streams responses via `POST /chat/threads/{id}/messages/stream` and renders an in-progress assistant bubble
  - [ ] Stream errors render inline and the input is re-enabled
  - [ ] `CandidateIntakeForm.tsx` no longer contains direct `fetch` / `ReadableStream` / token-accumulation logic for chat
  - [ ] Intake chat flow has no regressions (thread creation remains in intake; profile callbacks still work)
- **Enables test cases**: TC-032, TC-033 (and reduces risk for TC-039–TC-044)
- **Depends on**: —

### TASK-002: Add frontend API helpers for school selection + advisor thread creation [frontend]
- **Description**: Add typed API client functions for confirming school selection and creating advisor threads, used by the dashboard selection panel and `/advisor`.
- **Files to create/modify**:
  - `apps/web/src/lib/api.ts`
- **Acceptance criteria**:
  - [ ] `confirmSchoolSelection(sessionToken, selectedSchools)` calls `POST /candidates/me/school-selection/confirm`
  - [ ] `createAdvisorThread(sessionToken, { new?: boolean })` calls `POST /chat/advisor-threads` (and supports `?new=true`)
  - [ ] Errors are surfaced as throwables with readable messages for UI inline error display
- **Enables test cases**: TC-028, TC-029, TC-039, TC-041
- **Depends on**: TASK-001 (optional), but can be done in parallel

### TASK-003: Implement `SchoolSelectionConfirm` component (primary + extras sections) [frontend]
- **Description**: Build the school selection checklist panel shown after evaluation completes. Primary evaluated programs are pre-checked; extra recommendations render as opt-in unchecked rows. Confirm CTA requires at least one selection and preserves state on failure.
- **Files to create/modify**:
  - `apps/web/src/components/SchoolSelectionConfirm.tsx` (new)
  - `apps/web/src/components/AdmissionEvaluationPanel.tsx` (or `EvaluationResultsView` file where footer renders)
  - `apps/web/src/lib/api.ts` (uses TASK-002)
- **Acceptance criteria**:
  - [ ] Renders rows for `result.primary` as checked by default
  - [ ] Renders `result.extra` under “Additional recommendations” as unchecked by default
  - [ ] “Confirm & get advice” is disabled when zero are checked
  - [ ] On confirm, calls `confirmSchoolSelection`, then `createAdvisorThread`, then navigates to `/advisor`
  - [ ] If `profile.attributes.selected_schools` already exists on load, panel is skipped and a “Continue with your advisor” CTA is shown
  - [ ] Inline error shown on API failures; checkbox state preserved
- **Enables test cases**: TC-026, TC-027, TC-028, TC-029, TC-036, TC-039
- **Depends on**: TASK-002

### TASK-004: Wire evaluation failed state retry CTA styling/behavior [frontend]
- **Description**: Ensure the evaluation failed state shows an error summary and a primary “Retry evaluation” CTA (and that school selection is inaccessible until evaluation succeeds).
- **Files to create/modify**:
  - `apps/web/src/components/AdmissionEvaluationPanel.tsx`
  - (if needed) any shared `Button` component variants used by the panel
- **Acceptance criteria**:
  - [ ] Failed state displays human-readable message from `result.error`
  - [ ] “Retry evaluation” is styled as primary action
  - [ ] Clicking it calls `POST /candidates/me/admission-evaluation/start` and restarts polling (existing `retryStart` behavior preserved)
- **Enables test cases**: TC-040, TC-036 (failed variant)
- **Depends on**: —

### TASK-005: Backend schema + validation models for selected schools payload [backend]
- **Description**: Add Pydantic schema(s) for the school selection confirm request/response, including validation (non-empty strings, max length 10).
- **Files to create/modify**:
  - `backend/app/api/schemas/` (new or existing appropriate module)
  - (optional) `backend/app/core/` validation helpers if patterns exist
- **Acceptance criteria**:
  - [ ] Request schema matches spec: `{"selected_schools": [{ "school": str, "program_slug": str }]}`
  - [ ] Validation rejects empty list and invalid entries (leading to 400/422 depending on failure type)
  - [ ] Max length constraint (10) enforced
- **Enables test cases**: TC-011, TC-010, TC-012
- **Depends on**: —

### TASK-006: Implement `POST /candidates/me/school-selection/confirm` endpoint [backend]
- **Description**: Persist confirmed school list to `profile.attributes.selected_schools` (via `CandidateRepository.merge_profile_attributes`), upsert `StrategyDecision` for `SCHOOL_SELECTION`, and advance candidate stage to `STRATEGY`, with proper auth + gating.
- **Files to create/modify**:
  - `backend/app/api/routes/` (add endpoint in the appropriate candidates route file)
  - `backend/app/repositories/candidate_repo.py`
  - `backend/app/repositories/strategy_decision_repo.py` (or appropriate repo) / existing upsert method
  - `backend/app/db/models/strategy_decision.py` (only if needed for upsert helper usage; no migrations)
- **Acceptance criteria**:
  - [ ] Requires bearer token auth; returns 401 for invalid token
  - [ ] Returns 400 when `selected_schools` empty/missing (as per spec)
  - [ ] Returns 409 when `admission_evaluation_result.status != "complete"`
  - [ ] Writes `profile.attributes.selected_schools` via `merge_profile_attributes` (no migration)
  - [ ] Upserts exactly one `StrategyDecision` per candidate for `StrategyType.SCHOOL_SELECTION` (overwrite semantics)
  - [ ] Sets `candidate.stage = CandidateStage.STRATEGY`
  - [ ] Responds with `{"selected_schools": [...], "stage": "strategy"}`
- **Enables test cases**: TC-010, TC-011, TC-012, TC-013, TC-014, TC-015, TC-007, TC-008
- **Depends on**: TASK-005

### TASK-007: Implement `POST /chat/advisor-threads` endpoint [backend]
- **Description**: Add a dedicated endpoint to create or retrieve an advisor thread tagged with `extra.stage="advisor"` and `extra.selected_schools=[...]`. It must enforce that selected schools have been confirmed and persist an opening assistant message on new thread creation.
- **Files to create/modify**:
  - `backend/app/api/routes/chat.py`
  - `backend/app/repositories/chat_repo.py`
  - `backend/app/repositories/candidate_repo.py` (read selected_schools)
  - `backend/app/dspy/` (opening message generation helper if placed here)
- **Acceptance criteria**:
  - [ ] With default (`new=false`): return existing active advisor thread if present else create one
  - [ ] With `new=true`: close existing active advisor thread(s) and create a new one
  - [ ] Sets `ChatThread.extra = {"stage":"advisor","selected_schools":[...]}`
  - [ ] Persists an initial assistant `ChatMessage` on new thread creation
  - [ ] Returns `{"thread_id": "<uuid>", "is_new": <bool>}`
  - [ ] Returns 409 if `profile.attributes.selected_schools` absent
  - [ ] Applies `_ensure_thread_owned`/ownership guard patterns consistently
- **Enables test cases**: TC-023, TC-022, TC-025, TC-041
- **Depends on**: TASK-006

### TASK-008: Add opening advisor message generator (mockable) [backend]
- **Description**: Implement a function/module to generate the opening advisor greeting based on confirmed schools + evaluation priority actions. In `DSPY_MODE=mock`, return deterministic non-empty content.
- **Files to create/modify**:
  - `backend/app/dspy/school_advisor.py` (or adjacent helper file)
  - `backend/app/dspy/` mock utilities/pattern mirroring `MockIntakeInterviewer`
- **Acceptance criteria**:
  - [ ] Produces non-empty opening content
  - [ ] In non-mock mode, includes confirmed school names + references priority actions (best-effort)
  - [ ] In mock mode, deterministic non-empty string (CI-friendly)
- **Enables test cases**: TC-009, TC-023
- **Depends on**: TASK-007 (can be implemented earlier, but endpoint needs it)

### TASK-009: Implement `AdvisorModule` DSPy module + mock variant [backend]
- **Description**: Add `AdvisorModule` (and `MockAdvisorModule`) to generate advisor-stage conversational responses grounded in candidate profile, selected schools, evaluation results, and recent history.
- **Files to create/modify**:
  - `backend/app/dspy/school_advisor.py` (new)
  - `backend/app/dspy/__init__.py` (if exports are centralized)
- **Acceptance criteria**:
  - [ ] Module follows existing DSPy patterns (class inheriting `dspy.Module`, `forward` method)
  - [ ] Accepts required context inputs (profile attributes, selected schools, per-program evaluation results, conversation history, user message)
  - [ ] Handles at minimum CV gaps, essay angle, test-score strategy, and “what should I focus on” queries
  - [ ] Mock variant exists for `DSPY_MODE=mock` with deterministic non-empty output
- **Enables test cases**: TC-001, TC-002, TC-003, TC-004
- **Depends on**: —

### TASK-010: Route streaming chat requests to advisor module based on thread stage [backend]
- **Description**: Update streaming handler routing so advisor threads dispatch to `AdvisorModule` (and intake behavior remains unchanged). Must read `thread.extra.stage` from DB before dispatch.
- **Files to create/modify**:
  - `backend/app/api/routes/chat.py`
  - `backend/app/dspy/pipeline.py`
- **Acceptance criteria**:
  - [ ] Streaming endpoint reads `thread.extra.get("stage")` for the thread ID
  - [ ] When `stage=="advisor"`, dispatches to `AdvisorModule`
  - [ ] When stage absent/`"intake"`, behavior unchanged
  - [ ] Add/extend function signature to accept `thread_stage` or create a dedicated advisor generation path
- **Enables test cases**: TC-005, TC-006, TC-019, TC-020, TC-021
- **Depends on**: TASK-009

### TASK-011: Ensure advisor threads are discoverable/listable for return visits [backend]
- **Description**: Confirm the backend supports finding an existing advisor thread for a candidate (either via list endpoint or via `POST /chat/advisor-threads` default behavior). If thread listing exists, ensure advisor threads are included with `extra.stage`.
- **Files to create/modify**:
  - `backend/app/api/routes/chat.py`
  - `backend/app/repositories/chat_repo.py`
- **Acceptance criteria**:
  - [ ] Advisor threads show up in thread list responses (if such endpoint exists and is used by FE)
  - [ ] No cross-candidate leakage
- **Enables test cases**: TC-022
- **Depends on**: TASK-007

### TASK-012: Create `/advisor` page using `StreamingChat` + chips + new thread control [frontend]
- **Description**: Add a Next.js page at `/advisor` that loads candidate/session, enforces selection prerequisite, loads or creates advisor thread, shows selected school pills, and renders `StreamingChat` with quick-action chips and a “Start new conversation” button.
- **Files to create/modify**:
  - `apps/web/src/app/advisor/page.tsx` (new)
  - `apps/web/src/lib/api.ts` (uses TASK-002)
  - `apps/web/src/components/CandidateStitchShell.tsx` (if phase indicator needs a new prop/logic)
- **Acceptance criteria**:
  - [ ] Redirects unauthenticated users to sign-in
  - [ ] If `selected_schools` absent, redirects to dashboard with a notice/toast
  - [ ] Loads existing advisor thread when present; otherwise creates one via `POST /chat/advisor-threads`
  - [ ] Renders header pills for confirmed schools
  - [ ] Renders `StreamingChat` beneath header
  - [ ] Shows 3 quick-action chips that prefill input without auto-submit
  - [ ] “Start new conversation” calls `POST /chat/advisor-threads?new=true` then reloads chat
- **Enables test cases**: TC-030, TC-031, TC-034, TC-035, TC-041, TC-043
- **Depends on**: TASK-001, TASK-002, TASK-007

### TASK-013: Update dashboard navigation/CTAs for strategy stage [frontend]
- **Description**: Update dashboard to (a) surface school selection after evaluation complete, and (b) show a “Continue with your advisor” CTA when `selected_schools` exists or candidate is in `STRATEGY` stage (or later).
- **Files to create/modify**:
  - `apps/web/src/components/CandidateDashboard.tsx`
  - `apps/web/src/components/AdmissionEvaluationPanel.tsx` / evaluation footer component
  - `apps/web/src/components/CandidateStitchShell.tsx`
- **Acceptance criteria**:
  - [ ] When evaluation complete and no selection exists, shows selection panel flow (TASK-003)
  - [ ] When stage is `STRATEGY` (or `selected_schools` present), shows “Continue with your advisor” CTA linking to `/advisor`
  - [ ] Phase indicator advances to phase 3 (strategy) for strategy-stage candidates
- **Enables test cases**: TC-037, TC-038, TC-041
- **Depends on**: TASK-003, TASK-012

### TASK-014: Backend unit tests for advisor module + routing [test]
- **Description**: Add/extend pytest unit tests for `AdvisorModule` (mock mode) and pipeline routing function to ensure advisor-stage dispatch occurs and intake behavior doesn’t regress.
- **Files to create/modify**:
  - `backend/tests/` (new test module(s) as appropriate)
  - `backend/app/dspy/school_advisor.py`
  - `backend/app/dspy/pipeline.py`
- **Acceptance criteria**:
  - [ ] Tests cover TC-001 through TC-006
  - [ ] Runs with `DSPY_MODE=mock`
- **Enables test cases**: TC-001, TC-002, TC-003, TC-004, TC-005, TC-006
- **Depends on**: TASK-009, TASK-010

### TASK-015: Backend integration tests for selection confirm + advisor threads + streaming [test]
- **Description**: Add integration tests for the confirmation endpoint, advisor thread endpoint, and advisor-stage streaming routing, including auth and gating.
- **Files to create/modify**:
  - `backend/tests/` integration test module(s)
  - Test factories/fixtures for candidates/profiles/threads as needed
- **Acceptance criteria**:
  - [ ] Tests cover TC-010 through TC-015, TC-019 through TC-023, and TC-021
  - [ ] Uses `DSPY_MODE=mock` for streaming/advisor responses
- **Enables test cases**: TC-010–TC-015, TC-019–TC-023
- **Depends on**: TASK-006, TASK-007, TASK-010

### TASK-016: Frontend component/unit tests for selection + advisor page (where test infra exists) [frontend]
- **Description**: Implement React component tests for `SchoolSelectionConfirm` and `/advisor` behaviors (chips prefill, redirect rules, streaming disabled state).
- **Files to create/modify**:
  - `apps/web/src/components/SchoolSelectionConfirm.test.tsx` (or existing test conventions)
  - `apps/web/src/app/advisor/page.test.tsx` (or extracted page component tests)
  - `apps/web/src/components/StreamingChat.test.tsx` (optional)
- **Acceptance criteria**:
  - [ ] Covers TC-026–TC-029, TC-030–TC-033, TC-034–TC-038 (as feasible in unit tests)
  - [ ] Mocks API calls; does not require live backend for unit tests
- **Enables test cases**: TC-026–TC-038
- **Depends on**: TASK-001, TASK-003, TASK-012, TASK-013

## Implementation Order
1. TASK-001
2. TASK-002
3. TASK-005
4. TASK-006
5. TASK-007
6. TASK-008
7. TASK-009
8. TASK-010
9. TASK-011
10. TASK-003
11. TASK-004
12. TASK-012
13. TASK-013
14. TASK-014
15. TASK-015
16. TASK-016

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
