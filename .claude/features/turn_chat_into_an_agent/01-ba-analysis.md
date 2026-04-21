# BA Analysis: Turn Chat Into an Agent with CV Improvement and Essay Review Tools

## Status
COMPLETE

## Feature Request Summary

Transform the existing advisor chat (currently a simple single-turn DSPy Predict module) into a
ReAct-style agent that can invoke discrete tools to accomplish structured tasks. The two v1 tools
are:

1. **CV Improvement** — the agent retrieves the candidate's RAGed CV content, generates an
   improved version, iterates collaboratively with the candidate, and — when the candidate is
   satisfied — saves the result as an artifact tied to a specific school application.
2. **Essay Review** — the agent retrieves relevant context (CV, life story, profile attributes)
   via RAG and produces grounded, personalized feedback on a candidate-supplied essay draft,
   again iterating until the candidate is satisfied and saving the final version per school.

Both tools are school-aware: the agent proactively asks which school the work is for before
beginning, so tailoring and gap analysis are school-specific. Artifacts are downloadable as Word
or PDF, with the download button rendered inline in the assistant chat bubble (not in the
Documents tab).

---

## Codebase Findings

### Current State of the Pipeline

The existing chat stack works as follows:

- `POST /chat/threads/{id}/messages/stream` in `backend/app/api/routes/chat.py` drives all
  chat turns.
- `generate_assistant_response` in `backend/app/dspy/pipeline.py` routes to one of three
  deterministic DSPy modules depending on state: `IntakeInterviewer`, `ResearchAgent` (a simple
  handover message, misnamed), or `AdvisorModule`.
- The `AdvisorModule` (`backend/app/dspy/school_advisor.py`) is a plain `dspy.Predict` over
  `AdvisorSignature` — one LLM call per turn, no tool use, no iteration.
- The streaming response is plain text (`text/plain`), chunked word-by-word with `asyncio.sleep(0.01)`.
- The frontend (`StreamingChat.tsx`) accumulates chunks and renders them as Markdown. There is
  no concept of structured message types, tool calls, or artifact metadata in the current wire
  format.

### RAG / Document Retrieval (how it currently works)

- `_retrieve_doc_snippets` in `chat.py` runs a pgvector cosine search via `search_async` in
  `backend/app/core/vector_store.py`, scoped to the candidate's `DocumentChunk` rows.
- Embeddings use `text-embedding-3-small` (1536-dim). Chunks are stored per file (after
  document_processing task runs). Default retrieval top_k = 6.
- The retrieved snippets are passed as `docs_snippets` into `generate_assistant_response` but,
  critically, are **not currently forwarded into the AdvisorModule** — they are only used by the
  intake flow. The advisor signature has no `docs_snippets` input field.
- This is the key gap: the advisor has the profile JSON but **no direct access to raw document
  text or semantic search**.

### Existing DSPy Tool-Use Capabilities

- DSPy 3.1.3 is installed. `dspy.ReAct` exists at
  `backend/.venv/lib/python3.14/site-packages/dspy/predict/react.py`.
- `ReAct.__init__` accepts a `Signature` and a `list[Callable]` of tools, builds a looping
  Thought/ToolName/ToolArgs/Observation trajectory internally, and supports both sync `forward`
  and async `aforward`.
- Tools can be plain Python callables or `dspy.Tool` instances. The `finish` pseudo-tool is
  added automatically.
- No existing production code uses `dspy.ReAct`; this will be a first use.

### EssayDraft Model

`backend/app/db/models/essay.py` defines:
- `EssayDraft` — has `candidate_id`, `school_name` (nullable string), `prompt_text`, `title`,
  `body`, `status` (DRAFT / SUBMITTED / ARCHIVED), and `extra` (JSONB). This is exactly the
  right shape for essay artifacts. The `school_name` field covers school association.
- `EssayReview` — child of `EssayDraft`; stores AI/human review `summary`, `scores`, `feedback`.

There is **no equivalent `CVDraft` model**. CV artifacts per school must be built.

### Candidate/Profile Model

`backend/app/db/models/candidate.py`:
- `Candidate` has a `essay_drafts` relationship (via `cascade="all, delete-orphan"`).
- There is no `cv_drafts` relationship yet.
- `CandidateProfile.attributes` (JSONB) stores the selected schools as
  `attributes.selected_schools` — a list of `{school, program_slug, program_display_name}`.

### Streaming Response Format

- Current format: `text/plain; charset=utf-8`, words delimited by spaces, no framing.
- The frontend reads raw bytes and accumulates them as a single string.
- There is no SSE envelope, no JSON event types, no way to signal "this turn contains an
  artifact". Adding structured signals requires a protocol change.

### Files Likely Requiring Changes

**Backend**
- `backend/app/dspy/school_advisor.py` — replace `AdvisorModule` with `AgentAdvisorModule`
  that uses `dspy.ReAct` with the two tool functions
- `backend/app/dspy/pipeline.py` — pass `docs_snippets` into the advisor path; route to the
  new agent module when `thread_stage == "advisor"`
- `backend/app/api/routes/chat.py` — update streaming handler to support a new JSON-lines
  protocol (or SSE) that can carry both text chunks and artifact metadata; add `docs_snippets`
  to advisor routing
- `backend/app/db/models/essay.py` (or new file) — add `CVDraft` model (mirroring
  `EssayDraft`, adding `school_name`)
- `backend/app/db/models/candidate.py` — add `cv_drafts` relationship
- `backend/app/db/models/__init__.py` — export new model
- `backend/app/repositories/` — add `CVDraftRepository` (or extend `EssayDraftRepository`)
- `backend/app/api/routes/` — new or extended route for artifact download (Word / PDF)
- `backend/alembic/versions/` — new migration for `cv_drafts` table and any enum additions
- `backend/requirements.txt` — add `python-docx` for Word generation; consider `reportlab` or
  `weasyprint` for PDF (neither is currently installed)

**Frontend**
- `apps/web/src/components/StreamingChat.tsx` — extend to parse the new structured protocol
  and render an inline download button when an artifact is present in the message
- `apps/web/src/lib/api.ts` — add types and helpers for artifact download endpoints,
  CV draft CRUD
- `apps/web/src/app/advisor/page.tsx` — add quick-action chips for "Improve my CV" and
  "Review my essay"

---

### Existing Capabilities Relevant to This Feature

- pgvector semantic search (`search_async` in `vector_store.py`) — ready to serve as the RAG
  retrieval backend for both tools
- `EssayDraft` / `EssayReview` ORM models — essay artifact storage pattern is fully defined
- `ChatThread.extra` JSONB — already carries `stage`, `selected_schools`; can carry agent
  state (active tool, current artifact draft, school context)
- `dspy.ReAct` in the installed DSPy 3.1.3 — supports both sync and async tool-calling loops
- `run_dspy_module` wrapper in `dspy_runtime.py` — handles configure-on-first-call, OTel
  tracing, and logging
- `UploadedFile` / `DocumentChunk` — document bytes and chunked embeddings are already stored
  and queryable per candidate
- Bearer-token auth + candidate ownership checks — all existing patterns in `auth.py` and
  route dependencies apply unchanged
- `EssayStatus` enum and `AiRunType` enum in `db/enums.py` — extend for CV draft status

### New Capabilities Required

1. **`CVDraft` ORM model and migration** — mirrors `EssayDraft`; fields: `candidate_id`,
   `school_name`, `title`, `body`, `version` (int, default 1), `status`, `extra` (JSONB for
   agent metadata: which tool session produced it, iteration count)

2. **Agent-aware advisor DSPy module** — a `dspy.ReAct` module wrapping two async-capable tool
   functions:
   - `retrieve_candidate_context(query: str) -> str` — calls pgvector search and formats
     top-K chunks as a grounded context block
   - `save_artifact(artifact_type: str, title: str, body: str, school_name: str) -> str` —
     persists either an `EssayDraft` or `CVDraft` to the database and returns a stable
     `artifact_id` + download URL

3. **School-selection prompt within the agent** — before invoking the CV or essay tool,
   the agent must ask which school the work is for. This is best handled in the agent's
   system/signature instructions, not as a separate route.

4. **Structured streaming protocol** — upgrade the wire format from plain text to JSON-lines
   (newline-delimited JSON) or SSE with typed events:
   - `{"type": "text_chunk", "value": "..."}` — regular streamed text
   - `{"type": "artifact", "artifact_id": "...", "artifact_type": "cv_draft"|"essay_draft",
     "title": "...", "school_name": "...", "download_url": "..."}` — terminal event that
     triggers the inline download button

5. **Artifact download endpoint** — `GET /artifacts/{artifact_id}/download?format=docx|pdf`
   generates and streams a Word (`.docx`) or PDF file. Requires adding `python-docx` (Word)
   and a PDF library (e.g. `reportlab` or `weasyprint`) to `requirements.txt`.

6. **Frontend artifact renderer** — `StreamingChat.tsx` must parse the JSON-lines protocol and
   render a download button at the bottom of the assistant bubble when an `artifact` event is
   received.

---

## Dependencies

**Internal**
- `backend/app/core/vector_store.search_async` — RAG retrieval tool backend
- `backend/app/db/models/essay.py` `EssayDraft` — essay artifact persistence (already exists)
- `backend/app/repositories/` — data access for new `CVDraft`
- `backend/app/core/job_runner.py` — may be used if artifact generation becomes heavy enough
  to warrant a background job (likely not needed in v1)
- `dspy.ReAct` (DSPy 3.1.3) — agent loop

**External / New Library Dependencies**
- `python-docx` — Word document generation (not currently in `requirements.txt`)
- A PDF generation library — `reportlab` (pure Python, lightweight) is the safest choice;
  `weasyprint` is better quality but has system dependencies
- `openai` (already present) — embedding generation for RAG retrieval inside tool
- `pgvector` / `asyncpg` (already present) — vector search

---

## Risks & Constraints

1. **ReAct loop latency and streaming incompatibility** — `dspy.ReAct.forward` is synchronous
   and runs multiple LLM calls sequentially until `finish`. The current streaming handler calls
   `generate_assistant_response` in the main async event loop (via `asyncio.to_thread` for the
   blocking call). A multi-turn ReAct loop will take several seconds per agent turn, making the
   current word-by-word streaming look frozen. Mitigation: use `dspy.ReAct.aforward` (the async
   variant) and stream intermediate "thinking" status events to keep the UI alive, or run the
   full agent call in a thread pool and emit progress pings.

2. **Tool functions need database sessions** — `retrieve_candidate_context` must call
   `search_async` which needs an `AsyncSession`. DSPy tools are plain callables and have no
   access to the request context. Mitigation: capture the session and `candidate_id` in a
   closure at request time and pass the pre-bound function to `ReAct`. This works but is not
   testable without a real session; the mock path will need careful construction.

3. **Streaming protocol change is a breaking frontend change** — switching from `text/plain`
   to JSON-lines means the existing `StreamingChat.tsx` must be updated at the same time as the
   backend. The intake and (old) advisor threads still use the plain text format. Best approach:
   make the new protocol opt-in per thread stage (the response header or a thread-level flag
   can signal which format to use), or version the endpoint.

4. **`dspy.ReAct` is synchronous by default; the async variant (`aforward`) exists but is less
   battle-tested in DSPy 3.1.3** — check that `aforward` properly handles the `finish` tool and
   trajectory truncation before committing to async.

5. **No `python-docx` or PDF library installed** — must be added to `requirements.txt` and
   the Docker image before the download endpoint can ship. PDF generation in particular may
   require OS-level font packages in the container.

6. **Artifact ownership and access control** — `CVDraft` and `EssayDraft` records must be
   strictly scoped to the owning candidate. The download endpoint must verify ownership before
   returning bytes, using the same `get_candidate_id_from_bearer_token` pattern.

7. **Guardrail conflict** — `pipeline.py` contains a hard guardrail that blocks "write my
   essay" phrases. The agent's CV/essay tool must not collide with this guardrail. Since the
   guardrail fires before routing to the advisor, it will intercept legitimate agent invocations
   for "improve my essay". The guardrail must be narrowed to apply only to the intake/research
   stages, not the advisor/agent stage.

8. **EssayDraft model reuse vs. new artifact model** — `EssayDraft` already has `school_name`
   and `body`, making it usable for essay artifacts without schema changes. However, repurposing
   it for agent-generated essays alongside the eventual human-written essays in the same table
   may create confusion. A discriminator column (`source: "agent" | "human"`) or a separate
   `AgentArtifact` model should be considered. For CV drafts there is no existing model at all.

9. **Context window size for ReAct trajectory** — each RAG retrieval adds ~1-2K tokens of
   observation to the trajectory. With a default `max_iters=20` and 6 RAG chunks per call, the
   context can grow to 50K+ tokens. `dspy.ReAct` has built-in truncation but it discards early
   steps, which may cause the agent to lose the school context it established. Set `max_iters=8`
   for v1 and monitor.

10. **Mock mode for testing** — `dspy.ReAct` uses `dspy.Predict` internally, which requires a
    configured LM. The mock path must either stub `ReAct` entirely or implement a parallel
    `MockAgentAdvisorModule` (as the codebase does for every other module). This is non-trivial
    for an iterative agent and will require dedicated engineering effort.

---

## User Stories

1. As a candidate in the advisor stage, I can say "help me improve my CV" and the agent will
   ask which school I'm preparing for, then retrieve my CV from its documents, generate an
   improved version, and show it to me inline.
2. As a candidate, I can iterate on a CV draft by telling the agent what to change, and it will
   revise and show me the updated version in the same conversation.
3. As a candidate, when I'm happy with a CV draft, I can tell the agent to save it, and it will
   confirm the school and save the artifact.
4. As a candidate, I can download a saved CV draft or essay draft as a Word or PDF file directly
   from the chat bubble.
5. As a candidate, I can say "review my essay for Wharton" (pasting the essay text), and the
   agent will retrieve my profile context and give me structured, personalized feedback.
6. As a candidate, the agent proactively asks which school I'm targeting before starting CV or
   essay work.

---

## Functional Requirements

1. The advisor chat agent in the `advisor` thread stage MUST route to an agent module capable of
   calling `retrieve_candidate_context` and `save_artifact` tools.
2. `retrieve_candidate_context` MUST perform a pgvector semantic search over all of the
   candidate's `DocumentChunk` rows (top_k=8 for agent use, to give richer context).
3. Before starting CV improvement or essay review work, the agent MUST ask which school the work
   is for unless the school is already unambiguous from context.
4. `save_artifact` MUST persist CV content to a `cv_drafts` table and essay content to
   `essay_drafts`, both scoped to the candidate and the specified school.
5. When an artifact is saved, the streaming response MUST emit a terminal `artifact` event
   containing `artifact_id`, `artifact_type`, `title`, `school_name`, and a signed download URL.
6. The download URL MUST support both `?format=docx` and `?format=pdf`.
7. The inline download button MUST appear within the assistant chat bubble that triggered the
   save, not in a separate tab.
8. The "write my essay" guardrail MUST NOT fire for the advisor/agent thread stage.
9. Mock mode MUST remain functional — a `MockAgentAdvisorModule` MUST provide deterministic
   output without LLM calls.

---

## Data Model Changes Needed

### New: `cv_drafts` table

```
cv_drafts
  id              UUID PK
  candidate_id    UUID FK → candidates.id ON DELETE CASCADE
  school_name     VARCHAR(255) NULLABLE
  title           VARCHAR(512) NOT NULL
  body            TEXT NOT NULL
  version         INTEGER NOT NULL DEFAULT 1
  status          ENUM(draft, submitted, archived) NOT NULL DEFAULT draft
  extra           JSONB NULLABLE   -- agent session id, iteration count, tool trajectory summary
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT now()
  updated_at      TIMESTAMP WITH TIME ZONE DEFAULT now()
```

Indexes: `ix_cv_drafts_candidate_id`

### Existing: `essay_drafts` — no schema change needed for v1

`school_name` is already nullable VARCHAR. The `extra` JSONB can carry agent metadata.

### New: enum value addition (optional)

Consider adding `AiRunType.AGENT_TURN` to track per-turn costs, but this can be deferred.

### `Candidate` model change

Add `cv_drafts: Mapped[list["CVDraft"]]` relationship with `cascade="all, delete-orphan"`.

---

## API Changes Needed

### Modified: `POST /chat/threads/{id}/messages/stream`

- Response content-type changes from `text/plain` to `text/event-stream` (SSE) or
  `application/x-ndjson` for threads in the `advisor` stage.
- Event types:
  - `text_chunk`: `{"type": "text_chunk", "value": "<partial text>"}`
  - `artifact`: `{"type": "artifact", "artifact_id": "...", "artifact_type": "cv_draft"|"essay_draft", "title": "...", "school_name": "...", "download_url": "/artifacts/{id}/download"}`
  - `error`: `{"type": "error", "message": "..."}`
- Backward compatibility: intake/research threads continue to use `text/plain`.

### New: `GET /artifacts/{artifact_id}/download`

- Query param: `format=docx|pdf` (default `docx`)
- Auth: Bearer token, candidate ownership check
- Response: streaming binary file with `Content-Disposition: attachment`
- Requires `python-docx` for Word; PDF library TBD

### New: `GET /artifacts` (optional, v1 can skip)

- Lists the candidate's saved CV drafts and essay drafts
- Useful for future "saved artifacts" tab

---

## Agent Architecture

### Recommended: `dspy.ReAct` with Async Tools

```python
class AgentAdvisorModule(dspy.Module):
    def __init__(self, retrieve_fn, save_artifact_fn):
        self.react = dspy.ReAct(
            AgentAdvisorSignature,
            tools=[retrieve_fn, save_artifact_fn],
            max_iters=8,
        )

    def forward(self, **kwargs):
        return self.react(**kwargs)

    async def aforward(self, **kwargs):
        return await self.react.aforward(**kwargs)
```

The signature carries:
- Inputs: `profile_attributes_json`, `selected_schools_json`, `conversation_history`,
  `user_message`, `candidate_id` (for tool closure binding — not an LLM input, used for setup)
- Output: `response`

Tool functions are closures created at request time, capturing `session` and `candidate_id`:

```python
async def retrieve_candidate_context(query: str) -> str:
    # Embed query, call search_async, format chunks
    ...

async def save_artifact(artifact_type: str, title: str, body: str, school_name: str) -> str:
    # Persist CVDraft or EssayDraft, return artifact_id + download_url
    ...
```

### Mock Path

`MockAgentAdvisorModule` — detects "cv" or "essay" keywords in `user_message`, returns a
hardcoded draft body, and emits a fake `artifact_id`. Must not call any DB or embedding
functions.

---

## RAG Integration Approach

Current `_retrieve_doc_snippets` in `chat.py` is called once per request and passed to the
pipeline. For the agent, retrieval must happen inside the tool loop — the agent decides when and
what to retrieve, not the route handler.

The `retrieve_candidate_context` tool will:
1. Call `client.embeddings.create(model="text-embedding-3-small", input=query)` using the
   per-request `AsyncOpenAI` client.
2. Call `search_async(session, candidate_id=candidate_id, query_embedding=embedding, top_k=8)`.
3. Format the returned chunks as a numbered context block for the LLM's observation.

Because `dspy.ReAct.aforward` is async and tools can be async callables, the embedding call
can be awaited without blocking.

---

## Download Artifact Generation

### Word (`.docx`)
- `python-docx` library — add to `requirements.txt`
- Simple: create a `Document`, add a heading (title), add paragraphs (body split by `\n\n`)
- Serve via `StreamingResponse` with `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

### PDF
- Recommend `reportlab` (`pip install reportlab`) — no system font dependencies in Alpine/Debian
- Alternative: `weasyprint` for HTML-to-PDF (better formatting, but heavier)
- For v1, Word is sufficient; PDF can be implemented in v1.1

---

## UI/UX Considerations

### Inline Download Button in Chat Bubble

When the frontend receives an `artifact` SSE/NDJSON event:
1. The current streaming assistant bubble stops accumulating text.
2. A download card is appended below the final text content of the bubble:
   ```
   [ CV Draft saved: "Wharton MBA — Revised CV" ]
   [ Download as Word ]  [ Download as PDF ]
   ```
3. The download button calls `GET /artifacts/{artifact_id}/download?format=docx|pdf` with
   the Bearer token and triggers a browser file download.
4. The download card is persisted with the message — on page reload, the message history
   API should include `artifact_id` in the message `extra` field so the button can be
   reconstructed.

### Quick-Action Chips (Advisor Page)

Add two chips to the existing array in `/advisor/page.tsx`:
- "Improve my CV"
- "Review my essay"

These prefill the input with a short prompt that the agent can act on immediately.

### `StreamingChat.tsx` Protocol Change

- On first chunk for a given turn, detect `text/event-stream` or check the `Content-Type`
  header; if it is the new structured format, parse events from the stream.
- `text_chunk` events update `streamingText` as today.
- `artifact` events trigger rendering of the download card.
- Keep backward compatibility for `text/plain` (intake/research threads).

---

## Open Questions / Risks Summary

| # | Question / Risk | Severity | Recommended Resolution |
|---|----------------|----------|------------------------|
| 1 | `aforward` stability in DSPy 3.1.3 for multi-tool async loops | High | Prototype the async path in isolation before integrating; fall back to `asyncio.to_thread` wrapping sync `forward` if unstable |
| 2 | Tool functions require DB session — hard to inject into DSPy | High | Use closure capture at request time; document the pattern for mock mode |
| 3 | Protocol change breaks existing `StreamingChat.tsx` | Medium | Thread-stage-gated: use new protocol only when `thread.extra.stage == "advisor"` |
| 4 | Essay guardrail in `pipeline.py` blocks agent requests | Medium | Gate the guardrail on `thread_stage not in ("advisor",)` |
| 5 | No PDF library in requirements.txt | Medium | Add `reportlab`; test in Docker before shipping |
| 6 | Context window growth with RAG observations | Medium | Cap `max_iters=8`; implement trajectory summary logging |
| 7 | Mock mode for ReAct agent | Medium | Implement `MockAgentAdvisorModule` that returns fixed artifacts |
| 8 | `EssayDraft` reuse vs. separate agent artifact model | Low | Add `source` discriminator column to `essay_drafts` in the same migration |
| 9 | Artifact message persistence (download button on reload) | Low | Store `artifact_id` in `ChatMessage.extra` when saving artifact |

---

## Recommended Next Step

Hand off to Product Manager with this analysis for spec writing.

## Output Artifacts
- `01-ba-analysis.md` ✅
