# AI job framework (Task 003)

Celery runs long / flaky work (LLM calls, DSPy, etc.) off the FastAPI request path. This repo wires:

- **`AiJobTask`** — base task with retries (`ConnectionError`, `TimeoutError`, `OSError`), exponential backoff + jitter, structured logs (`correlation_id`, Celery task id), and best-effort `ai_run` → `FAILED` on final failure.
- **Typed payloads** — Pydantic models in `app/workers/payloads.py`; tasks call `Model.model_validate(payload)` on the dict Celery JSON-serializes.
- **`ai_runs` row** — API creates a `QUEUED` row, enqueues work with `ai_run_id` in the payload; the worker updates status through the lifecycle.
- **Sync DB in workers** — `app/core/sync_db.py` + `app/workers/ai_run_sync.py` (psycopg) so tasks avoid `asyncio.run()` per query.

## Sample flow

1. `POST /jobs/sample-sleep` → insert `ai_runs` (`QUEUED`) → `sample_sleep_ai_job.delay({...})`.
2. Worker stamps `request._meta.celery_task_id`, sets `RUNNING`, sleeps, sets `SUCCEEDED` (or `FAILED` on terminal error).
3. Client polls `GET /jobs/ai-runs/{id}` or `GET /jobs/celery/{task_id}`.

## Idempotency & safe retries

- **Celery retries** only fire for `autoretry_for` exceptions until `max_retries` is exhausted. `on_failure` runs on **final** failure and marks `ai_runs.failed` when `ai_run_id` is in the payload.
- **Business idempotency** must be explicit: the sample task skips work if the row is already `SUCCEEDED` (safe replays / duplicate delivery).
- **Retries after partial side effects** (e.g. billed LLM call) are unsafe unless the downstream call is **idempotent** (provider idempotency key, or “check output already stored” before re-calling). Prefer:
  - persist a **step checkpoint** in `ai_run.request` / `response`, or
  - use an **external idempotency key** stored on the row before calling the provider.
- **Exactly-once** is not guaranteed; design for **at-least-once** execution and dedupe on read paths where needed.

## Future tasks (profile extraction, strategy, essay review)

1. Add a Pydantic payload model next to `SampleSleepJobPayload`.
2. Add `@shared_task(bind=True, base=AiJobTask, name="app.jobs.<name>")` in `app/workers/tasks/`.
3. Import the module at the bottom of `app/core/celery_app.py` (after `celery_app` is created) so `@celery_app.task` registers on the correct app.
4. API route: create `ai_run` (`run_type` enum), enqueue dict payload with `ai_run_id` as string (UUID JSON-safe).

## DB access

- **API:** async SQLAlchemy (`get_db_session`, `AiRunRepository`).
- **Worker:** `sync_session_scope()` only; do not share async engines across threads.
