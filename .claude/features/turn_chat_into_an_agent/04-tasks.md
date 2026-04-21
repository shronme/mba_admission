# Development Tasks: Turn Chat Into an Agent with CV Improvement and Essay Review Tools

## Status
COMPLETE

## Task Summary
Total tasks: 18 | Backend: 10 | Frontend: 4 | Infra: 1 | Test: 3 | Docs: 0

---

## Tasks

---

### TASK-001: Add python-docx and weasyprint to requirements.txt and Dockerfile [infra]

- **Description**: Add `python-docx` and `weasyprint` to `backend/requirements.txt`. Update the `Dockerfile` (and any `docker-compose` service definition) to install the OS-level font packages required by weasyprint (`fonts-liberation` or `fonts-noto` on Debian/Ubuntu). Verify the image builds cleanly with `docker-compose build` and that `import docx` and `import weasyprint` succeed inside the container.
- **Files to create/modify**:
  - `backend/requirements.txt`
  - `Dockerfile` (backend service)
- **Acceptance criteria**:
  - [ ] `python-docx` appears in `requirements.txt` pinned to a specific version.
  - [ ] `weasyprint` appears in `requirements.txt` pinned to a specific version.
  - [ ] `docker-compose build` completes without errors.
  - [ ] `python -c "import docx; import weasyprint"` exits 0 inside the running backend container.
  - [ ] `pip install -r requirements.txt` succeeds in a clean venv locally (CI baseline).
- **Enables test cases**: TC-022, TC-023, TC-038, TC-039, TC-054
- **Depends on**: —
- **Complexity**: S

---

### TASK-002: Alembic migration — cv_drafts table and essay_drafts.source column [backend]

- **Description**: Create a single Alembic migration that (a) creates the `cv_drafts` table exactly as specified in the product spec data model section, and (b) adds a `source VARCHAR(20) NOT NULL DEFAULT 'human' CHECK (source IN ('agent', 'human'))` column to the existing `essay_drafts` table. The migration must be reversible (`downgrade` drops `cv_drafts` and removes the `source` column). Run `alembic upgrade head` against a local database to confirm.

  Schema for `cv_drafts`:
  ```sql
  CREATE TABLE cv_drafts (
      id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
      school_name  VARCHAR(255),
      title        VARCHAR(512) NOT NULL,
      body         TEXT NOT NULL,
      version      INTEGER NOT NULL DEFAULT 1,
      status       VARCHAR(20) NOT NULL DEFAULT 'draft'
                       CHECK (status IN ('draft', 'submitted', 'archived')),
      extra        JSONB,
      created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE INDEX ix_cv_drafts_candidate_id ON cv_drafts (candidate_id);
  ```
- **Files to create/modify**:
  - `backend/alembic/versions/<timestamp>_add_cv_drafts_and_essay_source.py` (new)
- **Acceptance criteria**:
  - [ ] `alembic upgrade head` on a blank database creates `cv_drafts` with all columns, types, constraints, and the `ix_cv_drafts_candidate_id` index.
  - [ ] `essay_drafts` table gains a `source` column with default `'human'` and check constraint.
  - [ ] Pre-existing `essay_drafts` rows have `source='human'` after the migration runs on a populated database.
  - [ ] `alembic downgrade -1` removes the `cv_drafts` table and drops the `source` column without error.
- **Enables test cases**: TC-034, TC-035
- **Depends on**: —
- **Complexity**: S

---

### TASK-003: CVDraft ORM model and Candidate relationship [backend]

- **Description**: Create `backend/app/db/models/cv_draft.py` defining the `CVDraft` SQLAlchemy 2.0 async ORM model that maps to the `cv_drafts` table from TASK-002. Add the `cv_drafts` relationship to `Candidate` in `backend/app/db/models/candidate.py`. Export `CVDraft` from `backend/app/db/models/__init__.py`. Also update `backend/app/db/models/essay.py` to add the `source` mapped column to `EssayDraft` (matching the migration column).

  The `CVDraft` model mirrors `EssayDraft` with the addition of `version` and the same `status` check values (`draft`, `submitted`, `archived`).
- **Files to create/modify**:
  - `backend/app/db/models/cv_draft.py` (new)
  - `backend/app/db/models/candidate.py`
  - `backend/app/db/models/essay.py`
  - `backend/app/db/models/__init__.py`
- **Acceptance criteria**:
  - [ ] `CVDraft` model has all columns from the migration (`id`, `candidate_id`, `school_name`, `title`, `body`, `version`, `status`, `extra`, `created_at`, `updated_at`).
  - [ ] `Candidate.cv_drafts` relationship is defined with `cascade="all, delete-orphan"` and `lazy="selectin"`.
  - [ ] `EssayDraft.source` mapped column exists with `default="human"`.
  - [ ] `from backend.app.db.models import CVDraft` succeeds without import errors.
  - [ ] `CVDraft.__tablename__ == "cv_drafts"`.
- **Enables test cases**: TC-032, TC-033, TC-037
- **Depends on**: TASK-002
- **Complexity**: S

---

### TASK-004: CVDraftRepository and EssayDraftRepository.source support [backend]

- **Description**: Create `backend/app/repositories/cv_draft_repository.py` with a `CVDraftRepository` class following the existing repository pattern in the codebase. It must implement at minimum:
  - `create(session, candidate_id, school_name, title, body, extra=None) -> CVDraft` — inserts a new row; auto-increments `version` by querying the max version for the same `(candidate_id, school_name)` pair and adding 1.
  - `get_by_id(session, artifact_id, candidate_id) -> CVDraft | None` — returns the row only if `candidate_id` matches (ownership check).

  Also update `backend/app/repositories/essay_draft_repository.py` (or whichever repository handles `EssayDraft`) to accept and persist the `source` field (default `"human"` if not supplied). An `agent`-created essay draft is created by passing `source="agent"`.
- **Files to create/modify**:
  - `backend/app/repositories/cv_draft_repository.py` (new)
  - `backend/app/repositories/essay_draft_repository.py` (or existing essay repository file)
  - `backend/app/repositories/__init__.py` (export new repository)
- **Acceptance criteria**:
  - [ ] `CVDraftRepository.create` inserts a row and returns the persisted `CVDraft` object with a valid UUID `id`.
  - [ ] A second `create` for the same `(candidate_id, school_name)` produces a row with `version=2`.
  - [ ] `CVDraftRepository.get_by_id` returns `None` when `candidate_id` does not match the stored row.
  - [ ] Essay draft repository `create` accepts `source` kwarg; omitting it defaults to `"human"`.
- **Enables test cases**: TC-010, TC-011, TC-032, TC-033, TC-037
- **Depends on**: TASK-003
- **Complexity**: M

---

### TASK-005: AgentAdvisorSignature, AgentAdvisorModule, and MockAgentAdvisorModule [backend]

- **Description**: Create `backend/app/dspy/agent_advisor.py` containing three items:

  1. `AgentAdvisorSignature` — a `dspy.Signature` subclass with the exact fields from the product spec (inputs: `profile_attributes_json`, `selected_schools_json`, `conversation_history`, `user_message`; output: `response`). The docstring must include the school-confirmation instruction.

  2. `AgentAdvisorModule` — a `dspy.Module` that takes `retrieve_fn: Callable` and `save_artifact_fn: Callable` in `__init__`, constructs `dspy.ReAct(AgentAdvisorSignature, tools=[retrieve_fn, save_artifact_fn], max_iters=8)`, and exposes both `forward(**kwargs) -> dspy.Prediction` and `async aforward(**kwargs) -> dspy.Prediction`.

  3. `MockAgentAdvisorModule` — a `dspy.Module` with deterministic `forward` and `async aforward` (delegates to `forward`). When `user_message` contains `"cv"` (case-insensitive), returns `dspy.Prediction(response="[MOCK] Here is your improved CV.", artifact_id="mock-cv-artifact-id", artifact_type="cv_draft")`. When it contains `"essay"`, returns the essay equivalent. Otherwise returns `dspy.Prediction(response="[MOCK] How can I help you?")`.

  No external calls, no database access in this file.
- **Files to create/modify**:
  - `backend/app/dspy/agent_advisor.py` (new)
- **Acceptance criteria**:
  - [ ] `AgentAdvisorModule(retrieve_fn=lambda q: "", save_artifact_fn=lambda **_: "")` instantiates without error.
  - [ ] `module.react` is a `dspy.ReAct` instance with `max_iters=8`.
  - [ ] `AgentAdvisorModule` has both `forward` and `aforward` methods.
  - [ ] `MockAgentAdvisorModule().forward(user_message="help improve my CV", ...)` returns a `dspy.Prediction` with `artifact_type="cv_draft"` and `artifact_id="mock-cv-artifact-id"`.
  - [ ] `MockAgentAdvisorModule().forward(user_message="review my essay", ...)` returns `artifact_type="essay_draft"`.
  - [ ] `MockAgentAdvisorModule().forward(user_message="deadline?", ...)` returns no `artifact_id` (attribute absent or `None`).
  - [ ] `await MockAgentAdvisorModule().aforward(user_message="cv")` returns the same result as `forward`.
- **Enables test cases**: TC-001, TC-002, TC-003, TC-004, TC-005, TC-006, TC-007
- **Depends on**: —
- **Complexity**: M

---

### TASK-006: build_agent_tools — retrieve_candidate_context and save_artifact closures [backend]

- **Description**: Create `backend/app/dspy/agent_tools.py` (or add to `agent_advisor.py`) containing the `build_agent_tools(session, candidate_id, openai_client)` factory function that returns the two tool closures.

  `retrieve_candidate_context(query: str) -> str`:
  - Embeds `query` with `openai_client.embeddings.create(model="text-embedding-3-small", input=query)`.
  - Calls `search_async(session, candidate_id=candidate_id, query_embedding=embedding, top_k=8)` from `backend/app/core/vector_store.py`.
  - Returns `"\n\n".join(f"[{i+1}] {chunk.text}" for i, chunk in enumerate(chunks))`.
  - Returns `"No relevant context found."` if chunks is empty.
  - Logs tool name, input length, and wall-clock duration at INFO level.

  `save_artifact(artifact_type: str, title: str, body: str, school_name: str) -> str`:
  - Validates `artifact_type` against `{"cv_draft", "essay_draft"}`; returns `'{"error": "invalid artifact_type"}'` without writing to DB if invalid.
  - For `"cv_draft"`: calls `CVDraftRepository.create(session, candidate_id, school_name, title, body)`.
  - For `"essay_draft"`: calls the essay draft repository `create` with `source="agent"`.
  - Returns `json.dumps({"artifact_id": str(record.id), "download_url": f"/artifacts/{record.id}/download"})`.
  - Logs tool name, inputs summary, and wall-clock duration at INFO level.

  Both functions are `async def` so they can be awaited inside `dspy.ReAct.aforward`.
- **Files to create/modify**:
  - `backend/app/dspy/agent_tools.py` (new)
- **Acceptance criteria**:
  - [ ] `retrieve_candidate_context` returns a numbered string; `search_async` receives `candidate_id` matching the closure argument and `top_k=8`.
  - [ ] With 0 chunks, returns `"No relevant context found."`.
  - [ ] With 9 chunks from `search_async`, only the first 8 appear in the output (enforced by `top_k=8` or post-filter).
  - [ ] `save_artifact` with `artifact_type="malicious"` returns an error JSON string and does not write to DB.
  - [ ] `save_artifact("cv_draft", ...)` returns JSON with `artifact_id` (valid UUID string) and `download_url` matching `/artifacts/<uuid>/download`.
  - [ ] `save_artifact("essay_draft", ...)` calls the essay draft repository with `source="agent"`.
  - [ ] INFO-level log entries are emitted for each tool call.
- **Enables test cases**: TC-008, TC-009, TC-010, TC-011, TC-012, TC-013, TC-052
- **Depends on**: TASK-004
- **Complexity**: M

---

### TASK-007: Pipeline routing — advisor stage to AgentAdvisorModule, essay guardrail scoping [backend]

- **Description**: Modify `backend/app/dspy/pipeline.py` to make two changes:

  1. **Guardrail scoping**: Find the existing "write my essay" guardrail block. Wrap it with a condition so it only fires when `thread_stage` is NOT `"advisor"`. Leave the existing logic unchanged for all other stages.

  2. **Advisor routing**: In the `elif stage == "advisor":` branch, replace the call to `AdvisorModule()` with:
     ```python
     retrieve_fn, save_fn = build_agent_tools(session, candidate_id, openai_client)
     module = MockAgentAdvisorModule() if DSPY_MODE == "mock" else AgentAdvisorModule(retrieve_fn, save_fn)
     return await module.aforward(
         profile_attributes_json=profile_attributes_json,
         selected_schools_json=selected_schools_json,
         conversation_history=conversation_history,
         user_message=user_message,
     )
     ```
     The `docs_snippets` variable (currently retrieved but unused for the advisor) is NOT passed to the agent; the agent retrieves its own context via the tool.

  `DSPY_MODE` must be read from the environment (already a pattern in the codebase; confirm the import).

  The `session`, `candidate_id`, and `openai_client` must be threaded through from `generate_assistant_response`'s call site — check whether they are already available in that function's signature or need to be added.
- **Files to create/modify**:
  - `backend/app/dspy/pipeline.py`
- **Acceptance criteria**:
  - [ ] With `DSPY_MODE=mock` and `thread_stage="advisor"`, `MockAgentAdvisorModule.aforward` is called.
  - [ ] With `DSPY_MODE=mock` and `thread_stage="intake"`, the legacy intake module is called (not `MockAgentAdvisorModule`).
  - [ ] A message `"review my essay"` with `thread_stage="advisor"` is NOT blocked by the guardrail.
  - [ ] A message `"write my essay"` with `thread_stage="intake"` IS blocked by the guardrail.
  - [ ] `thread_stage="research"` is unaffected by both changes.
- **Enables test cases**: TC-014, TC-015, TC-016, TC-017
- **Depends on**: TASK-005, TASK-006
- **Complexity**: M

---

### TASK-008: NDJSON streaming handler for advisor-stage threads [backend]

- **Description**: Modify `backend/app/api/routes/chat.py` to split the streaming response path based on `thread.extra.stage`:

  - **Non-advisor stages** (intake, research): behaviour unchanged — `text/plain`, word-by-word chunks.
  - **Advisor stage**: return `StreamingResponse` with `media_type="application/x-ndjson"`. The generator must:
    1. Call `pipeline.generate_assistant_response(...)` with `thread_stage="advisor"` to get a `dspy.Prediction`.
    2. Emit the agent's text response as one or more `{"type": "text_chunk", "value": "..."}` lines (break on whitespace boundaries or emit as a single chunk — consistency matters more than granularity here).
    3. After text events, if `prediction.artifact_id` is set, emit one `{"type": "artifact", ...}` event with all required fields (`artifact_id`, `artifact_type`, `title`, `school_name`, `download_url`).
    4. Catch any unhandled exception in the generator and emit `{"type": "error", "message": "<description>"}` before closing (no stack trace in the message value).
    5. Each event line is `json.dumps(event_dict) + "\n"`.
    6. After the stream closes, update `ChatMessage.extra` with the artifact fields (see TASK-009).

  The `title` and `school_name` values for the `artifact` event must come from the `prediction` returned by `save_artifact` (the tool already stores them in the repository) — the route handler retrieves them by looking up the artifact by `artifact_id` OR by having `save_artifact` return those fields in its JSON string (preferred: include them in the tool's return JSON and parse them in the route or pipeline).

  Ensure the `openai_client` and `candidate_id` are passed through to `build_agent_tools` inside `pipeline.py`; if not yet available in the route, extract them from the existing auth dependency and the request's thread lookup.
- **Files to create/modify**:
  - `backend/app/api/routes/chat.py`
- **Acceptance criteria**:
  - [ ] Advisor-stage stream response has `Content-Type: application/x-ndjson`.
  - [ ] Every non-empty line in the advisor stream is valid JSON with a `type` field.
  - [ ] `text_chunk` events accumulate to the full agent response text.
  - [ ] When mock module returns `artifact_id`, exactly one `artifact` event is present as the last event.
  - [ ] `artifact` event contains `artifact_id`, `artifact_type`, `title`, `school_name`, `download_url`.
  - [ ] `download_url` has no host prefix (starts with `/artifacts/`).
  - [ ] An exception in the generator produces an `error` event; no stack trace in `message`.
  - [ ] Intake-stage stream response remains `Content-Type: text/plain`.
- **Enables test cases**: TC-024, TC-025, TC-026, TC-027, TC-028, TC-029, TC-030
- **Depends on**: TASK-007
- **Complexity**: L

---

### TASK-009: Patch ChatMessage.extra with artifact fields after advisor turn [backend]

- **Description**: After the advisor-stage stream generator emits its final event and the stream closes, the `ChatMessage` row for the assistant message in that turn must be updated. Specifically, if an `artifact` event was emitted, fetch the assistant `ChatMessage` by its ID (the route already saves the message before streaming — confirm that `message.id` is available in the generator scope), then `UPDATE chat_messages SET extra = extra || '<artifact_json>'::jsonb WHERE id = <message_id>`.

  Use the existing repository or a direct async session call for this update. The update must be a JSONB merge (`||` operator), not a replacement, to preserve any existing `extra` keys. The update runs after the generator finishes (in a `finally` or post-stream callback), not before, so the download URL is not emitted until after the artifact row is confirmed saved.

  This behaviour applies only to advisor-stage turns that produced an artifact. Turns with no artifact event do not modify `extra`.
- **Files to create/modify**:
  - `backend/app/api/routes/chat.py` (add post-stream patch logic)
  - `backend/app/repositories/chat_message_repository.py` (or whichever handles `ChatMessage`) — add/extend a `patch_extra(session, message_id, extra_dict)` method if not already present.
- **Acceptance criteria**:
  - [ ] After a mock CV advisor turn, the assistant `ChatMessage.extra` contains `artifact_id`, `artifact_type`, `title`, `school_name`, `download_url`.
  - [ ] Pre-existing `extra` keys on the message are not removed.
  - [ ] After a turn with no artifact (generic response), `ChatMessage.extra` does not gain artifact keys.
  - [ ] `GET /chat/threads/{id}/messages` returns the message with the patched `extra` on subsequent fetches.
- **Enables test cases**: TC-031, TC-040, TC-049
- **Depends on**: TASK-008
- **Complexity**: M

---

### TASK-010: Artifact download endpoint — GET /artifacts/{artifact_id}/download [backend]

- **Description**: Add a new route file `backend/app/api/routes/artifacts.py` (or add to an existing routes module) with:

  ```
  GET /artifacts/{artifact_id}/download?format=docx|pdf
  ```

  Steps:
  1. Validate Bearer token via existing `get_candidate_id_from_bearer_token` dependency; return 401 if missing/invalid.
  2. Validate `format` query param is in `{"docx", "pdf"}`; return 400 otherwise.
  3. Look up `artifact_id` in `cv_drafts` first, then `essay_drafts` (both repositories). Return 404 if not found in either.
  4. Check `record.candidate_id == authenticated_candidate_id`; return 403 if mismatch.
  5. Generate the document:
     - `docx`: use `python-docx` — create `Document`, add `Heading(title, level=1)`, add paragraphs by splitting `body` on `\n\n`. Write to `BytesIO`.
     - `pdf`: use `weasyprint` — convert `body` (treated as plain text wrapped in minimal HTML) to PDF via `HTML(string=html_body).write_pdf()`. Write to bytes.
  6. Return `StreamingResponse` with appropriate `Content-Type` and `Content-Disposition: attachment; filename="<title>.<ext>"`.

  Register the router in `backend/app/main.py` (or wherever routes are included) with prefix `/artifacts`.
- **Files to create/modify**:
  - `backend/app/api/routes/artifacts.py` (new)
  - `backend/app/main.py` (register router)
- **Acceptance criteria**:
  - [ ] `GET /artifacts/<id>/download?format=docx` with no auth returns 401.
  - [ ] `format=xlsx` returns 400; `format` omitted returns 400.
  - [ ] Nonexistent `artifact_id` returns 404.
  - [ ] Artifact owned by another candidate returns 403.
  - [ ] Valid `format=docx` returns 200 with correct `Content-Type` and a valid OOXML ZIP body.
  - [ ] Valid `format=pdf` returns 200 with `Content-Type: application/pdf` and body starting with `%PDF`.
  - [ ] `Content-Disposition` filename matches `<title>.docx` / `<title>.pdf`.
- **Enables test cases**: TC-018, TC-019, TC-020, TC-021, TC-022, TC-023, TC-038, TC-039, TC-053
- **Depends on**: TASK-004, TASK-001
- **Complexity**: M

---

### TASK-011: Update save_artifact tool return value to include title and school_name [backend]

- **Description**: The `artifact` streaming event in TASK-008 needs `title` and `school_name` to render the download card. The cleanest way is for `save_artifact` (in `agent_tools.py`) to include these in its returned JSON string:

  ```json
  {"artifact_id": "<uuid>", "artifact_type": "cv_draft", "title": "...", "school_name": "...", "download_url": "/artifacts/<uuid>/download"}
  ```

  Update the `save_artifact` closure in `backend/app/dspy/agent_tools.py` to add `"artifact_type"`, `"title"`, and `"school_name"` to the returned JSON. Update the streaming handler in `chat.py` (TASK-008) to parse these fields from `prediction` or from the last `save_artifact` call result to populate the `artifact` event.

  This task may be done in-line during TASK-006 or TASK-008 if the developer notices the gap. It is listed separately to make the dependency explicit.
- **Files to create/modify**:
  - `backend/app/dspy/agent_tools.py`
- **Acceptance criteria**:
  - [ ] `save_artifact` return JSON includes `artifact_id`, `artifact_type`, `title`, `school_name`, `download_url`.
  - [ ] TC-013 (download_url format check) still passes.
  - [ ] TC-027 `artifact` event includes all five required fields.
- **Enables test cases**: TC-013, TC-027, TC-030
- **Depends on**: TASK-006
- **Complexity**: S

---

### TASK-012: Observability — INFO logging for agent tool calls and ReAct trajectory [backend]

- **Description**: Ensure that every invocation of `retrieve_candidate_context` and `save_artifact` emits a structured INFO log entry including: tool name, input summary (query length for retrieve; `artifact_type` + `school_name` for save), and wall-clock duration in milliseconds. Also log the ReAct trajectory length (number of iterations) after `aforward` completes. Use Python's `logging` module (the existing codebase pattern); do not use `print`.

  The trajectory length can be extracted from `prediction.trajectory` if DSPy exposes it, or estimated by counting the number of tool call observations in `prediction`'s internal state. If not directly accessible, log a note that trajectory logging is best-effort.
- **Files to create/modify**:
  - `backend/app/dspy/agent_tools.py` (logging in closures)
  - `backend/app/dspy/pipeline.py` (trajectory length logging after `aforward`)
- **Acceptance criteria**:
  - [ ] At least one INFO log entry per tool call containing tool name, input length, and duration.
  - [ ] A log entry for trajectory length appears after each advisor `aforward` call.
  - [ ] No `print` statements used.
  - [ ] Logs are emitted in tests captured by pytest's `caplog` fixture.
- **Enables test cases**: TC-052
- **Depends on**: TASK-006, TASK-007
- **Complexity**: S

---

### TASK-013: Frontend — update StreamingChat.tsx to parse NDJSON and render download card [frontend]

- **Description**: Update `apps/web/src/components/StreamingChat.tsx` (or the relevant streaming chat component) to handle both the existing `text/plain` protocol and the new `application/x-ndjson` protocol.

  Detection: After initiating the stream request, inspect `response.headers.get("content-type")`. If it contains `application/x-ndjson`, switch to NDJSON parsing mode; otherwise, use the existing plain-text accumulation path.

  NDJSON mode:
  - Read the response body via `reader = response.body.getReader()`.
  - Split the accumulated buffer on `\n` and parse each non-empty line as JSON.
  - `type === "text_chunk"`: append `event.value` to the streaming assistant message text (same as today's word-by-word accumulation).
  - `type === "artifact"`: store `{artifact_id, artifact_type, title, school_name, download_url}` in the message's local state.
  - `type === "error"`: display the error message inline in the chat bubble.

  Rendering: When a message has `artifact` state set, render an `ArtifactDownloadCard` component (defined in TASK-014) at the bottom of the assistant bubble.

  Persistence: When the stream completes and an artifact was received, the artifact metadata is already in `ChatMessage.extra` on the server (TASK-009). On message history load (`GET /chat/threads/{id}/messages`), detect `message.extra?.artifact_id` and render the download card from that data. Add logic to the existing message-rendering path to check `extra` and pass it to `ArtifactDownloadCard`.
- **Files to create/modify**:
  - `apps/web/src/components/StreamingChat.tsx`
- **Acceptance criteria**:
  - [ ] Advisor-stage stream is parsed as NDJSON; non-advisor streams still work as before.
  - [ ] `text_chunk` events accumulate to full response text visible in the bubble.
  - [ ] When an `artifact` event arrives, `ArtifactDownloadCard` renders below the assistant text.
  - [ ] On message history reload, messages with `extra.artifact_id` render `ArtifactDownloadCard`.
  - [ ] Messages without an artifact show no download card.
  - [ ] An `error` event shows an error notice in the bubble, not a crash.
- **Enables test cases**: TC-046, TC-049, TC-050
- **Depends on**: TASK-008, TASK-009
- **Complexity**: L

---

### TASK-014: Frontend — ArtifactDownloadCard component [frontend]

- **Description**: Create `apps/web/src/components/ArtifactDownloadCard.tsx`. Props:
  ```ts
  interface ArtifactDownloadCardProps {
    artifactId: string;
    artifactType: "cv_draft" | "essay_draft";
    title: string;
    schoolName: string;
    downloadUrl: string; // relative path, e.g. "/artifacts/<uuid>/download"
  }
  ```

  The card renders:
  - A label line showing the artifact title and school name (e.g. "CV Draft saved: Wharton MBA — Revised CV").
  - A "Download as Word" button — on click, triggers authenticated download of `{NEXT_PUBLIC_API_URL}{downloadUrl}?format=docx` by creating a temporary `<a>` element with an object URL, fetching with `Authorization: Bearer <token>` header, and triggering click. Must not navigate away from the page.
  - A "Download as PDF" button — same pattern with `format=pdf`.
  - Both buttons must have `aria-label` attributes in the form `"Download <title> as Word"` and `"Download <title> as PDF"`.
  - A thinking/loading indicator during the download fetch.

  Read the Bearer token from the same localStorage key the rest of the app uses (`apps/web/src/lib/api.ts` or equivalent).
- **Files to create/modify**:
  - `apps/web/src/components/ArtifactDownloadCard.tsx` (new)
- **Acceptance criteria**:
  - [ ] Card renders title and school name.
  - [ ] "Download as Word" button has `aria-label="Download <title> as Word"`.
  - [ ] "Download as PDF" button has `aria-label="Download <title> as PDF"`.
  - [ ] Clicking either button initiates a file download without navigating away.
  - [ ] Download fetch includes `Authorization: Bearer <token>`.
  - [ ] Loading state shown during fetch.
  - [ ] `make lint-fe` passes with no new ESLint errors.
- **Enables test cases**: TC-047, TC-048, TC-051
- **Depends on**: TASK-010
- **Complexity**: M

---

### TASK-015: Frontend — advisor page thinking indicator during ReAct loop [frontend]

- **Description**: Add a visible "thinking" indicator to the advisor chat UI that appears after the user sends a message and before the first `text_chunk` event arrives. This covers the latency gap during the ReAct loop's tool calls.

  Implementation: In the NDJSON streaming path of `StreamingChat.tsx`, after the fetch request is sent but before any `text_chunk` is received, display an animated indicator (spinner, typing dots, or status text such as "Advisor is thinking…") in the assistant bubble position. Remove/replace the indicator when the first `text_chunk` arrives and text starts accumulating.

  The indicator must not appear for non-advisor (text/plain) streams, where the existing streaming behavior is unchanged.
- **Files to create/modify**:
  - `apps/web/src/components/StreamingChat.tsx`
- **Acceptance criteria**:
  - [ ] A visible indicator appears in the chat after message submission, before first text arrives, in advisor-stage threads.
  - [ ] The indicator disappears once the first `text_chunk` is processed.
  - [ ] No indicator appears for intake/research streams.
  - [ ] `make lint-fe` passes.
- **Enables test cases**: TC-050
- **Depends on**: TASK-013
- **Complexity**: S

---

### TASK-016: Frontend — quick-action chips on advisor page [frontend]

- **Description**: Update `apps/web/src/app/advisor/page.tsx` (or `apps/web/src/features/chat/` equivalent for the advisor chat view) to render two quick-action chips: "Improve my CV" and "Review my essay".

  Behaviour:
  - Chips are only visible when the advisor thread has no prior messages (empty history).
  - Clicking "Improve my CV" prefills the chat input with `"Help me improve my CV"` (or an equivalent short prompt that triggers the CV path).
  - Clicking "Review my essay" prefills the chat input with `"Review my essay"`.
  - Chips are disabled while a message is being streamed.
  - Chip layout should fit the existing page styling without breaking the layout on mobile viewport.
- **Files to create/modify**:
  - `apps/web/src/app/advisor/page.tsx` (or the relevant feature component)
- **Acceptance criteria**:
  - [ ] Both chips render when thread message history is empty.
  - [ ] Chips are not visible when the thread has at least one message.
  - [ ] Clicking "Improve my CV" sets the input value to a CV prompt.
  - [ ] Clicking "Review my essay" sets the input value to an essay prompt.
  - [ ] Chips are visually disabled during active streaming.
  - [ ] `make lint-fe` passes.
- **Enables test cases**: TC-043, TC-044, TC-045
- **Depends on**: TASK-013
- **Complexity**: S

---

### TASK-017: Backend unit and integration tests for agent modules and tools [test]

- **Description**: Write pytest tests covering the backend logic introduced in TASK-005, TASK-006, TASK-007, TASK-008, TASK-009, and TASK-010. All tests must pass with `DSPY_MODE=mock` and no external service calls.

  Test file locations follow the existing `backend/tests/` structure. Suggested files:
  - `backend/tests/test_agent_advisor.py` — TC-001 through TC-007 (module instantiation, mock module variants)
  - `backend/tests/test_agent_tools.py` — TC-008 through TC-013 (retrieve and save tool closures, with `search_async` and repositories stubbed via `pytest-mock`)
  - `backend/tests/test_pipeline_routing.py` — TC-014 through TC-017 (advisor routing, guardrail scoping)
  - `backend/tests/test_artifacts_route.py` — TC-018 through TC-023 (download endpoint auth, format validation, docx/pdf generation)
  - `backend/tests/test_chat_stream.py` (extend or create) — TC-024 through TC-031 (NDJSON stream content-type, event structure, artifact event, ChatMessage.extra patch)
  - `backend/tests/test_repositories.py` (extend) — TC-032 through TC-037 (CVDraftRepository.create versioning, essay draft source, migration-level schema tests)

  Use `pytest-asyncio` for async tests. Use `respx` or `pytest-mock` to stub the OpenAI embeddings call in tool tests.
- **Files to create/modify**:
  - `backend/tests/test_agent_advisor.py` (new)
  - `backend/tests/test_agent_tools.py` (new)
  - `backend/tests/test_pipeline_routing.py` (new or extend)
  - `backend/tests/test_artifacts_route.py` (new)
  - `backend/tests/test_chat_stream.py` (new or extend)
  - `backend/tests/test_repositories.py` (extend)
- **Acceptance criteria**:
  - [ ] `cd backend && DSPY_MODE=mock pytest -q` exits 0 with all new tests passing.
  - [ ] TC-001 through TC-040 and TC-052 through TC-054 are covered by automated tests.
  - [ ] No test makes a real network call to OpenAI or Perplexity.
  - [ ] Test coverage for ownership checks (TC-009, TC-021, TC-053) is verified by asserting 403/isolation.
- **Enables test cases**: TC-001 through TC-040, TC-052, TC-053, TC-054
- **Depends on**: TASK-010, TASK-011, TASK-012
- **Complexity**: L

---

### TASK-018: Alembic migration downgrade smoke test and CI environment validation [test]

- **Description**: Verify that `alembic downgrade -1` is clean and that the full migration round-trip works in the Docker test environment. Also confirm that `cd backend && DSPY_MODE=mock pytest -q` passes in the CI Docker environment (i.e., `python-docx` and `weasyprint` are installed and test imports succeed). Add a brief note to `CLAUDE.md` or the backend `README` if there is a section for environment setup, documenting the new font-package requirement for weasyprint.

  This task gates the "migration is reversible" acceptance criterion from TASK-002 being proven in the actual Docker environment, not just locally.
- **Files to create/modify**:
  - CI/Dockerfile verification (no file change required; run as a step in the pipeline)
  - `CLAUDE.md` or backend `README.md` — add weasyprint font dependency note if a setup section exists
- **Acceptance criteria**:
  - [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` completes without error in the Docker container.
  - [ ] `cd backend && DSPY_MODE=mock pytest -q` passes inside the Docker container from `make up`.
  - [ ] `python -c "import weasyprint; weasyprint.HTML(string='<p>test</p>').write_pdf()"` succeeds inside the container.
- **Enables test cases**: TC-034, TC-035, TC-054
- **Depends on**: TASK-001, TASK-002, TASK-017
- **Complexity**: S

---

## Implementation Order

1. TASK-001 — Add python-docx and weasyprint (infrastructure baseline; unblocks docx/pdf work)
2. TASK-002 — Alembic migration (schema must exist before ORM or repository code runs)
3. TASK-003 — CVDraft ORM model and Candidate relationship (depends on migration)
4. TASK-004 — CVDraftRepository and essay draft source support (depends on ORM)
5. TASK-005 — AgentAdvisorModule, MockAgentAdvisorModule (no external deps; can start in parallel with TASK-001)
6. TASK-006 — build_agent_tools closures (depends on TASK-004 for repositories)
7. TASK-011 — Extend save_artifact return value (small fix; best done immediately after TASK-006)
8. TASK-007 — Pipeline routing + guardrail scoping (depends on TASK-005 + TASK-006)
9. TASK-008 — NDJSON streaming handler (depends on TASK-007)
10. TASK-009 — ChatMessage.extra patch after advisor turn (depends on TASK-008)
11. TASK-010 — Artifact download endpoint (depends on TASK-004 + TASK-001)
12. TASK-012 — Observability logging (depends on TASK-006 + TASK-007)
13. TASK-013 — StreamingChat.tsx NDJSON parsing + download card integration (depends on TASK-008, TASK-009)
14. TASK-014 — ArtifactDownloadCard component (depends on TASK-010)
15. TASK-015 — Thinking indicator in advisor chat (depends on TASK-013)
16. TASK-016 — Quick-action chips on advisor page (depends on TASK-013)
17. TASK-017 — Backend unit and integration tests (depends on all backend tasks)
18. TASK-018 — Migration round-trip and CI environment validation (depends on TASK-001, TASK-002, TASK-017)

---

## Output Artifacts

- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
