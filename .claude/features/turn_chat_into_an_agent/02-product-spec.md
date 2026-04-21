# Product Specification: Turn Chat Into an Agent with CV Improvement and Essay Review Tools

## Status
COMPLETE

---

## Overview

The advisor chat currently calls a single `dspy.Predict` module per turn, producing a flat conversational response with no ability to invoke tools, retrieve documents, or persist structured output. This feature replaces that module with a `dspy.ReAct`-based agent that can iteratively call two tools — CV improvement and essay review — retrieve grounded candidate context via RAG, and save the results as downloadable artifacts (Word and PDF) anchored to a specific school application. The download card is rendered inline in the assistant chat bubble so the candidate never leaves the conversation to access their work product. The feature ships only to the `advisor` thread stage; all other thread stages remain on the existing plain-text streaming protocol.

---

## Goals and Success Metrics

- Goal: Enable candidates to produce a school-tailored CV draft or structured essay feedback entirely within the advisor chat, without switching to an external editor.
  - Metric: At least one CV or essay artifact saved per active advisor session within 30 days of launch.

- Goal: Artifacts are immediately downloadable in two formats from the chat bubble.
  - Metric: Download button click-through rate >= 60% among sessions that produce an artifact.

- Goal: The ReAct loop completes and emits its final response in under 30 seconds for the typical case (2-3 tool calls).
  - Metric: p95 agent turn latency < 30 s measured from message submission to `artifact` or final `text_chunk` event.

- Goal: Zero regression in intake and research thread streaming.
  - Metric: No increase in error rate on `POST /chat/threads/{id}/messages/stream` for non-advisor threads post-deploy.

---

## User Stories

| ID | Persona | Action | Benefit |
|----|---------|--------|---------|
| US-1 | Candidate in advisor stage | Says "help me improve my CV" | The agent asks which school, retrieves the CV, generates an improved version, and shows it inline |
| US-2 | Candidate | Tells the agent what to change in a CV draft | The agent revises and shows the updated version in the same conversation |
| US-3 | Candidate | Says "save it" after approving a draft | The agent confirms the school and saves the artifact |
| US-4 | Candidate | Clicks "Download as Word" or "Download as PDF" in the chat bubble | A formatted file downloads to the browser immediately |
| US-5 | Candidate | Pastes an essay and says "review my essay for Wharton" | The agent retrieves profile context and returns structured, personalized feedback |
| US-6 | Candidate | Reloads the page after an artifact was saved | The download buttons are still visible on the relevant message |
| US-7 | Candidate | Starts CV work without specifying a school | The agent proactively asks which school before proceeding |

---

## Functional Requirements

### FR-1: Agent Routing for Advisor Stage
- Description: When `thread.extra.stage == "advisor"`, the pipeline MUST route to `AgentAdvisorModule` instead of the legacy `AdvisorModule`. All other stages (intake, research) continue to use their existing modules unchanged.
- Acceptance Criteria:
  - [ ] A message sent to an advisor-stage thread is handled by `AgentAdvisorModule`.
  - [ ] A message sent to an intake-stage thread is NOT handled by `AgentAdvisorModule`.
  - [ ] Routing decision is made in `pipeline.py` based on `thread_stage`, not on message content.

### FR-2: ReAct Agent with Two Tools
- Description: `AgentAdvisorModule` MUST use `dspy.ReAct` with `max_iters=8`, equipped with two tool functions: `retrieve_candidate_context` and `save_artifact`. The `finish` pseudo-tool is added automatically by DSPy.
- Acceptance Criteria:
  - [ ] `AgentAdvisorModule` wraps `dspy.ReAct` with exactly the two tool functions listed.
  - [ ] `max_iters` is set to 8.
  - [ ] The module exposes both `forward` and `aforward` entry points.

### FR-3: RAG Retrieval Tool
- Description: `retrieve_candidate_context(query: str) -> str` MUST embed the query using `text-embedding-3-small`, call `search_async` scoped to the candidate's `DocumentChunk` rows with `top_k=8`, and return a numbered context block of chunk text for the LLM observation.
- Acceptance Criteria:
  - [ ] Tool returns at most 8 chunks.
  - [ ] Chunks are scoped strictly to the requesting candidate (no cross-candidate leakage).
  - [ ] Returned string is formatted as a numbered list of chunk excerpts.
  - [ ] The tool is a closure capturing `session` and `candidate_id` constructed at request time.

### FR-4: School Selection Before Tool Work
- Description: Before executing CV improvement or essay review, the agent MUST confirm which school the work is for unless the school is already unambiguous from the conversation. This behavior is enforced via the `AgentAdvisorSignature` instructions, not a separate route or middleware.
- Acceptance Criteria:
  - [ ] If the user says "improve my CV" with no school context, the agent's next response is a question asking which school.
  - [ ] If the user says "improve my CV for Wharton", the agent proceeds without asking again.
  - [ ] In mock mode, the mock module returns a hardcoded school-prompt response when no school is detected.

### FR-5: Save Artifact Tool
- Description: `save_artifact(artifact_type: str, title: str, body: str, school_name: str) -> str` MUST persist the artifact to the appropriate table (`cv_drafts` for `artifact_type="cv_draft"`, `essay_drafts` for `artifact_type="essay_draft"`), scoped to `candidate_id` and `school_name`. It MUST return a JSON string containing `artifact_id` and `download_url`.
- Acceptance Criteria:
  - [ ] Calling `save_artifact` with `artifact_type="cv_draft"` creates a row in `cv_drafts`.
  - [ ] Calling `save_artifact` with `artifact_type="essay_draft"` creates a row in `essay_drafts` with `source="agent"`.
  - [ ] The returned JSON includes `artifact_id` (UUID) and `download_url` (path string).
  - [ ] The tool is a closure capturing `session` and `candidate_id`.
  - [ ] A second call for the same school/type creates a new row (version increment logic is handled by the repository, not the tool).

### FR-6: JSON-Lines Streaming Protocol for Advisor Stage
- Description: For advisor-stage threads, `POST /chat/threads/{id}/messages/stream` MUST return `application/x-ndjson` (newline-delimited JSON) instead of `text/plain`. Each line is a JSON object of one of three event types: `text_chunk`, `artifact`, or `error`. Intake and research threads MUST continue to return `text/plain` unchanged.
- Acceptance Criteria:
  - [ ] Advisor-stage stream response has `Content-Type: application/x-ndjson`.
  - [ ] Every line in the advisor stream is a valid JSON object.
  - [ ] `text_chunk` events accumulate to reproduce the full agent text response.
  - [ ] When the agent saves an artifact, one `artifact` event is emitted as the last event in the stream.
  - [ ] `error` events are emitted when the agent loop throws an unhandled exception.
  - [ ] Intake-stage stream response remains `Content-Type: text/plain`.

### FR-7: Artifact Event Carries Full Download Metadata
- Description: The `artifact` streaming event MUST include all fields required for the frontend to render a download card without a secondary API call.
- Acceptance Criteria:
  - [ ] `artifact` event contains `artifact_id`, `artifact_type`, `title`, `school_name`, and `download_url`.
  - [ ] `download_url` is the path `/artifacts/{artifact_id}/download` (no host-prefix; frontend resolves against `NEXT_PUBLIC_API_URL`).

### FR-8: Artifact Persistence in ChatMessage.extra
- Description: When the backend emits an `artifact` event, the `ChatMessage` record for that turn MUST be updated to include `artifact_id`, `artifact_type`, `title`, `school_name`, and `download_url` in its `extra` JSONB field, so that the download button can be reconstructed on page reload.
- Acceptance Criteria:
  - [ ] After a save-artifact turn, `ChatMessage.extra` contains the artifact fields listed above.
  - [ ] On page reload, loading message history returns the artifact metadata and the frontend renders the download buttons.

### FR-9: Artifact Download Endpoint
- Description: `GET /artifacts/{artifact_id}/download?format=docx|pdf` MUST authenticate the request, verify the artifact belongs to the requesting candidate, generate the document in the requested format, and return it as a file attachment.
- Acceptance Criteria:
  - [ ] Returns 401 if Bearer token is missing or invalid.
  - [ ] Returns 403 if the artifact belongs to a different candidate.
  - [ ] Returns 404 if `artifact_id` does not exist.
  - [ ] Returns 400 if `format` is not `docx` or `pdf`.
  - [ ] `format=docx` response has `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document` and a filename of `{title}.docx`.
  - [ ] `format=pdf` response has `Content-Type: application/pdf` and a filename of `{title}.pdf`.
  - [ ] Both formats are available in v1 (both `python-docx` and `weasyprint` ship in v1).

### FR-10: Inline Download Card in Chat Bubble
- Description: When `StreamingChat.tsx` receives an `artifact` event, it MUST render an inline download card at the bottom of the assistant message bubble containing the artifact title, school name, a "Download as Word" button, and a "Download as PDF" button.
- Acceptance Criteria:
  - [ ] Download card renders only on messages that produced an artifact.
  - [ ] "Download as Word" triggers `GET /artifacts/{artifact_id}/download?format=docx` with the Bearer token and initiates a browser download.
  - [ ] "Download as PDF" triggers `GET /artifacts/{artifact_id}/download?format=pdf` with the Bearer token and initiates a browser download.
  - [ ] Download card is re-rendered from `ChatMessage.extra` on page reload.

### FR-11: Essay Guardrail Scoped to Non-Advisor Stages
- Description: The "write my essay" guardrail in `pipeline.py` MUST NOT fire when `thread_stage == "advisor"`. It must continue to fire for intake and research stages.
- Acceptance Criteria:
  - [ ] A message containing "review my essay" in an advisor-stage thread reaches the agent module without being blocked.
  - [ ] The same message in an intake-stage thread is still blocked by the guardrail.

### FR-12: Mock Mode
- Description: When `DSPY_MODE=mock`, `AgentAdvisorModule` MUST be replaced by `MockAgentAdvisorModule`, which returns deterministic output without calling any LLM, embedding, or database function.
- Acceptance Criteria:
  - [ ] `MockAgentAdvisorModule` is instantiated when `DSPY_MODE=mock`.
  - [ ] A message containing "cv" or "CV" returns a hardcoded CV body and emits a fake `artifact_id`.
  - [ ] A message containing "essay" returns hardcoded essay feedback and emits a fake `artifact_id`.
  - [ ] All tests pass with `DSPY_MODE=mock` and no external service calls.

### FR-13: Quick-Action Chips on Advisor Page
- Description: The advisor page MUST surface two quick-action chips — "Improve my CV" and "Review my essay" — that prefill the chat input with a short prompt.
- Acceptance Criteria:
  - [ ] Both chips are visible when the advisor thread has no messages.
  - [ ] Clicking "Improve my CV" prefills the input with a prompt that triggers the CV tool.
  - [ ] Clicking "Review my essay" prefills the input with a prompt that triggers the essay review tool.

---

## Non-Functional Requirements

- **Latency**: p95 end-to-end agent turn latency (message submission to final event) MUST be < 30 seconds for a typical 2-3 tool-call loop. The frontend MUST display a visible progress/thinking indicator between `text_chunk` events during the ReAct loop to avoid the impression of a frozen UI.
- **Security — Artifact Ownership**: Every access to `cv_drafts` and `essay_drafts` via the download endpoint MUST verify that `candidate_id` on the record matches the authenticated candidate. No artifact ID may be accessed by a different candidate. The same `get_candidate_id_from_bearer_token` pattern used throughout the codebase applies.
- **Security — Input Validation**: `artifact_type` in `save_artifact` MUST be validated against the allowed set `{"cv_draft", "essay_draft"}`. Any other value MUST return an error event and not write to the database.
- **Security — Format Validation**: The `format` query parameter on the download endpoint MUST be restricted to `{"docx", "pdf"}`. Any other value returns HTTP 400.
- **Backward Compatibility**: Intake and research thread streaming MUST remain `text/plain` with no behavioral change. Any schema migration MUST be backward-compatible (additive only).
- **Accessibility**: The inline download card MUST include `aria-label` attributes on both download buttons describing the file name and format. Focus must not be lost when the card renders mid-stream.
- **Testability**: All new backend code MUST be exercisable with `DSPY_MODE=mock` and no external service calls. `pytest -q` MUST pass with only a test database and `DSPY_MODE=mock`.
- **Observability**: Agent tool calls MUST be logged at INFO level including tool name, input length, and wall-clock duration. ReAct trajectory length (number of iterations) MUST be logged per turn.

---

## User Flows / API Contracts

### Flow 1: CV Improvement — Happy Path

1. Candidate is in an advisor-stage thread. They click the "Improve my CV" chip or type a similar prompt.
2. Frontend sends `POST /chat/threads/{id}/messages/stream` with the user message.
3. Backend detects `thread_stage == "advisor"`, constructs tool closures bound to `session` and `candidate_id`, instantiates `AgentAdvisorModule`, and calls `aforward`.
4. Agent's first ReAct iteration: no school in context, so it emits a text response asking which school. Backend streams this as `text_chunk` events. Frontend accumulates and renders.
5. Candidate replies "Wharton". Frontend sends second message to the stream endpoint.
6. Agent's iteration: calls `retrieve_candidate_context("CV Wharton MBA")`. Tool embeds query, runs pgvector search, returns top-8 chunks. Agent receives observation.
7. Agent generates an improved CV body. It calls `save_artifact("cv_draft", "Wharton MBA — Revised CV", "<body>", "Wharton")`. Tool persists a `cv_drafts` row, returns `{"artifact_id": "uuid", "download_url": "/artifacts/uuid/download"}`.
8. Agent calls `finish` with a summary response. Backend emits remaining `text_chunk` events, then one `artifact` event, then closes the stream.
9. Backend updates `ChatMessage.extra` with artifact fields.
10. Frontend renders assistant text followed by the download card: title, school, Word button, PDF button.

### Flow 2: Essay Review — Happy Path

1. Candidate pastes an essay and types "review my Booth essay".
2. `POST /chat/threads/{id}/messages/stream` — advisor stage detected.
3. Agent: school is "Booth" from context, no school prompt needed.
4. Agent calls `retrieve_candidate_context("Booth MBA essay candidate profile")`. Returns profile-grounded chunks.
5. Agent generates structured feedback (strengths, weaknesses, suggestions).
6. Agent calls `save_artifact("essay_draft", "Booth Essay — AI Review", "<feedback>", "Booth")`. Tool writes to `essay_drafts` with `source="agent"`, returns artifact metadata.
7. Agent calls `finish`. Backend emits `text_chunk` events then `artifact` event.
8. Frontend renders the feedback text and download card.

### Flow 3: Iterating on a Draft

1. After Flow 1 completes, candidate says "make the opening more concise".
2. Agent has the previous turn in `conversation_history`.
3. Agent calls `retrieve_candidate_context` again if needed, generates a revised body, calls `save_artifact` again (new row, incremented version in repository).
4. A new `artifact` event is emitted; a new download card appears on the new message.

### Flow 4: Download

1. Candidate clicks "Download as Word" on any download card.
2. Frontend calls `GET /artifacts/{artifact_id}/download?format=docx` with `Authorization: Bearer <token>`.
3. Backend verifies ownership, generates `.docx` via `python-docx`, streams the binary.
4. Browser prompts file save dialog.

### Flow 5: Page Reload

1. Candidate reloads the browser.
2. Frontend fetches message history from `GET /chat/threads/{id}/messages`.
3. For each message where `extra.artifact_id` is present, the frontend renders the download card using `extra.artifact_id`, `extra.title`, `extra.school_name`, and `extra.download_url`.
4. Download buttons are functional without a new agent turn.

---

## API Contract

### Modified: POST /chat/threads/{id}/messages/stream

**No change to request shape.**

Request body (existing):
```json
{ "content": "string" }
```

Response — advisor stage:
```
Content-Type: application/x-ndjson
Transfer-Encoding: chunked
```

Each line is one of:

```json
{"type": "text_chunk", "value": "<partial text string>"}
```
```json
{"type": "artifact", "artifact_id": "<uuid>", "artifact_type": "cv_draft|essay_draft", "title": "<string>", "school_name": "<string>", "download_url": "/artifacts/<uuid>/download"}
```
```json
{"type": "error", "message": "<human-readable error string>"}
```

Response — intake/research stage: unchanged (`text/plain`, word-by-word chunks).

Error codes:
- 401: unauthenticated
- 403: thread belongs to another candidate
- 404: thread not found
- 500: agent loop threw unhandled exception (also emitted as `{"type": "error", ...}` in the stream before closing)

---

### New: GET /artifacts/{artifact_id}/download

**Path parameter**: `artifact_id` — UUID

**Query parameter**: `format` — `docx` | `pdf` (required; 400 if absent or invalid)

**Auth**: `Authorization: Bearer <token>` (required)

**Response — success (docx)**:
```
HTTP 200
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="<title>.docx"
<binary stream>
```

**Response — success (pdf)**:
```
HTTP 200
Content-Type: application/pdf
Content-Disposition: attachment; filename="<title>.pdf"
<binary stream>
```

**Error codes**:
| Code | Condition |
|------|-----------|
| 400 | `format` is missing or not in `{docx, pdf}` |
| 401 | Bearer token missing or invalid |
| 403 | `artifact_id` belongs to a different candidate |
| 404 | `artifact_id` does not exist in `cv_drafts` or `essay_drafts` |
| 500 | Document generation failed |

---

## Data Model Changes

### New Table: cv_drafts

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

The `extra` JSONB column stores agent session metadata:
```json
{
  "agent_session_id": "<thread_id>",
  "iteration_count": 3,
  "tool_trajectory_summary": "retrieved CV chunks, generated draft, saved"
}
```

---

### Modified Table: essay_drafts — Add `source` Column

```sql
ALTER TABLE essay_drafts
    ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'human'
        CHECK (source IN ('agent', 'human'));
```

This column is added in the same Alembic migration as `cv_drafts`. Existing rows get `source='human'` via the column default. Agent-generated drafts are written with `source='agent'`.

---

### Modified Model: ChatMessage.extra — Artifact Fields

When a turn produces an artifact, the `ChatMessage` record's `extra` JSONB field is updated to include:

```json
{
  "artifact_id": "<uuid>",
  "artifact_type": "cv_draft|essay_draft",
  "title": "<string>",
  "school_name": "<string>",
  "download_url": "/artifacts/<uuid>/download"
}
```

Pre-existing `extra` keys on the message are preserved (merged, not replaced).

---

### Modified Model: Candidate — cv_drafts Relationship

Add to `backend/app/db/models/candidate.py`:

```python
cv_drafts: Mapped[list["CVDraft"]] = relationship(
    "CVDraft",
    back_populates="candidate",
    cascade="all, delete-orphan",
    lazy="selectin",
)
```

---

## Streaming Protocol Spec

The advisor-stage stream uses newline-delimited JSON (`application/x-ndjson`). Each event is a single UTF-8 JSON object terminated by `\n`. Clients MUST process events line-by-line.

### text_chunk

Emitted for each partial text token produced by the agent's final `finish` response (and for any intermediate "thinking" status text the implementation chooses to emit).

```json
{"type": "text_chunk", "value": "Here is your revised CV for Wharton:\n\n"}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| type | string | yes | Always `"text_chunk"` |
| value | string | yes | Partial text; accumulate in order to reconstruct full response |

### artifact

Emitted once per turn, after all `text_chunk` events, when `save_artifact` was called during the ReAct loop. There is at most one `artifact` event per stream response.

```json
{
  "type": "artifact",
  "artifact_id": "3f2a1b4c-...",
  "artifact_type": "cv_draft",
  "title": "Wharton MBA — Revised CV",
  "school_name": "Wharton",
  "download_url": "/artifacts/3f2a1b4c-.../download"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| type | string | yes | Always `"artifact"` |
| artifact_id | string (UUID) | yes | Stable ID for the persisted record |
| artifact_type | string | yes | `"cv_draft"` or `"essay_draft"` |
| title | string | yes | Display title for the download card |
| school_name | string | yes | School the artifact is associated with |
| download_url | string | yes | Relative path; resolve against `NEXT_PUBLIC_API_URL` |

### error

Emitted when an unhandled exception occurs during the agent loop. The stream is closed immediately after this event.

```json
{"type": "error", "message": "Agent loop exceeded max iterations"}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| type | string | yes | Always `"error"` |
| message | string | yes | Human-readable description; do not include stack traces in production |

---

## Agent Architecture

### AgentAdvisorSignature

```python
class AgentAdvisorSignature(dspy.Signature):
    """You are an MBA admissions advisor. Before starting CV or essay work, confirm
    which school the candidate is targeting unless it is already clear from context.
    Use retrieve_candidate_context to ground your responses in the candidate's actual
    documents. Use save_artifact when the candidate approves a draft."""

    profile_attributes_json: str = dspy.InputField(
        desc="Candidate profile attributes as JSON"
    )
    selected_schools_json: str = dspy.InputField(
        desc="Schools the candidate is applying to as JSON"
    )
    conversation_history: str = dspy.InputField(
        desc="Full conversation history, newest last"
    )
    user_message: str = dspy.InputField(desc="The candidate's latest message")
    response: str = dspy.OutputField(
        desc="The advisor's response to the candidate"
    )
```

### AgentAdvisorModule

```python
class AgentAdvisorModule(dspy.Module):
    def __init__(self, retrieve_fn: Callable, save_artifact_fn: Callable):
        super().__init__()
        self.react = dspy.ReAct(
            AgentAdvisorSignature,
            tools=[retrieve_fn, save_artifact_fn],
            max_iters=8,
        )

    def forward(self, **kwargs) -> dspy.Prediction:
        return self.react(**kwargs)

    async def aforward(self, **kwargs) -> dspy.Prediction:
        return await self.react.aforward(**kwargs)
```

### Tool Closure Pattern

Tool functions are constructed at request time in the route handler and capture `session` and `candidate_id` via closure. This avoids any dependency injection framework.

```python
def build_agent_tools(session: AsyncSession, candidate_id: UUID, openai_client: AsyncOpenAI):

    async def retrieve_candidate_context(query: str) -> str:
        """Retrieve relevant sections from the candidate's uploaded documents."""
        embedding_response = await openai_client.embeddings.create(
            model="text-embedding-3-small", input=query
        )
        embedding = embedding_response.data[0].embedding
        chunks = await search_async(
            session, candidate_id=candidate_id,
            query_embedding=embedding, top_k=8
        )
        return "\n\n".join(
            f"[{i+1}] {chunk.text}" for i, chunk in enumerate(chunks)
        )

    async def save_artifact(
        artifact_type: str, title: str, body: str, school_name: str
    ) -> str:
        """Save a CV or essay draft and return artifact_id and download_url."""
        # validate artifact_type
        # persist to cv_drafts or essay_drafts
        # return JSON string
        ...

    return retrieve_candidate_context, save_artifact
```

### MockAgentAdvisorModule

Used when `DSPY_MODE=mock`. Implements the same interface as `AgentAdvisorModule` with no external calls.

```python
class MockAgentAdvisorModule(dspy.Module):
    def forward(self, user_message: str, **kwargs) -> dspy.Prediction:
        msg = user_message.lower()
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
```

### Pipeline Integration Point

In `pipeline.py`, the routing condition changes from:

```python
# before
elif stage == "advisor":
    return AdvisorModule()(...)
```

to:

```python
# after
elif stage == "advisor":
    retrieve_fn, save_fn = build_agent_tools(session, candidate_id, openai_client)
    module = MockAgentAdvisorModule() if DSPY_MODE == "mock" else AgentAdvisorModule(retrieve_fn, save_fn)
    return await module.aforward(...)
```

The `docs_snippets` variable (previously retrieved but unused for the advisor) is not passed into the agent — the agent retrieves its own context via the tool.

---

## Out of Scope

- A "Saved Artifacts" tab or Documents page listing all CV and essay drafts. The download button exists only inline in chat for v1.
- Multi-turn artifact versioning UI (showing diff between iterations). Each save creates a new row; no version history UI in v1.
- Artifact sharing or export to a third-party service (Dropbox, Google Drive, etc.).
- Human-authored CV uploads or edits outside the agent loop.
- AI-generated application-level strategy artifacts (e.g., school list recommendations as a downloadable report).
- `GET /artifacts` listing endpoint — deferred to v2.
- `AiRunType.AGENT_TURN` cost tracking — deferred to v2.
- Real-time collaborative editing or simultaneous multi-user access to the same draft.
- Streaming intermediate ReAct thought steps (Thought/Observation lines) to the frontend — only the final `finish` response and `artifact` event are streamed to the user.
- Support for artifact types other than `cv_draft` and `essay_draft`.
- Essay guardrail removal — it is narrowed to non-advisor stages only, not removed entirely.

---

## Dependencies (from BA)

| Dependency | Type | Status |
|------------|------|--------|
| `dspy.ReAct` (DSPy 3.1.3) | Internal library | Already installed |
| `search_async` in `vector_store.py` | Internal | Already exists |
| `EssayDraft` ORM model | Internal | Already exists; `source` column to be added |
| `ChatThread.extra` JSONB | Internal | Already exists |
| Bearer-token auth pattern | Internal | Already exists |
| `python-docx` | New Python dependency | Must be added to `requirements.txt` |
| `weasyprint` | New Python dependency | Must be added to `requirements.txt`; may require OS font packages in Docker image |
| `CVDraft` ORM model | New | Must be created |
| `CVDraftRepository` | New | Must be created |
| Alembic migration for `cv_drafts` and `essay_drafts.source` | New | Must be authored |

---

## Output Artifacts

- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅

---

> Human checkpoint: review `02-product-spec.md`, then run `/feature-qa turn_chat_into_an_agent` to continue.
