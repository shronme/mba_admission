# QA Test Plan: Turn Chat Into an Agent with CV Improvement and Essay Review Tools

## Status
COMPLETE

## Coverage Summary
- Unit tests: 24
- Integration tests: 18
- System/E2E tests: 9

---

## Test Cases

### TC-001: AgentAdvisorModule instantiates with correct ReAct configuration
- **Type**: Unit
- **Requirement**: FR-2
- **Preconditions**: `DSPY_MODE=mock` not set; dummy callables available for tools
- **Steps**:
  1. Instantiate `AgentAdvisorModule(retrieve_fn=dummy_fn, save_artifact_fn=dummy_fn)`.
  2. Inspect `module.react` attribute.
- **Expected Result**: `module.react` is a `dspy.ReAct` instance; its `max_iters` is 8; it exposes both `forward` and `aforward` methods.
- **Edge Cases / Variants**: Confirm that passing `max_iters` other than 8 is rejected or overridden per spec.

---

### TC-002: AgentAdvisorModule.forward delegates to dspy.ReAct.forward
- **Type**: Unit
- **Requirement**: FR-2
- **Preconditions**: `dspy.ReAct.forward` stubbed to return a fixed `dspy.Prediction`
- **Steps**:
  1. Call `module.forward(user_message="hello", profile_attributes_json="{}", selected_schools_json="[]", conversation_history="")`.
  2. Assert the stub was called with the same kwargs.
- **Expected Result**: Return value equals the stubbed `dspy.Prediction`.
- **Edge Cases / Variants**: Ensure no extra kwargs are silently dropped.

---

### TC-003: AgentAdvisorModule.aforward is async and delegates to dspy.ReAct.aforward
- **Type**: Unit
- **Requirement**: FR-2
- **Preconditions**: `dspy.ReAct.aforward` stubbed with an `AsyncMock`
- **Steps**:
  1. `await module.aforward(user_message="hello", profile_attributes_json="{}", selected_schools_json="[]", conversation_history="")`.
  2. Assert the async stub was awaited.
- **Expected Result**: Coroutine completes; stub was called once.
- **Edge Cases / Variants**: Verify that calling `aforward` on a sync stub raises `TypeError` (guard against accidental sync call).

---

### TC-004: MockAgentAdvisorModule returns CV artifact for CV-related message
- **Type**: Unit
- **Requirement**: FR-12
- **Preconditions**: `DSPY_MODE=mock`; `MockAgentAdvisorModule` instantiated
- **Steps**:
  1. Call `forward(user_message="help me improve my CV", profile_attributes_json="{}", selected_schools_json="[]", conversation_history="")`.
- **Expected Result**: `prediction.response` contains `"[MOCK]"`; `prediction.artifact_id` equals `"mock-cv-artifact-id"`; `prediction.artifact_type` equals `"cv_draft"`.
- **Edge Cases / Variants**: Message "CV" (uppercase); message "improve cv for wharton".

---

### TC-005: MockAgentAdvisorModule returns essay artifact for essay-related message
- **Type**: Unit
- **Requirement**: FR-12
- **Preconditions**: Same as TC-004
- **Steps**:
  1. Call `forward(user_message="review my essay", ...)`.
- **Expected Result**: `prediction.artifact_type` equals `"essay_draft"`; `prediction.artifact_id` equals `"mock-essay-artifact-id"`.
- **Edge Cases / Variants**: Message "Essay" (mixed case); message with both "cv" and "essay" — confirm CV takes precedence per keyword order in code.

---

### TC-006: MockAgentAdvisorModule returns generic response for unrelated message
- **Type**: Unit
- **Requirement**: FR-12
- **Preconditions**: `DSPY_MODE=mock`
- **Steps**:
  1. Call `forward(user_message="what is the application deadline?", ...)`.
- **Expected Result**: `prediction.response == "[MOCK] How can I help you?"`; no `artifact_id` attribute set (or `None`).
- **Edge Cases / Variants**: Empty string message; None message (should not crash).

---

### TC-007: MockAgentAdvisorModule.aforward delegates to forward
- **Type**: Unit
- **Requirement**: FR-12
- **Preconditions**: `DSPY_MODE=mock`
- **Steps**:
  1. `await mock_module.aforward(user_message="cv")`.
- **Expected Result**: Returns same result as `forward` with no external calls.
- **Edge Cases / Variants**: Confirms `aforward` is awaitable.

---

### TC-008: retrieve_candidate_context returns numbered chunk list scoped to candidate
- **Type**: Unit
- **Requirement**: FR-3
- **Preconditions**: `search_async` stubbed to return 3 `DocumentChunk` objects with `.text` set; `openai_client.embeddings.create` stubbed to return a fixed embedding
- **Steps**:
  1. Call `retrieve_candidate_context("my query")`.
  2. Inspect the returned string.
- **Expected Result**: String is `"[1] <chunk1_text>\n\n[2] <chunk2_text>\n\n[3] <chunk3_text>"`; `search_async` was called with `candidate_id=<correct_id>` and `top_k=8`.
- **Edge Cases / Variants**: Zero chunks returned — should return an empty string or a `"No relevant context found."` placeholder. Exactly 8 chunks — all included. 9 chunks returned by stub — only first 8 included.

---

### TC-009: retrieve_candidate_context does not return chunks belonging to another candidate
- **Type**: Unit
- **Requirement**: FR-3
- **Preconditions**: `search_async` stub captures the `candidate_id` argument
- **Steps**:
  1. Build tool closure with `candidate_id=uuid_A`.
  2. Call `retrieve_candidate_context("query")`.
  3. Assert `search_async` was called with `candidate_id=uuid_A`, never with `uuid_B`.
- **Expected Result**: Cross-candidate leakage is impossible at the tool level.
- **Edge Cases / Variants**: Two concurrent tool closures built for different candidates — each uses its own `candidate_id`.

---

### TC-010: save_artifact with artifact_type="cv_draft" creates a CVDraft row
- **Type**: Unit
- **Requirement**: FR-5
- **Preconditions**: `CVDraftRepository.create` stubbed; session stub available
- **Steps**:
  1. Call `save_artifact(artifact_type="cv_draft", title="Wharton CV", body="<body>", school_name="Wharton")`.
  2. Assert `CVDraftRepository.create` was called with matching fields.
- **Expected Result**: Returns a JSON string containing valid `artifact_id` UUID and `download_url` starting with `/artifacts/`.
- **Edge Cases / Variants**: Repository raises `IntegrityError` — tool should return an `error` string, not crash.

---

### TC-011: save_artifact with artifact_type="essay_draft" creates an EssayDraft row with source="agent"
- **Type**: Unit
- **Requirement**: FR-5
- **Preconditions**: `EssayDraftRepository.create` stubbed
- **Steps**:
  1. Call `save_artifact(artifact_type="essay_draft", title="Booth Essay", body="<feedback>", school_name="Booth")`.
  2. Inspect the stub call arguments.
- **Expected Result**: `source` field passed to repository equals `"agent"`; returned JSON contains `artifact_id` and `download_url`.
- **Edge Cases / Variants**: Second call for same school/type — a new row is created (no upsert); version increment is handled by repository.

---

### TC-012: save_artifact rejects invalid artifact_type
- **Type**: Unit
- **Requirement**: FR-5, NFR (Input Validation)
- **Preconditions**: Tool closure built; no real DB calls
- **Steps**:
  1. Call `save_artifact(artifact_type="malicious_type", title="T", body="B", school_name="S")`.
- **Expected Result**: Returns an error string (not raises exception); no database write occurs.
- **Edge Cases / Variants**: Empty string; `"CV_DRAFT"` (wrong case); SQL injection fragment.

---

### TC-013: save_artifact returns correct download_url format
- **Type**: Unit
- **Requirement**: FR-7
- **Preconditions**: Stub returns a known UUID `"aaaabbbb-..."`
- **Steps**:
  1. Parse JSON from `save_artifact(...)` return value.
- **Expected Result**: `download_url == "/artifacts/aaaabbbb-.../download"` (no host prefix).
- **Edge Cases / Variants**: UUID with all-zero bytes.

---

### TC-014: Pipeline routes advisor-stage thread to AgentAdvisorModule
- **Type**: Unit
- **Requirement**: FR-1
- **Preconditions**: `DSPY_MODE=mock`; `pipeline.generate_assistant_response` importable; `thread_stage="advisor"` passed in
- **Steps**:
  1. Patch `MockAgentAdvisorModule.aforward` with a spy.
  2. Call `generate_assistant_response(..., thread_stage="advisor")`.
  3. Assert the spy was called.
- **Expected Result**: `MockAgentAdvisorModule.aforward` is invoked; `AdvisorModule` (legacy) is not invoked.
- **Edge Cases / Variants**: `thread_stage=None`; `thread_stage="ADVISOR"` (case sensitivity check).

---

### TC-015: Pipeline does not route intake-stage thread to AgentAdvisorModule
- **Type**: Unit
- **Requirement**: FR-1
- **Preconditions**: `DSPY_MODE=mock`
- **Steps**:
  1. Patch `MockAgentAdvisorModule.aforward` with a spy.
  2. Call `generate_assistant_response(..., thread_stage="intake")`.
  3. Assert the spy was NOT called.
- **Expected Result**: Legacy intake module handles the message.
- **Edge Cases / Variants**: `thread_stage="research"`.

---

### TC-016: Essay guardrail does not fire for advisor-stage threads
- **Type**: Unit
- **Requirement**: FR-11
- **Preconditions**: `pipeline.py` imported with guardrail logic accessible
- **Steps**:
  1. Call `generate_assistant_response(user_message="review my essay", thread_stage="advisor")`.
- **Expected Result**: No guardrail response returned; the agent module is called.
- **Edge Cases / Variants**: "write my essay for wharton"; "help me write an essay".

---

### TC-017: Essay guardrail still fires for intake-stage threads
- **Type**: Unit
- **Requirement**: FR-11
- **Preconditions**: Same as TC-016
- **Steps**:
  1. Call `generate_assistant_response(user_message="write my essay", thread_stage="intake")`.
- **Expected Result**: Guardrail response returned without calling the agent.
- **Edge Cases / Variants**: `thread_stage="research"` with "write my essay".

---

### TC-018: Artifact download endpoint returns 401 for missing Bearer token
- **Type**: Unit
- **Requirement**: FR-9
- **Preconditions**: FastAPI test client; route registered
- **Steps**:
  1. `GET /artifacts/some-uuid/download?format=docx` with no `Authorization` header.
- **Expected Result**: HTTP 401.
- **Edge Cases / Variants**: Malformed token `"Bearer not-a-real-token"`.

---

### TC-019: Artifact download endpoint returns 400 for invalid format parameter
- **Type**: Unit
- **Requirement**: FR-9
- **Preconditions**: Valid auth token; artifact exists in DB stub
- **Steps**:
  1. `GET /artifacts/{id}/download?format=xlsx` with valid Bearer token.
- **Expected Result**: HTTP 400.
- **Edge Cases / Variants**: `format=PDF` (wrong case); `format=` (empty); `format` param omitted entirely.

---

### TC-020: Artifact download endpoint returns 404 for nonexistent artifact
- **Type**: Unit
- **Requirement**: FR-9
- **Preconditions**: Valid auth; repository stub returns `None`
- **Steps**:
  1. `GET /artifacts/00000000-0000-0000-0000-000000000000/download?format=docx`.
- **Expected Result**: HTTP 404.
- **Edge Cases / Variants**: Valid UUID format but nonexistent row.

---

### TC-021: Artifact download endpoint returns 403 when artifact belongs to another candidate
- **Type**: Unit
- **Requirement**: FR-9, NFR (Security)
- **Preconditions**: Auth token resolves to `candidate_A`; artifact row has `candidate_id=candidate_B`
- **Steps**:
  1. `GET /artifacts/{id_for_B}/download?format=docx` authenticated as `candidate_A`.
- **Expected Result**: HTTP 403.
- **Edge Cases / Variants**: Artifact ID that exists in `essay_drafts` vs. `cv_drafts` (both tables must be checked for ownership).

---

### TC-022: Artifact download endpoint generates valid .docx for format=docx
- **Type**: Unit
- **Requirement**: FR-9
- **Preconditions**: `python-docx` installed; artifact row with `body` and `title` stubbed
- **Steps**:
  1. `GET /artifacts/{id}/download?format=docx` with valid auth and matching candidate.
  2. Collect response bytes.
- **Expected Result**: HTTP 200; `Content-Type` is `application/vnd.openxmlformats-officedocument.wordprocessingml.document`; `Content-Disposition` includes `filename="<title>.docx"`; response body is a valid ZIP (OOXML) file.
- **Edge Cases / Variants**: Title contains special characters (`"Wharton — CV"`); body is an empty string.

---

### TC-023: Artifact download endpoint generates valid PDF for format=pdf
- **Type**: Unit
- **Requirement**: FR-9
- **Preconditions**: `weasyprint` installed with system fonts; artifact row stubbed
- **Steps**:
  1. `GET /artifacts/{id}/download?format=pdf` with valid auth.
  2. Collect response bytes.
- **Expected Result**: HTTP 200; `Content-Type` is `application/pdf`; `Content-Disposition` includes `filename="<title>.pdf"`; response body starts with `%PDF`.
- **Edge Cases / Variants**: Very long body (10,000+ chars); Unicode characters in body.

---

### TC-024: NDJSON stream emits correct Content-Type for advisor-stage thread
- **Type**: Integration
- **Requirement**: FR-6
- **Preconditions**: `DSPY_MODE=mock`; advisor-stage thread in DB; valid auth
- **Steps**:
  1. `POST /chat/threads/{advisor_thread_id}/messages/stream` with `{"content": "hello"}`.
  2. Inspect response headers before reading body.
- **Expected Result**: `Content-Type: application/x-ndjson`.
- **Edge Cases / Variants**: Confirm `Transfer-Encoding: chunked` is present.

---

### TC-025: NDJSON stream for advisor stage emits valid JSON on every line
- **Type**: Integration
- **Requirement**: FR-6
- **Preconditions**: Same as TC-024
- **Steps**:
  1. Collect full response body; split by `\n`.
  2. Parse each non-empty line as JSON.
- **Expected Result**: All lines parse without error; each has a `type` field.
- **Edge Cases / Variants**: Last line (possibly empty after trailing newline) is handled gracefully.

---

### TC-026: Intake-stage stream response remains text/plain
- **Type**: Integration
- **Requirement**: FR-6
- **Preconditions**: `DSPY_MODE=mock`; intake-stage thread; valid auth
- **Steps**:
  1. `POST /chat/threads/{intake_thread_id}/messages/stream` with any message.
  2. Inspect `Content-Type` header.
- **Expected Result**: `Content-Type: text/plain` (or `text/plain; charset=utf-8`).
- **Edge Cases / Variants**: Research-stage thread also returns `text/plain`.

---

### TC-027: NDJSON stream emits artifact event after mock CV request
- **Type**: Integration
- **Requirement**: FR-6, FR-7
- **Preconditions**: `DSPY_MODE=mock`; advisor-stage thread; valid auth
- **Steps**:
  1. `POST /chat/threads/{id}/messages/stream` with `{"content": "improve my cv"}`.
  2. Parse all NDJSON lines.
  3. Find the line where `type == "artifact"`.
- **Expected Result**: Exactly one `artifact` event; it contains `artifact_id`, `artifact_type="cv_draft"`, `title`, `school_name`, and `download_url` starting with `/artifacts/`.
- **Edge Cases / Variants**: Essay request — `artifact_type="essay_draft"`.

---

### TC-028: NDJSON stream emits text_chunk events that accumulate to full response
- **Type**: Integration
- **Requirement**: FR-6
- **Preconditions**: `DSPY_MODE=mock`; advisor-stage thread
- **Steps**:
  1. Collect all `text_chunk` events from the stream.
  2. Concatenate `value` fields in order.
- **Expected Result**: Concatenated string equals the full agent response (non-empty); no gaps or duplicates.
- **Edge Cases / Variants**: Response with newlines; response containing JSON-like characters.

---

### TC-029: NDJSON stream emits error event on agent loop exception
- **Type**: Integration
- **Requirement**: FR-6
- **Preconditions**: `AgentAdvisorModule.aforward` patched to raise `RuntimeError("test error")`; advisor-stage thread; valid auth
- **Steps**:
  1. Send a message to the advisor stream.
  2. Parse NDJSON lines.
- **Expected Result**: At least one line has `type == "error"` with a non-empty `message` field; stream closes after the error event; no stack trace in `message`.
- **Edge Cases / Variants**: Exception raised partway through tool loop vs. immediately.

---

### TC-030: artifact event download_url has no host prefix
- **Type**: Integration
- **Requirement**: FR-7
- **Preconditions**: `DSPY_MODE=mock`; advisor-stage thread
- **Steps**:
  1. Collect `artifact` event from NDJSON stream.
  2. Inspect `download_url` field.
- **Expected Result**: `download_url` matches the pattern `/artifacts/<uuid>/download` with no `http://` or `https://` prefix.
- **Edge Cases / Variants**: `NEXT_PUBLIC_API_URL` set to a non-localhost value — URL should still be a relative path on the backend.

---

### TC-031: ChatMessage.extra is updated with artifact fields after advisor turn
- **Type**: Integration
- **Requirement**: FR-8
- **Preconditions**: `DSPY_MODE=mock`; advisor-stage thread; `CVDraftRepository` (or mock equivalent) returns a real UUID
- **Steps**:
  1. Send `"improve my cv"` to advisor stream; consume full response.
  2. Query `ChatMessage` row for the assistant message in that turn.
  3. Inspect `extra` JSONB field.
- **Expected Result**: `extra` contains `artifact_id`, `artifact_type`, `title`, `school_name`, and `download_url`; pre-existing `extra` keys are preserved (not wiped).
- **Edge Cases / Variants**: Turn with no artifact (no `save_artifact` call) — `extra` should not gain artifact keys.

---

### TC-032: save_artifact tool persists CVDraft with correct candidate_id and school_name
- **Type**: Integration
- **Requirement**: FR-5
- **Preconditions**: Test database with a candidate row; tool closure built with that candidate's session and ID
- **Steps**:
  1. Call `save_artifact("cv_draft", "Wharton CV", "<body>", "Wharton")`.
  2. Query `cv_drafts` table directly.
- **Expected Result**: One row exists with matching `candidate_id`, `school_name="Wharton"`, `title`, `body`, and `status="draft"`.
- **Edge Cases / Variants**: `school_name=None` — row saved with null school.

---

### TC-033: save_artifact tool persists EssayDraft with source="agent"
- **Type**: Integration
- **Requirement**: FR-5
- **Preconditions**: Test database; tool closure built
- **Steps**:
  1. Call `save_artifact("essay_draft", "Booth Essay", "<feedback>", "Booth")`.
  2. Query `essay_drafts` table.
- **Expected Result**: Row has `source="agent"`, `school_name="Booth"`, `candidate_id` matches.
- **Edge Cases / Variants**: Existing `essay_drafts` rows with `source="human"` are unaffected.

---

### TC-034: Alembic migration creates cv_drafts table with correct schema
- **Type**: Integration
- **Requirement**: Data model (FR-5)
- **Preconditions**: Clean test database; alembic available
- **Steps**:
  1. Run `alembic upgrade head` on a blank database.
  2. Inspect `cv_drafts` table columns, types, and constraints.
- **Expected Result**: Table exists with columns `id` (UUID PK), `candidate_id` (FK → candidates), `school_name` (VARCHAR 255 nullable), `title` (VARCHAR 512 not null), `body` (TEXT not null), `version` (INTEGER default 1), `status` (VARCHAR with check constraint), `extra` (JSONB), `created_at`, `updated_at`; index `ix_cv_drafts_candidate_id` exists.
- **Edge Cases / Variants**: Run `alembic downgrade` — migration is reversible without data loss on a fresh DB.

---

### TC-035: Alembic migration adds source column to essay_drafts with default "human"
- **Type**: Integration
- **Requirement**: Data model (FR-5)
- **Preconditions**: Database with existing `essay_drafts` rows
- **Steps**:
  1. Insert a row into `essay_drafts` before running migration.
  2. Run `alembic upgrade head`.
  3. Query the row.
- **Expected Result**: `source` column exists; pre-existing row has `source="human"`.
- **Edge Cases / Variants**: New insert after migration with no explicit `source` — defaults to `"human"`.

---

### TC-036: retrieve_candidate_context integration with real pgvector search
- **Type**: Integration
- **Requirement**: FR-3
- **Preconditions**: Test database with 3 `DocumentChunk` rows for candidate A and 2 for candidate B; embeddings inserted; `text-embedding-3-small` call stubbed to return a fixed vector
- **Steps**:
  1. Build tool closure for candidate A.
  2. Call `retrieve_candidate_context("test query")`.
  3. Inspect the returned string.
- **Expected Result**: Only candidate A's chunks appear in the result; at most 8 returned.
- **Edge Cases / Variants**: No `DocumentChunk` rows for candidate A — returns empty string or placeholder.

---

### TC-037: CVDraftRepository.create increments version for subsequent saves for same school
- **Type**: Integration
- **Requirement**: FR-5
- **Preconditions**: Test database; candidate row present
- **Steps**:
  1. Create first draft via `CVDraftRepository.create(candidate_id=..., school_name="Wharton", ...)`.
  2. Create second draft with same `candidate_id` and `school_name`.
  3. Query `cv_drafts` and compare `version` values.
- **Expected Result**: Second row has `version=2` (or both rows exist if versioning is by new row, with repository logic setting the version).
- **Edge Cases / Variants**: Different `school_name` — version counter resets to 1.

---

### TC-038: Artifact download integration — docx round-trip
- **Type**: Integration
- **Requirement**: FR-9
- **Preconditions**: Test database with a `cv_drafts` row; `python-docx` installed; auth token for owning candidate
- **Steps**:
  1. `GET /artifacts/{cv_draft_id}/download?format=docx`.
  2. Save bytes to a temp file; open with `python-docx`.
- **Expected Result**: Document opens without error; first paragraph or heading matches `title` field of the draft.
- **Edge Cases / Variants**: Essay draft downloaded as docx — same behavior.

---

### TC-039: Artifact download integration — pdf round-trip
- **Type**: Integration
- **Requirement**: FR-9
- **Preconditions**: Test database with a `cv_drafts` row; `weasyprint` installed with system fonts; auth token
- **Steps**:
  1. `GET /artifacts/{cv_draft_id}/download?format=pdf`.
  2. Inspect first 4 bytes of response body.
- **Expected Result**: Response body starts with `%PDF`; status 200.
- **Edge Cases / Variants**: Body containing HTML-like characters — weasyprint should not interpret them.

---

### TC-040: Full advisor turn with mock module — stream, persist, reload
- **Type**: Integration
- **Requirement**: FR-1, FR-6, FR-7, FR-8
- **Preconditions**: `DSPY_MODE=mock`; advisor-stage thread in test DB; candidate with auth token
- **Steps**:
  1. `POST /chat/threads/{id}/messages/stream` with `{"content": "improve my CV"}`.
  2. Consume stream; confirm `artifact` event received.
  3. `GET /chat/threads/{id}/messages` (history endpoint).
  4. Find the assistant message from this turn.
  5. Check `extra` field.
- **Expected Result**: `extra` on the assistant message contains all required artifact fields; the download card can be reconstructed from this data alone.
- **Edge Cases / Variants**: Multiple sequential artifact turns — each assistant message has its own distinct artifact fields.

---

### TC-041: School-context prompt fired when no school specified (mock mode)
- **Type**: Integration
- **Requirement**: FR-4
- **Preconditions**: `DSPY_MODE=mock`; advisor-stage thread
- **Steps**:
  1. Send `"improve my CV"` (no school name).
  2. Inspect stream output.
- **Expected Result**: Mock module response asks which school; no `artifact` event emitted (no artifact saved yet).
- **Edge Cases / Variants**: Mock module response contains "which school" or equivalent phrasing.

---

### TC-042: Agent does not ask for school when school is present in message
- **Type**: Integration
- **Requirement**: FR-4
- **Preconditions**: `DSPY_MODE=mock`
- **Steps**:
  1. Send `"improve my CV for Wharton"` to advisor stream.
- **Expected Result**: Mock module proceeds to artifact generation; response does not ask for school again. (Full integration test; with real LLM, verified via AgentAdvisorSignature instructions.)
- **Edge Cases / Variants**: School name as part of prior conversation history turn.

---

### TC-043: Quick-action chips visible on advisor page with no messages
- **Type**: System/E2E
- **Requirement**: FR-13
- **Preconditions**: Running dev stack (`make up`); candidate logged in; advisor-stage thread with no prior messages
- **Steps**:
  1. Navigate to `/advisor` page.
  2. Observe chip area.
- **Expected Result**: "Improve my CV" and "Review my essay" chips are both visible.
- **Edge Cases / Variants**: Chips hidden when thread already has messages.

---

### TC-044: "Improve my CV" chip prefills input and submits CV prompt
- **Type**: System/E2E
- **Requirement**: FR-13
- **Preconditions**: Same as TC-043
- **Steps**:
  1. Click "Improve my CV" chip.
  2. Observe the chat input field.
- **Expected Result**: Input is prefilled with a CV-improvement prompt; submitting it reaches the advisor agent stream endpoint.
- **Edge Cases / Variants**: Clicking chip while another message is streaming — chip should be disabled or queue.

---

### TC-045: "Review my essay" chip prefills input and submits essay prompt
- **Type**: System/E2E
- **Requirement**: FR-13
- **Preconditions**: Same as TC-043
- **Steps**:
  1. Click "Review my essay" chip.
- **Expected Result**: Input is prefilled with an essay-review prompt.
- **Edge Cases / Variants**: Same as TC-044.

---

### TC-046: Inline download card renders after advisor turn produces artifact
- **Type**: System/E2E
- **Requirement**: FR-10
- **Preconditions**: `DSPY_MODE=mock` backend running; frontend running; advisor-stage thread; candidate logged in
- **Steps**:
  1. Send "improve my cv" message via UI.
  2. Wait for stream to complete.
  3. Observe assistant chat bubble.
- **Expected Result**: Download card appears at the bottom of the assistant bubble with title, school name, "Download as Word" button, and "Download as PDF" button.
- **Edge Cases / Variants**: Card does not appear for messages that produced no artifact.

---

### TC-047: Download card "Download as Word" button triggers browser file download
- **Type**: System/E2E
- **Requirement**: FR-10
- **Preconditions**: Download card visible from TC-046; `python-docx` installed on backend
- **Steps**:
  1. Click "Download as Word" button.
- **Expected Result**: Browser prompts file save dialog for `<title>.docx`; no navigation away from chat page.
- **Edge Cases / Variants**: Token expiry before click — should receive a meaningful error, not a broken file.

---

### TC-048: Download card "Download as PDF" button triggers browser file download
- **Type**: System/E2E
- **Requirement**: FR-10
- **Preconditions**: Download card visible; `weasyprint` installed on backend
- **Steps**:
  1. Click "Download as PDF" button.
- **Expected Result**: Browser prompts file save dialog for `<title>.pdf`.
- **Edge Cases / Variants**: Same as TC-047.

---

### TC-049: Download card persists after page reload
- **Type**: System/E2E
- **Requirement**: FR-8, FR-10
- **Preconditions**: An artifact has been saved in a prior turn; `ChatMessage.extra` contains artifact fields
- **Steps**:
  1. Reload the browser page.
  2. Scroll to the message that produced the artifact.
- **Expected Result**: Download card is re-rendered with correct title, school, and functional download buttons; no additional API call needed to reconstruct the card.
- **Edge Cases / Variants**: Multiple artifact messages — each shows its own independent card.

---

### TC-050: Advisor chat thinking indicator is visible during ReAct loop
- **Type**: System/E2E
- **Requirement**: NFR (Latency / UX)
- **Preconditions**: Real LLM backend (or a slow mock); advisor-stage thread
- **Steps**:
  1. Send a CV request.
  2. Observe UI between message submission and first `text_chunk` arrival.
- **Expected Result**: A visible progress/thinking indicator (spinner, animated dots, or status text) is shown; UI does not appear frozen.
- **Edge Cases / Variants**: Indicator disappears once the first `text_chunk` arrives.

---

### TC-051: Download card aria-labels are set on both buttons
- **Type**: System/E2E
- **Requirement**: NFR (Accessibility)
- **Preconditions**: Download card rendered in DOM
- **Steps**:
  1. Inspect the DOM for the "Download as Word" button.
  2. Check `aria-label` attribute.
  3. Repeat for "Download as PDF" button.
- **Expected Result**: Both buttons have `aria-label` values that include the file name and format (e.g., `"Download Wharton MBA — Revised CV as Word"`).
- **Edge Cases / Variants**: Focus is not lost from the active element when card renders mid-stream.

---

### TC-052: Agent tool calls are logged at INFO level
- **Type**: Integration
- **Requirement**: NFR (Observability)
- **Preconditions**: `DSPY_MODE=mock`; log capture configured; advisor-stage thread
- **Steps**:
  1. Send a message that triggers artifact generation.
  2. Capture log output.
- **Expected Result**: At least one INFO-level log entry for each tool call, containing tool name, input length, and wall-clock duration; one log entry for ReAct trajectory length.
- **Edge Cases / Variants**: No tools called (generic response) — trajectory length 0 is logged.

---

### TC-053: No cross-candidate artifact access via guessable UUID
- **Type**: Integration
- **Requirement**: NFR (Security)
- **Preconditions**: Two candidates `A` and `B`; B has a `cv_draft` row
- **Steps**:
  1. Authenticate as candidate A.
  2. `GET /artifacts/{B_artifact_id}/download?format=docx`.
- **Expected Result**: HTTP 403; no file bytes returned.
- **Edge Cases / Variants**: Attempt with `essay_draft` owned by B; attempt with a sequential integer ID if old records lacked UUIDs.

---

### TC-054: pytest suite passes with DSPY_MODE=mock and no external services
- **Type**: Integration
- **Requirement**: FR-12, NFR (Testability)
- **Preconditions**: Test database running; no `OPENAI_API_KEY` or `PERPLEXITY_API_KEY` set; `DSPY_MODE=mock`
- **Steps**:
  1. `cd backend && DSPY_MODE=mock pytest -q`.
- **Expected Result**: All tests pass; zero network calls to OpenAI or Perplexity APIs.
- **Edge Cases / Variants**: Tests pass in CI environment with only the test database container.

---

## Test Data Requirements

- A candidate row with a valid UUID and at least one associated `DocumentChunk` row containing text (for RAG integration tests).
- A second candidate row (distinct UUID) for cross-candidate ownership/isolation tests.
- An advisor-stage `ChatThread` row (`extra.stage = "advisor"`) linked to the first candidate.
- An intake-stage `ChatThread` row (`extra.stage = "intake"`) for backward-compatibility tests.
- A research-stage `ChatThread` row for backward-compatibility tests.
- At least one pre-existing `EssayDraft` row with `source` defaulted or omitted (for migration test TC-035).
- A `CVDraft` row (post-migration) for download endpoint tests.
- Valid Bearer tokens for each test candidate (generated via the existing auth flow or seeded).
- A short multi-paragraph text body (100–500 words) to serve as the `body` field for artifact generation tests.
- A Unicode-heavy text sample (accented characters, em dashes) for character-encoding tests on docx/pdf generation.

---

## Environment Requirements

- **Backend**:
  - PostgreSQL 15+ with `pgvector` extension enabled.
  - `DSPY_MODE=mock` for unit and integration tests.
  - `DSPY_MODE=openai` with `OPENAI_API_KEY` for real-LLM E2E tests only.
  - `python-docx` installed (`pip install python-docx`).
  - `weasyprint` installed with system font packages (`apt-get install fonts-liberation` or equivalent in Docker).
  - `DATABASE_URL` pointing to the test database.
  - `PYTHONPATH=.` set when running pytest from `backend/`.

- **Frontend**:
  - `NEXT_PUBLIC_API_URL=http://localhost:8000`.
  - Browser with DevTools for network inspection (TC-047, TC-048).
  - Playwright or Cypress for automated E2E (TC-043 through TC-051).

- **Mocks / Stubs**:
  - `MockAgentAdvisorModule` (already defined in spec) replaces `AgentAdvisorModule` when `DSPY_MODE=mock`.
  - OpenAI embedding endpoint stubbed via `pytest-mock` or `respx` (to avoid real API calls in integration tests).
  - `search_async` can be patched at the module level or replaced with a factory that returns fixture chunks.

---

## Hard-to-Test Areas

- **dspy.ReAct.aforward multi-tool async loop**: The actual multi-step ReAct trajectory (Thought → ToolCall → Observation → repeat) is opaque inside DSPy internals. Testing the exact sequence of tool calls requires either monkey-patching `dspy.ReAct` internals or inspecting trajectory logs. Workaround: test tool functions independently (TC-008 through TC-013) and test the full module only via `MockAgentAdvisorModule`; add a separate real-LLM integration test that verifies at least one `retrieve_candidate_context` call occurred by checking log output.

- **Streaming mid-turn UI state (thinking indicator, TC-050)**: Timing-dependent; requires a deliberately slow mock or real LLM to produce a noticeable gap. Workaround: add an artificial `asyncio.sleep` in the mock's `aforward` for the specific test; or test in E2E with a real slow-response stub.

- **weasyprint font dependencies in CI**: `weasyprint` requires OS-level font packages that may not be present in a minimal CI container. Workaround: add `fonts-liberation` (or `fonts-noto`) to the Dockerfile and test CI image; alternatively, add a CI skip annotation on the PDF E2E test and run it only in the full Docker environment (`make up`).

- **Download card focus management (aria / accessibility, TC-051)**: Automated accessibility assertions require either `axe-core` integration in the test suite or manual inspection. Workaround: add `@axe-core/playwright` to the E2E test setup and assert no critical violations after card render; defer focus-trap verification to manual QA.

- **ReAct max_iters=8 exhaustion behavior**: Testing the exact behavior when the loop exhausts 8 iterations without calling `finish` requires crafting a scenario where the LLM keeps requesting tools. With `DSPY_MODE=mock`, this cannot be forced without patching DSPy internals. Workaround: lower `max_iters` to 1 in a dedicated test and assert an `error` event is emitted; or test by patching `dspy.ReAct` to raise a `MaxIterationsExceeded` exception.

- **Concurrent advisor sessions from the same candidate**: The tool closure pattern captures `session` at request time; verifying that two concurrent requests do not share state requires async concurrency testing. Workaround: run two async tasks simultaneously using `asyncio.gather` in a pytest-asyncio test and assert each closure uses its own `candidate_id`.

---

## Output Artifacts

- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅

---

> Human checkpoint: review `03-qa-plan.md`, then run `/feature-tasks` to continue.
