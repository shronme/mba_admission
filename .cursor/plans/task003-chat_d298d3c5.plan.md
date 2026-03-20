---
name: task003-chat
overview: Build an initial high-end chat-based web UI with fake login, document intake + sidebar, and a DSPy-powered admissions chat backend with guardrails and streaming responses.
todos:
  - id: fe-chat-ui
    content: "Build FE: session-aware dashboard with high-end layout, sidebar docs, and streaming chat UI (SSE via fetch)."
    status: completed
  - id: be-auth-sessions
    content: "Add backend fake session-token auth: new `candidate_sessions` model + update `/candidates/enter` to return token; add auth dependency."
    status: completed
  - id: be-storage-proxy
    content: Implement backend-proxy document upload/download and listing using Railway Storage Buckets; persist metadata in `uploaded_files`.
    status: completed
  - id: be-chat-routes
    content: "Implement chat endpoints: create thread, list messages, and stream assistant output while persisting chat messages."
    status: completed
  - id: be-dspy-runtime
    content: "Implement DSPy runtime (Task 004): env-driven provider/model config, centralized `dspy.configure`, one runnable module."
    status: completed
  - id: be-dspy-pipeline
    content: Implement DSPy pipeline modules (intent classification + response generation) with guardrails and memory/context injection.
    status: completed
  - id: db-migration-and-tests
    content: Create Alembic migration for `candidate_sessions`, add minimal unit tests for auth ownership and streaming smoke tests; update docs.
    status: completed
isProject: false
---

## Scope

Implement a minimal but end-to-end “candidate experience”:

- Email fake-login → candidate session → candidate details + sidebar
- Candidate uploads documents → raw bytes stored in a Railway bucket → metadata stored in Postgres
- Chat UI: initial intake asks for relevant documents; then asks about Grad school goals at a top US university
- Chat pipeline uses DSPy: Intent Classification → Routing/Tool Selection → Response Generation → Memory/Context Injection → Final Answer
- Guardrails restrict content to admissions/help topics
- LLM output is streamed to the FE

## Key data model

- Reuse existing tables:
  - `chat_threads`, `chat_messages`
  - `uploaded_files`
  - `candidates`, `candidate_profiles`
- Add minimal new table for “server-session-token” fake auth (to satisfy per-candidate isolation): `candidate_sessions` (token → candidate_id)

## Backend tasks

1. Auth/session wiring (fake)
  - Add `candidate_sessions` model + Alembic migration.
  - Update `POST /candidates/enter` to return a `session_token`.
  - Add auth dependency for all subsequent endpoints:
    - read `Authorization: Bearer <token>` (or `X-Session-Token`)
    - map to `candidate_id`
2. Bucket storage (backend-proxy upload/download)
  - Add S3-compatible storage adapter under `backend/app/core/storage.py` using Railway Storage Buckets credentials.
  - Add API routes:
    - `POST /files/upload` (multipart): upload bytes to bucket under a deterministic key (candidate_id + file_id + original filename)
    - `GET /files` list uploaded files for candidate
    - `GET /files/{file_id}/download` streams raw object bytes back (proxy)
  - Persist metadata in `uploaded_files` (original_filename, content_type, byte_size, storage_uri/key, status).
3. Chat endpoints + persistence
  - Add routes:
    - `POST /chat/threads` (create thread; insert initial assistant “intake: upload docs” message)
    - `GET /chat/threads/{thread_id}/messages` (sidebar can show history if needed)
    - `POST /chat/threads/{thread_id}/messages/stream` to accept user message and stream assistant output
  - Persist:
    - user messages immediately
    - assistant messages after streaming completes (or create empty then update)
4. DSPy runtime (Task 004)
  - Add `backend/app/core/dspy_runtime.py`:
    - env-driven provider/model config
    - centralized `dspy.configure(lm=...)`
    - one minimal sample module (can be adapted into classifier + responder)
5. DSPy modules: classification + response (Task 005)
  - Create strict Pydantic contracts/enums for:
    - top intents (intake_docs, goals, admissions_help, off_topic)
    - secondary flags, confidence, reasoning, recommended_agent, requires_clarification
  - Implement DSPy:
    - Intent Classification module
    - Response Generation module that takes:
      - user message
      - stage/state derived from (a) uploaded files count and (b) whether candidate goals exist
      - candidate profile + memory snippets
      - classification/tool-selection
      - produces final assistant response
6. Memory / context injection
  - For each turn, assemble context:
    - candidate profile and `candidate_profile.attributes`
    - extracted text snippets from uploaded documents (MVP: decode text/*, pdf via `pypdf` or similar)
    - recent chat history
  - Token/length caps (truncate excerpts, limit number of documents and messages).
7. Guardrails
  - If intent classifier returns `off_topic` or low confidence with requires_clarification:
    - refuse/redirect to admissions scope
  - Maintain a short “allowed topics” list.
8. Streaming
  - Implement streaming SSE/streaming-response from the backend.
  - Use DSPy streaming utilities (StreamListener + streamify) and forward token chunks to FE.

## Frontend tasks

1. Update fake login to store `session_token` and use it in all API requests.
  - Modify `SessionContext.tsx` + `enterWithEmail` flow.
2. Professional high-end layout
  - Replace current diagnostics-only dashboard with:
    - left sidebar: candidate info + uploaded files list (download links)
    - main: chat transcript + streaming assistant responses
    - top bar: candidate name + sign out
3. Chat UI with streaming
  - Create `src/features/chat/ChatView`:
    - message list
    - input box
    - optional file upload CTA (to support intake)
    - “send” triggers POST to `.../messages/stream` and renders streamed tokens live.
4. Sidebar for candidate info
  - Create `SidebarDocuments`:
    - list uploaded documents metadata from `GET /files`
    - download via `GET /files/{id}/download`
5. Route wiring
  - Update `CandidateDashboard` to render the chat + sidebar.

## Testing & acceptance

- Backend unit tests:
  - session auth dependency
  - candidate/file ownership enforcement
  - intent classification schema validation
- Integration smoke tests:
  - create thread → upload doc → send chat message → ensure SSE stream returns final response and DB rows created.
- Local dev checklist:
  - run docker compose (web + worker if needed)
  - apply migrations (Task 002 already provides schema; new session + file/chat rules require a new migration)

## Manual Railway setup (one-time checklist)

- Add managed services to the Railway project: **Postgres** and **Redis**.
- Create a **Railway Storage Bucket** (private, S3-compatible) for file bytes.
- Copy the bucket’s **Credentials** (bucket name + S3-compatible endpoint/region + access key id + secret access key) and set them as environment variables on the **API (web) service**; redeploy the API.
- If the backend reads documents from the bucket in background workers (or if we offload extraction/chat generation to Celery), also set the same bucket credentials on the **worker service**; otherwise only web needs them.
- Ensure DB schema is migrated on the API web process startup: either keep the web entrypoint running `alembic upgrade head`, or add a one-off command `cd /app/backend && alembic upgrade head` after deploy.
- Configure CORS on the **API (web) service**: set `CORS_ORIGINS` to include the **frontend** origin exactly (scheme + host, no path); redeploy the API.
- Configure the **frontend service**: set `NEXT_PUBLIC_API_URL` to the **FastAPI** public URL (the one where `/health` returns `{"status":"ok"}`); redeploy the frontend after changing it.
- Assign a public domain to the **frontend** service.
- The **API web** service must also be reachable publicly by the frontend.
- Do not expose the **worker** service publicly.

## Files to change/create (high-level)

Backend:

- `backend/app/api/routes/candidates_enter.py`
- `backend/app/api/routes/files_*.py` (new)
- `backend/app/api/routes/chat_*.py` (new)
- `backend/app/core/storage.py` (new)
- `backend/app/core/dspy_runtime.py` (new)
- `backend/app/dspy/` (new modules + contracts)
- `backend/app/db/models/`* + `backend/alembic/` migration for `candidate_sessions`

Frontend:

- `apps/web/src/context/SessionContext.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/components/CandidateDashboard.tsx`
- `apps/web/src/features/chat/`* (new chat UI + sidebar)

