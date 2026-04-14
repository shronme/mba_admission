# AI job framework (Task 003)

This repo runs long / flaky work (LLM calls, DSPy, etc.) off the FastAPI request path using an **in-process job runner**:

- **Runner** — `app/core/job_runner.py` (bounded queue + worker pool).
- **Typed payloads** — Pydantic models in `app/workers/payloads.py`; jobs validate with `Model.model_validate(payload)`.
- **`ai_runs` row** — API creates a `QUEUED` row, enqueues work with `ai_run_id` in the payload; the runner updates status through the lifecycle.
- **Sync DB helpers** — `app/core/sync_db.py` + `app/workers/ai_run_sync.py` (psycopg) for job code paths that use synchronous SQLAlchemy.

## Sample flow

1. `POST /jobs/sample-sleep` → insert `ai_runs` (`QUEUED`) → enqueue in-process job.
2. Runner sets `RUNNING`, sleeps, sets `SUCCEEDED` (or `FAILED` on error).
3. Client polls `GET /jobs/ai-runs/{id}`.

## Idempotency & safe retries

- In-process execution does **not** automatically retry by default. If you add retries, ensure you do not duplicate billable side effects.
- **Business idempotency** must be explicit: the sample task skips work if the row is already `SUCCEEDED` (safe replays / duplicate delivery).
- **Retries after partial side effects** (e.g. billed LLM call) are unsafe unless the downstream call is **idempotent** (provider idempotency key, or “check output already stored” before re-calling). Prefer:
  - persist a **step checkpoint** in `ai_run.request` / `response`, or
  - use an **external idempotency key** stored on the row before calling the provider.
- **Exactly-once** is not guaranteed; design for **at-least-once** execution and dedupe on read paths where needed.

## Future tasks (profile extraction, strategy, essay review)

1. Add a Pydantic payload model next to `SampleSleepJobPayload`.
2. Add a job function in `app/workers/tasks/`.
3. Add a `JobType` + dispatch mapping in `app/core/job_runner.py`.
4. API route: create `ai_run` (`run_type` enum), enqueue dict payload with `ai_run_id` as string (UUID JSON-safe).

## DB access

- **API:** async SQLAlchemy (`get_db_session`, `AiRunRepository`).
- **Jobs:** prefer `sync_session_scope()` for job code paths that use sync helpers.
