# QA Test Plan: School Selection Advisor

## Status
COMPLETE

## Coverage Summary
- Unit tests: 18
- Integration tests: 16
- System/E2E tests: 7

---

## Test Cases

---

### TC-001: AdvisorModule produces non-empty output with complete context (mock)
- **Type**: Unit
- **Requirement**: FR-4
- **Preconditions**: `DSPY_MODE=mock` set. `AdvisorModule` (`backend/app/dspy/school_advisor.py`) exists and is importable.
- **Steps**:
  1. Instantiate `AdvisorModule` (mock variant).
  2. Call it with a populated profile dict (background, goals, GMAT score), a single selected school (`{"school": "Harvard Business School", "program_slug": "mba"}`), a per-program evaluation result dict (strengths, weaknesses, priority_actions, narrative_strategy), an empty conversation history, and the user message `"What should I focus on first?"`.
  3. Assert the return value is a non-empty string.
- **Expected Result**: Module returns a non-empty string response without raising.
- **Edge Cases / Variants**: Repeat with multiple selected schools; repeat with empty `priority_actions` list.

---

### TC-002: AdvisorModule handles empty conversation history
- **Type**: Unit
- **Requirement**: FR-4
- **Preconditions**: `DSPY_MODE=mock`.
- **Steps**:
  1. Call `AdvisorModule` with `conversation_history=[]`.
  2. Assert no exception is raised and a non-empty string is returned.
- **Expected Result**: Module gracefully handles first-turn with no prior messages.
- **Edge Cases / Variants**: History with only user messages (no prior assistant turns).

---

### TC-003: AdvisorModule handles multi-turn conversation history
- **Type**: Unit
- **Requirement**: FR-4
- **Preconditions**: `DSPY_MODE=mock`.
- **Steps**:
  1. Build a list of 6 alternating user/assistant messages as the history.
  2. Call `AdvisorModule` with this history and a new user message.
  3. Assert a string response is returned.
- **Expected Result**: Module returns a response without error; history does not cause a crash.
- **Edge Cases / Variants**: History list with 20+ messages (test truncation behaviour if implemented).

---

### TC-004: AdvisorModule receives all required context fields
- **Type**: Unit
- **Requirement**: FR-4
- **Preconditions**: `DSPY_MODE=mock`. A spy/mock wrapper records what the module receives.
- **Steps**:
  1. Call `AdvisorModule` with full context (profile attributes, selected schools, per-program eval, history, user message).
  2. Inspect the signature/inputs to confirm all fields are passed.
- **Expected Result**: The module signature receives `profile_attributes`, `selected_schools`, `evaluation_results`, `conversation_history`, and `user_message` (or equivalent field names).
- **Edge Cases / Variants**: Missing optional profile fields (e.g., no GMAT score).

---

### TC-005: `generate_advisor_response` routing function selects AdvisorModule for advisor-stage threads
- **Type**: Unit
- **Requirement**: FR-5
- **Preconditions**: `DSPY_MODE=mock`. `pipeline.py` updated to include advisor routing.
- **Steps**:
  1. Call the pipeline routing entry point (e.g., `generate_advisor_response` or the updated `generate_assistant_response`) with `thread_stage="advisor"` and a mock context payload.
  2. Assert the returned text is non-empty and `AdvisorModule` was invoked (not `IntakeInterviewer`).
- **Expected Result**: Advisor path is taken; intake interviewer is not called.
- **Edge Cases / Variants**: `thread_stage=None` or `thread_stage="intake"` should NOT invoke `AdvisorModule`.

---

### TC-006: `generate_assistant_response` unchanged behaviour for intake-stage thread
- **Type**: Unit
- **Requirement**: FR-5
- **Preconditions**: `DSPY_MODE=mock`. Pipeline updated with advisor routing.
- **Steps**:
  1. Call `generate_assistant_response` with `thread_stage="intake"` (or absent).
  2. Assert intake interviewer behaviour is preserved (existing unit tests continue to pass).
- **Expected Result**: No regression in intake path.
- **Edge Cases / Variants**: `thread_stage=""` (empty string); `thread_stage="unknown"`.

---

### TC-007: `merge_profile_attributes` writes `selected_schools` with overwrite=True
- **Type**: Unit
- **Requirement**: FR-2
- **Preconditions**: In-memory SQLAlchemy session (or pytest with test DB). A `CandidateProfile` with existing attributes exists.
- **Steps**:
  1. Call `CandidateRepository.merge_profile_attributes(candidate_id, {"selected_schools": [{"school": "HBS", "program_slug": "mba"}]}, overwrite=True)`.
  2. Reload the profile.
  3. Assert `profile.attributes["selected_schools"]` equals the provided list.
- **Expected Result**: `selected_schools` key is present with the correct value.
- **Edge Cases / Variants**: Call again with a different list and verify overwrite replaces the previous value.

---

### TC-008: `merge_profile_attributes` does not clobber pre-existing attributes
- **Type**: Unit
- **Requirement**: FR-2
- **Preconditions**: Profile with `{"gmat_total": 720, "target_schools": ["HBS"]}` in attributes.
- **Steps**:
  1. Call `merge_profile_attributes` with `{"selected_schools": [...]}` and `overwrite=True`.
  2. Reload profile and inspect attributes.
- **Expected Result**: Both `gmat_total` and `selected_schools` are present in `profile.attributes`.
- **Edge Cases / Variants**: `overwrite=False` should not replace existing keys.

---

### TC-009: Opening message generator references confirmed school names
- **Type**: Unit
- **Requirement**: FR-3
- **Preconditions**: `DSPY_MODE=mock`. A function (e.g., `generate_advisor_opening_message`) exists in the dspy layer.
- **Steps**:
  1. Call the opening-message generator with `selected_schools=[{"school": "Stanford GSB", "program_slug": "mba"}]` and a mock evaluation result containing `priority_actions=["Improve GMAT to 730+"]`.
  2. Assert the returned string is non-empty.
- **Expected Result**: Returns a non-empty greeting string. (With real LLM, it would contain school names; with mock, non-empty suffices.)
- **Edge Cases / Variants**: Multiple schools; schools with long names.

---

### TC-010: School selection confirmation API — happy path (200 OK)
- **Type**: Integration
- **Requirement**: FR-2
- **Preconditions**: Test DB running. Candidate exists with `admission_evaluation_result.status = "complete"` in profile attributes. Valid session token.
- **Steps**:
  1. `POST /candidates/me/school-selection/confirm` with `{"selected_schools": [{"school": "Harvard Business School", "program_slug": "mba"}]}` and Bearer token.
  2. Assert HTTP 200.
  3. Assert response body contains `selected_schools` and `"stage": "strategy"`.
  4. Query the DB: `profile.attributes["selected_schools"]` equals the submitted list.
  5. Query the DB: `candidate.stage == CandidateStage.STRATEGY`.
  6. Query the DB: a `StrategyDecision` row exists with `strategy_type = SCHOOL_SELECTION`.
- **Expected Result**: All DB assertions pass; HTTP 200 with correct body.
- **Edge Cases / Variants**: Multiple schools in the list; single school.

---

### TC-011: School selection confirmation API — returns 400 for empty list
- **Type**: Integration
- **Requirement**: FR-2
- **Preconditions**: Candidate with complete evaluation. Valid session token.
- **Steps**:
  1. `POST /candidates/me/school-selection/confirm` with `{"selected_schools": []}`.
  2. Assert HTTP 400.
- **Expected Result**: 400 response; no DB changes.
- **Edge Cases / Variants**: Request body with missing `selected_schools` key entirely (should be 422 Unprocessable Entity).

---

### TC-012: School selection confirmation API — returns 401 for missing/invalid token
- **Type**: Integration
- **Requirement**: FR-2, NFR Security
- **Preconditions**: Endpoint is live.
- **Steps**:
  1. `POST /candidates/me/school-selection/confirm` with no Authorization header.
  2. Assert HTTP 401.
  3. Repeat with an invalid token string.
- **Expected Result**: 401 in both cases; no DB writes.
- **Edge Cases / Variants**: Expired token (if TTL-based); token belonging to a different candidate.

---

### TC-013: School selection confirmation API — returns 409 when evaluation not complete
- **Type**: Integration
- **Requirement**: FR-2
- **Preconditions**: Candidate whose `profile.attributes["admission_evaluation_result"]` is absent OR has `status != "complete"`.
- **Steps**:
  1. `POST /candidates/me/school-selection/confirm` with a valid non-empty school list.
  2. Assert HTTP 409 (or similar graceful error response).
- **Expected Result**: Request rejected; stage not updated.
- **Edge Cases / Variants**: `status = "failed"` vs. `status = "running"` vs. attribute entirely absent.

---

### TC-014: School selection confirmation API — idempotency (upsert behaviour)
- **Type**: Integration
- **Requirement**: FR-2
- **Preconditions**: Candidate with complete evaluation. Valid session token.
- **Steps**:
  1. `POST /candidates/me/school-selection/confirm` with school list A. Assert 200.
  2. Query DB: one `StrategyDecision` row with `strategy_type = SCHOOL_SELECTION`.
  3. `POST /candidates/me/school-selection/confirm` with school list B (different schools). Assert 200.
  4. Query DB: still exactly one `StrategyDecision` row for this candidate with `strategy_type = SCHOOL_SELECTION`; its payload equals list B.
  5. Query DB: `profile.attributes["selected_schools"]` equals list B.
- **Expected Result**: No duplicate `StrategyDecision` rows; second call overwrites the first.
- **Edge Cases / Variants**: Same payload submitted twice; concurrent duplicate requests.

---

### TC-015: School selection confirmation API — cross-candidate isolation
- **Type**: Integration
- **Requirement**: NFR Security
- **Preconditions**: Two candidates A and B both with complete evaluations.
- **Steps**:
  1. Candidate A confirms their selection.
  2. Verify candidate B's `profile.attributes` and `StrategyDecision` are unaffected.
  3. Candidate B attempts to call the endpoint with candidate A's session token — assert 200 only for their own data.
- **Expected Result**: Each candidate's data is isolated.
- **Edge Cases / Variants**: Candidate B explicitly providing candidate A's candidate ID in a crafted request.

---

### TC-016: `POST /chat/threads` with `stage="advisor"` creates advisor thread
- **Type**: Integration
- **Requirement**: FR-3
- **Preconditions**: Candidate has completed school selection (`selected_schools` in profile attributes). Valid session token.
- **Steps**:
  1. `POST /chat/threads` with `{"stage": "advisor"}`.
  2. Assert HTTP 201 and `"created": true`.
  3. Query DB: thread `extra` equals `{"stage": "advisor", "selected_schools": [...]}`.
  4. Query DB: at least one `ChatMessage` with `role = assistant` exists in the thread.
- **Expected Result**: Advisor thread created with correct `extra` metadata and an opening message.
- **Edge Cases / Variants**: Candidate has no `selected_schools` yet (edge: should this fail or use an empty list?).

---

### TC-017: `POST /chat/threads` with `stage="advisor"` is idempotent — returns existing thread
- **Type**: Integration
- **Requirement**: FR-3
- **Preconditions**: Advisor thread already exists for the candidate.
- **Steps**:
  1. `POST /chat/threads` with `{"stage": "advisor"}` a second time.
  2. Assert HTTP 200 and `"created": false`.
  3. Assert `thread_id` matches the previously created thread.
  4. Query DB: only one advisor thread exists for this candidate.
- **Expected Result**: No duplicate threads; same thread ID returned.
- **Edge Cases / Variants**: Multiple rapid concurrent requests (race condition); candidate previously had an intake thread.

---

### TC-018: `POST /chat/threads` without stage parameter still creates intake thread (no regression)
- **Type**: Integration
- **Requirement**: FR-5
- **Preconditions**: Candidate with no existing threads. Valid session token.
- **Steps**:
  1. `POST /chat/threads` with no body (or `{}`).
  2. Assert HTTP 200.
  3. Query DB: thread `extra.stage` equals `"intake"`.
- **Expected Result**: Existing intake behaviour unchanged.
- **Edge Cases / Variants**: `stage="intake"` explicitly; stage field absent.

---

### TC-019: Streaming endpoint routes advisor threads to AdvisorModule
- **Type**: Integration
- **Requirement**: FR-5
- **Preconditions**: `DSPY_MODE=mock`. Advisor thread exists for candidate. Valid session token.
- **Steps**:
  1. `POST /chat/threads/{advisor_thread_id}/messages/stream` with `{"content": "What should I work on?"}`.
  2. Consume the full stream.
  3. Assert HTTP 200 and non-empty streamed content.
  4. Query DB: a new `ChatMessage` with `role = assistant` was persisted.
- **Expected Result**: Advisor module response is streamed and persisted.
- **Edge Cases / Variants**: Empty string content rejected (should be 422); content at max length (50,000 chars).

---

### TC-020: Streaming endpoint does NOT route intake threads to AdvisorModule
- **Type**: Integration
- **Requirement**: FR-5
- **Preconditions**: `DSPY_MODE=mock`. Intake thread exists. Valid session token.
- **Steps**:
  1. `POST /chat/threads/{intake_thread_id}/messages/stream` with a normal user message.
  2. Assert HTTP 200 and non-empty response.
  3. Verify (via logging assertion or mock spy) that `IntakeInterviewer` was called, not `AdvisorModule`.
- **Expected Result**: Intake behaviour is preserved; no regression.
- **Edge Cases / Variants**: Thread with no `extra` field; thread with `extra = {}`.

---

### TC-021: Streaming endpoint returns 404 for an advisor thread owned by a different candidate
- **Type**: Integration
- **Requirement**: NFR Security
- **Preconditions**: Advisor thread belongs to candidate A.
- **Steps**:
  1. Candidate B attempts `POST /chat/threads/{candidate_A_advisor_thread_id}/messages/stream`.
  2. Assert HTTP 404.
- **Expected Result**: Thread not found for unauthorised candidate.
- **Edge Cases / Variants**: Non-existent thread UUID.

---

### TC-022: `GET /chat/threads` returns advisor thread in list
- **Type**: Integration
- **Requirement**: FR-6 (return visit)
- **Preconditions**: Advisor thread exists for candidate.
- **Steps**:
  1. `GET /chat/threads` (or equivalent list endpoint) with valid Bearer token.
  2. Assert the advisor thread appears in the response with `extra.stage = "advisor"`.
- **Expected Result**: Advisor thread is discoverable by the frontend.
- **Edge Cases / Variants**: Candidate has both intake and advisor threads — both appear; no cross-candidate leakage.

---

### TC-023: Advisor thread opening message is available before client connects
- **Type**: Integration
- **Requirement**: FR-3
- **Preconditions**: `DSPY_MODE=mock`. Advisor thread just created via `POST /chat/threads`.
- **Steps**:
  1. Immediately after creation, call `GET /chat/threads/{thread_id}/messages`.
  2. Assert at least one message exists with `role = "assistant"` and non-empty `content`.
- **Expected Result**: Opening message is pre-persisted synchronously during thread creation.
- **Edge Cases / Variants**: Opening message creation fails mid-request (thread created but message not written — verify error handling).

---

### TC-024: Response latency — confirmation API under 500 ms
- **Type**: Integration
- **Requirement**: NFR Performance
- **Preconditions**: Test DB warm. No LLM calls in confirmation endpoint.
- **Steps**:
  1. Time `POST /candidates/me/school-selection/confirm` with a valid 2-school list.
  2. Assert end-to-end response time < 500 ms.
- **Expected Result**: Sub-500 ms response.
- **Edge Cases / Variants**: Run 10 times and assert no single call exceeds 500 ms.

---

### TC-025: Response latency — advisor thread creation returns thread ID within 3 seconds
- **Type**: Integration
- **Requirement**: NFR Performance
- **Preconditions**: `DSPY_MODE=mock` to avoid real LLM latency in CI. Warm DB.
- **Steps**:
  1. Time `POST /chat/threads` with `{"stage": "advisor"}`.
  2. Assert response (including opening message generation) completes within 3 seconds.
- **Expected Result**: Thread ID returned within 3 s.
- **Edge Cases / Variants**: With real LLM (manual smoke test), assert < 5 s.

---

### TC-026: SchoolSelectionConfirm component renders all evaluated programs pre-checked
- **Type**: Unit (component)
- **Requirement**: FR-1
- **Preconditions**: `SchoolSelectionConfirm.tsx` renders with a mock prop `evaluatedPrograms` containing 3 programs.
- **Steps**:
  1. Render the component with `evaluatedPrograms=[{school: "HBS", program_slug: "mba"}, {school: "Stanford GSB", program_slug: "mba"}, {school: "Wharton", program_slug: "mba"}]`.
  2. Assert 3 checkboxes are visible.
  3. Assert all 3 are checked by default.
  4. Assert "Confirm & get advice" button is enabled.
- **Expected Result**: All programs rendered as checked; confirm button active.
- **Edge Cases / Variants**: Single program; zero programs (empty state should not render panel).

---

### TC-027: SchoolSelectionConfirm "Confirm" button disabled when all items are unchecked
- **Type**: Unit (component)
- **Requirement**: FR-1
- **Preconditions**: Component rendered with 2 programs.
- **Steps**:
  1. Uncheck the first program checkbox.
  2. Assert button remains enabled (1 still checked).
  3. Uncheck the second program checkbox.
  4. Assert "Confirm & get advice" button is now disabled.
- **Expected Result**: Button reflects minimum-one-selection constraint.
- **Edge Cases / Variants**: Re-checking a program re-enables the button.

---

### TC-028: SchoolSelectionConfirm submits only checked programs
- **Type**: Unit (component)
- **Requirement**: FR-1
- **Preconditions**: Component rendered with 3 programs; mock `onConfirm` callback.
- **Steps**:
  1. Uncheck program 2 (Stanford GSB).
  2. Click "Confirm & get advice".
  3. Inspect the argument passed to `onConfirm`.
- **Expected Result**: `onConfirm` called with list containing only HBS and Wharton, not Stanford GSB.
- **Edge Cases / Variants**: All 3 checked (submit all); only 1 checked (submit one).

---

### TC-029: SchoolSelectionConfirm displays inline error and preserves state on API failure
- **Type**: Unit (component)
- **Requirement**: NFR Error States
- **Preconditions**: Component with 2 programs; `confirmSchoolSelection` API mock throws an error.
- **Steps**:
  1. Click "Confirm & get advice".
  2. Mock API call rejects with a network error.
  3. Assert an inline error message is visible.
  4. Assert checkboxes retain their prior checked state.
  5. Assert confirm button is re-enabled (user can retry).
- **Expected Result**: Error displayed; no navigation; state preserved.
- **Edge Cases / Variants**: API returns 409 (evaluation not complete) — specific message shown.

---

### TC-030: AdvisorChatPage renders school summary header
- **Type**: Unit (component)
- **Requirement**: FR-6
- **Preconditions**: `AdvisorChatPage` (or `apps/web/src/app/advisor/page.tsx`) renders with mock props including `selectedSchools=[{school: "HBS", program_slug: "mba"}, {school: "Stanford GSB", program_slug: "mba"}]` and an existing thread.
- **Steps**:
  1. Render the page.
  2. Assert school names "Harvard Business School" (or "HBS") and "Stanford GSB" appear in the header area.
- **Expected Result**: Confirmed schools are visible in the header.
- **Edge Cases / Variants**: Long school name does not overflow layout.

---

### TC-031: AdvisorChatPage quick-action chips pre-fill input on click
- **Type**: Unit (component)
- **Requirement**: FR-6
- **Preconditions**: `AdvisorChatPage` rendered with mock data. At least the "Review my CV" chip is present.
- **Steps**:
  1. Click the "Review my CV" chip.
  2. Assert the text input field value equals `"Review my CV"` (or the configured chip text).
  3. Assert focus has moved to the input field.
- **Expected Result**: Input is pre-filled with chip text; user can immediately send or edit.
- **Edge Cases / Variants**: "Help me with my [school] essay" chip — school name interpolated correctly for each selected school.

---

### TC-032: AdvisorChatPage input is disabled while streaming
- **Type**: Unit (component)
- **Requirement**: FR-6
- **Preconditions**: Component in streaming state (mock `isStreaming=true`).
- **Steps**:
  1. Assert the text input and send button are disabled.
  2. Assert quick-action chips are also disabled or non-interactive.
- **Expected Result**: No user interaction possible during streaming.
- **Edge Cases / Variants**: Streaming completes — input re-enabled immediately.

---

### TC-033: AdvisorChatPage displays inline error on streaming failure and re-enables input
- **Type**: Unit (component)
- **Requirement**: NFR Error States
- **Preconditions**: Component with an active thread; streaming mock throws mid-stream.
- **Steps**:
  1. Trigger a message send.
  2. Simulate a streaming error.
  3. Assert an error message ("Something went wrong") is displayed.
  4. Assert the input field is re-enabled.
- **Expected Result**: Error inline; input usable for retry.
- **Edge Cases / Variants**: User retries after error — stream starts fresh for that message.

---

### TC-034: AdvisorChatPage redirects unauthenticated user to sign-in
- **Type**: Unit (component)
- **Requirement**: FR-6
- **Preconditions**: No session token in localStorage; routing mock in place.
- **Steps**:
  1. Render `AdvisorChatPage` or navigate to `/advisor` without a valid session.
  2. Assert redirect to sign-in page.
- **Expected Result**: Unauthenticated users cannot access `/advisor`.
- **Edge Cases / Variants**: Session token expired (treated as unauthenticated).

---

### TC-035: AdvisorChatPage navigates back to dashboard if no advisor thread exists
- **Type**: Unit (component)
- **Requirement**: FR-6
- **Preconditions**: Authenticated candidate whose stage is `PROGRAM_RESEARCH` (no advisor thread, no confirmed schools).
- **Steps**:
  1. Navigate to `/advisor`.
  2. Assert the page redirects (or navigates) back to the dashboard.
- **Expected Result**: No dead state on `/advisor` for candidates who haven't confirmed selection.
- **Edge Cases / Variants**: Candidate with stage `STRATEGY` but whose thread was deleted (edge).

---

### TC-036: CandidateDashboard "Proceed to positioning" button activates when evaluation complete
- **Type**: Unit (component)
- **Requirement**: FR-7
- **Preconditions**: `AdmissionEvaluationPanel` / `EvaluationResultsView` rendered with `evaluationStatus="complete"`.
- **Steps**:
  1. Assert the "Proceed to positioning" button is enabled and clickable.
  2. Click it. Assert `SchoolSelectionConfirm` panel becomes visible.
- **Expected Result**: Button transitions from disabled to enabled; selection panel appears.
- **Edge Cases / Variants**: `evaluationStatus="running"` — button remains disabled; `evaluationStatus="failed"` — error state shown.

---

### TC-037: CandidateDashboard shows "Continue to advisor" for returning STRATEGY-stage candidate
- **Type**: Unit (component)
- **Requirement**: FR-7
- **Preconditions**: Candidate with `stage === "STRATEGY"` and existing advisor thread. Dashboard loads with this state.
- **Steps**:
  1. Render `CandidateDashboard` with candidate stage `"STRATEGY"`.
  2. Assert a "Continue to advisor" button/link is visible (not the evaluation footer / selection panel).
  3. Click it. Assert navigation to `/advisor`.
- **Expected Result**: Returning candidate is taken directly to the advisor.
- **Edge Cases / Variants**: Stage `"NARRATIVE"` or beyond also shows "Continue to advisor" (no regression).

---

### TC-038: Phase indicator advances to strategy phase when stage is STRATEGY
- **Type**: Unit (component)
- **Requirement**: FR-7
- **Preconditions**: `CandidateStitchShell` rendered with `candidate.stage === "STRATEGY"`.
- **Steps**:
  1. Render the shell.
  2. Assert the phase indicator is at the strategy phase (index 2 or equivalent).
- **Expected Result**: Phase indicator reflects advanced stage.
- **Edge Cases / Variants**: Stage `"INTAKE"` shows phase 0; `"PROGRAM_RESEARCH"` shows phase 1.

---

### TC-039: Full flow — first-time school selection to advisor chat
- **Type**: System/E2E
- **Requirement**: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7
- **Preconditions**: Fresh candidate account. Evaluation result pre-seeded as `status: complete` with 2 programs. Valid session.
- **Steps**:
  1. Sign in. Land on `CandidateDashboard`.
  2. Verify evaluation results are visible.
  3. Click "Proceed to positioning". Verify `SchoolSelectionConfirm` panel appears with 2 checked programs.
  4. Uncheck one program. Verify "Confirm & get advice" button remains enabled.
  5. Click "Confirm & get advice".
  6. Verify `POST /candidates/me/school-selection/confirm` called with the 1 checked program.
  7. Verify `POST /chat/threads` called with `stage="advisor"`.
  8. Verify navigation to `/advisor`.
  9. On `/advisor`: verify school name in header; opening assistant message visible; quick-action chips visible.
  10. Type a message and send.
  11. Verify streamed response appears and is saved.
- **Expected Result**: End-to-end flow completes without error. Candidate stage is `STRATEGY` in DB.
- **Edge Cases / Variants**: N/A (happy path E2E).

---

### TC-040: Full flow — evaluation failure state
- **Type**: System/E2E
- **Requirement**: FR-7, NFR Error States
- **Preconditions**: Candidate with `admission_evaluation_result.status = "failed"`.
- **Steps**:
  1. Sign in. Land on `CandidateDashboard`.
  2. Verify error state message is visible in `AdmissionEvaluationPanel`.
  3. Verify "Proceed to positioning" and school selection panel are NOT accessible.
  4. Verify a "Retry evaluation" button is displayed.
- **Expected Result**: Clear error state; no path to advisor until evaluation succeeds.
- **Edge Cases / Variants**: Evaluation transitions from `failed` to `complete` after retry — verify UI recovers.

---

### TC-041: Full flow — returning candidate re-enters existing advisor session
- **Type**: System/E2E
- **Requirement**: FR-7, FR-6
- **Preconditions**: Candidate who previously completed selection and has an advisor thread with 5 messages.
- **Steps**:
  1. Sign in (new browser session / cleared tab).
  2. Land on `CandidateDashboard`.
  3. Verify "Continue to advisor" link is displayed instead of the evaluation footer.
  4. Click it. Navigate to `/advisor`.
  5. Verify all 5 prior messages are loaded in the chat view.
  6. Send a new message and verify it appends to history.
- **Expected Result**: Full conversation history preserved; no selection panel shown; no new thread created.
- **Edge Cases / Variants**: Very long conversation history (50+ messages) — verify performance.

---

### TC-042: Full flow — concurrent confirm + thread creation (idempotency under race)
- **Type**: System/E2E
- **Requirement**: NFR Reliability
- **Preconditions**: Candidate with complete evaluation.
- **Steps**:
  1. Simultaneously fire two `POST /candidates/me/school-selection/confirm` requests (e.g., double-tap simulation).
  2. Await both responses.
  3. Query DB: assert exactly one `StrategyDecision` row exists.
  4. Similarly, fire two `POST /chat/threads` with `stage="advisor"` simultaneously.
  5. Query DB: assert exactly one advisor thread exists.
- **Expected Result**: No duplicate rows in either case; both responses are successful.
- **Edge Cases / Variants**: Network failure on second request after first succeeds.

---

### TC-043: Full flow — quick-action chip sends message and gets advisor response
- **Type**: System/E2E
- **Requirement**: FR-6, FR-4
- **Preconditions**: Candidate on `/advisor` with an existing advisor thread.
- **Steps**:
  1. Click the "Review my CV" chip.
  2. Assert input is pre-filled with "Review my CV".
  3. Press send.
  4. Assert a streamed response appears and is non-empty.
- **Expected Result**: Chip-initiated messages work identically to typed messages.
- **Edge Cases / Variants**: School-specific chip ("Help me with my HBS essay") generates a response mentioning HBS.

---

### TC-044: Full flow — streaming error recovery
- **Type**: System/E2E
- **Requirement**: NFR Error States
- **Preconditions**: Candidate on `/advisor`. Network or server is configured to fail mid-stream (manual test: kill the backend mid-response).
- **Steps**:
  1. Send a message.
  2. Interrupt the server during streaming.
  3. Observe the UI.
  4. Assert "Something went wrong" message appears.
  5. Assert the input field is re-enabled.
  6. Send a new message and assert it succeeds (new stream).
- **Expected Result**: Graceful recovery from streaming failure; no stuck UI state.
- **Edge Cases / Variants**: Backend crashes vs. network disconnect vs. timeout.

---

### TC-045: Full flow — keyboard and screen-reader accessibility for school selection
- **Type**: System/E2E
- **Requirement**: NFR Accessibility
- **Preconditions**: `SchoolSelectionConfirm` panel is open.
- **Steps**:
  1. Using keyboard only (Tab / Space / Enter), navigate to each checkbox and toggle it.
  2. Navigate to the "Confirm & get advice" button and activate it.
  3. Verify each checkbox has a visible `<label>` or `aria-label`.
  4. Open a screen reader (e.g., VoiceOver / NVDA). Verify checkboxes are announced with school and program name.
  5. Verify the confirm button announces its enabled/disabled state.
- **Expected Result**: All interactions achievable via keyboard; screen reader reads meaningful labels.
- **Edge Cases / Variants**: Focus moves to error message when confirmation fails.

---

## Test Data Requirements

- **Candidate with complete evaluation**: A seeded (or factory-created) candidate whose `profile.attributes` includes `admission_evaluation_result: {status: "complete", results: [{school: "Harvard Business School", program_slug: "mba", strengths: [...], weaknesses: [...], priority_actions: [...], narrative_strategy: "...", admission_band: "competitive"}]}`.
- **Candidate with failed evaluation**: `admission_evaluation_result: {status: "failed"}`.
- **Candidate with running evaluation**: `admission_evaluation_result: {status: "running"}` (or attribute absent).
- **Candidate in STRATEGY stage**: Stage set to `CandidateStage.STRATEGY` with `profile.attributes.selected_schools` populated and an advisor `ChatThread` with 5+ messages.
- **Two-candidate isolation fixture**: Two separate candidates (different emails) for cross-candidate security tests.
- **Advisor thread fixture**: A `ChatThread` with `extra = {"stage": "advisor", "selected_schools": [...]}` and an initial assistant `ChatMessage`.
- **Mock DSPy responses**: In `DSPY_MODE=mock`, the `AdvisorModule` mock must return a deterministic non-empty string. Add a `MockAdvisorModule` class mirroring the pattern of `MockIntakeInterviewer`.

---

## Environment Requirements

- `DATABASE_URL` pointing to a local PostgreSQL test database (same as existing test setup).
- `DSPY_MODE=mock` for all automated tests (no real LLM calls, no `OPENAI_API_KEY` required).
- `DSPY_MODE=openai` + `OPENAI_API_KEY` for manual smoke tests and latency benchmarks only.
- `NEXT_PUBLIC_API_URL=http://localhost:8000` for frontend E2E tests.
- Full stack running (`make up`) for E2E tests in TC-039 through TC-045.
- For component unit tests: a React testing environment (e.g., Jest + React Testing Library) consistent with the existing frontend setup.

---

## Hard-to-Test Areas

- **Opening message LLM quality**: The content of the advisor's opening message (FR-3 acceptance criterion: "references at least the confirmed school names and one or more top priority actions") cannot be asserted in automated tests with `DSPY_MODE=mock`. Workaround: in mock mode, assert message is non-empty; add a separate offline DSPy eval script (in `evals/`) that runs with a real LLM against a set of seeded evaluation results and spot-checks output quality.

- **Streaming race condition / idempotency under load** (TC-042): True concurrency is hard to reproduce deterministically in pytest. Workaround: use `asyncio.gather` to fire two coroutines against the test server simultaneously; accept that this is probabilistic coverage rather than a deterministic race test.

- **Advisor DSPy module response coherence across topics** (CV gaps, essay angles, test score strategy, general priorities): Unit tests with `DSPY_MODE=mock` cannot verify that responses are contextually correct. Workaround: add DSPy eval cases in `evals/school_advisor_eval.py` with hand-crafted gold examples for each of the four question types.

- **`CandidateStitchShell` phase indicator** (TC-038): The current component hardcodes `activePhaseIndex={1}` according to the BA analysis. Testing the advancement relies on a prop-driven interface; if the component reads stage from a global store or context, the test setup becomes more involved. Workaround: ensure the phase index is passed as a prop derived from `candidate.stage` in the parent, then assert on the prop value in the component test.

- **Browser-level accessibility testing** (TC-045): Automated axe or Playwright accessibility scans can catch ARIA attribute issues, but screen-reader announcements for `aria-live` regions require manual verification. Workaround: include a manual accessibility checklist in the PR review process; augment with `jest-axe` for static ARIA structure assertions in component tests.

- **Evaluation-complete gate at the database level**: The `409` response (TC-013) depends on `profile.attributes["admission_evaluation_result"]["status"]` being read correctly by the new endpoint. Because this is a JSONB key path check, a typo in the key name silently returns `None` rather than an error. Workaround: add an explicit unit test that calls the relevant repository/service function directly with a profile that has the evaluation result at the wrong key path and asserts an appropriate error is raised.

---

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅

---

> Human checkpoint: review `03-qa-plan.md`, then run `/feature-tasks school-selection-advisor` to continue.
