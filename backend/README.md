# Backend (FastAPI)

## Task 002 — persistence

- **Models:** `app/db/models/` (candidates, profiles, chats, files, strategy, tasks, essays, AI runs, audit).
- **Repositories:** `app/repositories/` (`CandidateRepository`, `ChatRepository`).
- **Migrations:** Alembic in `alembic/versions/` — create new revisions with `alembic revision --autogenerate` only.

### Test with Docker Compose (migrations on boot)

From the **repository root**:

```bash
docker compose up --build web
```

- **`web`** waits until **Postgres is healthy**, then the entrypoint runs **`alembic upgrade head`**, then starts **uvicorn** on [http://localhost:8000](http://localhost:8000).
- **`worker`** does not run migrations (only the web role does).

Full stack (API + worker + Redis + Postgres):

```bash
docker compose up --build
```

Optional seed (host Python, DB reachable on `localhost:5432`):

```bash
cd backend && export PYTHONPATH=. DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions
python scripts/seed_task002_demo.py
```

### Commands without Docker (from `backend/`)

```bash
export PYTHONPATH=.
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions

alembic upgrade head
pytest -q
python scripts/seed_task002_demo.py
```

Use `docker compose up -d postgres` from the repo root if you only need Postgres on `localhost:5432`.

## Task 003 — Celery AI job framework

- **Base task:** `app/workers/base_task.py` (`AiJobTask` — retries, logging, `on_failure` → `ai_run` FAILED).
- **Payloads:** `app/workers/payloads.py` (Pydantic; add one model per job type).
- **Worker DB:** `app/core/sync_db.py`, `app/workers/ai_run_sync.py`.
- **Sample job:** `POST /jobs/sample-sleep` → `GET /jobs/ai-runs/{id}` (see **[`docs/AI_JOB_FRAMEWORK.md`](docs/AI_JOB_FRAMEWORK.md)**).

### Fake login (candidates)

- **`POST /candidates/enter`** — JSON `{ "email": "…", "full_name": "…" (optional) }`. Case-insensitive email match; creates a candidate with a derived display name if new. Returns `{ created, candidate, session_token }` including `profile` when present.

Use the returned token for subsequent endpoints:
- `Authorization: Bearer <session_token>`

This is still a **scaffold** (fake auth); lock down or replace before production.

See **[`RAILWAY_DEPLOYMENT.md`](RAILWAY_DEPLOYMENT.md)** for production deploy notes.

## Candidate chat + file intake (initial scaffold)

- **Upload docs (bytes stored in Railway Storage bucket when configured):**
  - `POST /files/upload` (multipart, field name: `files`)
  - `GET /files` (lists uploaded files for the candidate)
  - `GET /files/{file_id}/download` (streams raw bytes)
- **Chat:**
  - `POST /chat/threads` (creates a thread + initial assistant intake message)
  - `GET /chat/threads/{thread_id}/messages` (message history)
  - `POST /chat/threads/{thread_id}/messages/stream` (streams assistant output as `text/plain`)

All `/files/*` and `/chat/*` endpoints require:
- `Authorization: Bearer <session_token>`

DSPy plumbing currently powers the assistant text decisions in a deterministic MVP mode; later we’ll wire real LLM calls + streaming tokens.

### Using OpenAI for DSPy (optional)

To enable real LLM calls for the assistant:
- Set `DSPY_MODE=openai`
- Set `OPENAI_API_KEY` in your runtime environment (Docker compose: in your shell before `make up`, e.g. `export OPENAI_API_KEY=...`)
- Optional: set `DSPY_MODEL` (defaults to `openai/gpt-4o-mini`)

## DSPy Evaluation & Optimisation

The `evals/` directory contains a complete evaluation framework for all four LLM-backed DSPy modules: `answer_relevance`, `document_classifier`, `intent_classifier`, and `intake_interviewer`.

### Prerequisites

Run from `backend/` with the venv active:

```bash
cd backend
source .venv/bin/activate
export PYTHONPATH=.
export OPENAI_API_KEY=...   # required for real LLM calls
```

### Evaluate a module (score it against the labelled devset)

```bash
# Use the production module with its current signature
python -m evals.run_evals --module answer_relevance --mode openai

# Use a specific named signature variant (field structure only — instruction optimised separately)
python -m evals.run_evals --module answer_relevance --signature v2_cot_literal --mode openai

# Evaluate all modules in one pass
python -m evals.run_evals --module all --mode openai
```

### Compare signature field-structure variants

Runs every variant in `evals/signatures/<module>.py` and prints a ranked table:

```bash
python -m evals.run_evals --module document_classifier --compare-signatures --mode openai
```

Output:

```
document_classifier signature comparison (devset n=16)
------------------------------------------------------
v2_cot_literal       0.88   <- best
v1_baseline          0.75
v3_no_reasoning      0.70
```

### Optimise a module (MIPROv2 — auto-proposes instructions + few-shot demos)

MIPROv2 proposes candidate instruction variants for each predictor, bootstraps few-shot demonstrations from the trainset, then uses Bayesian search to find the best combination. The winning instructions and demonstrations are saved in the compiled JSON.

```bash
python -m evals.run_evals --module document_classifier --signature v2_cot_literal \
    --optimize --optimizer mipro \
    --save-path evals/compiled/doc_v2_mipro.json \
    --mode openai
```

After compilation the CLI evaluates the compiled program and prints the before/after scores. The compiled JSON is human-readable — inspect the `instructions` field to see what MIPROv2 produced, and promote it back into the signature docstring as the new baseline.

### Cheaper optimisers (few-shot demos only, no instruction search)

```bash
# Bootstrap demos, random subset search — best cost/quality tradeoff
python -m evals.run_evals --module answer_relevance \
    --optimize --optimizer bootstrap_random_search \
    --save-path evals/compiled/ar_bootstrap.json \
    --mode openai

# Hard-code k trainset examples as demos — zero LM calls during compile
python -m evals.run_evals --module intent_classifier \
    --optimize --optimizer labeled_few_shot \
    --save-path evals/compiled/ic_labeled.json \
    --mode openai
```

### Load and re-evaluate a compiled program

```bash
python -m evals.run_evals --module document_classifier \
    --loaded-program evals/compiled/doc_v2_mipro.json \
    --mode openai
```

### Full workflow

```
1. --compare-signatures           → find the best field structure
2. --optimize --optimizer mipro   → auto-generate instructions + few-shot demos
3. Inspect compiled JSON          → optionally promote instructions back into the signature
4. --loaded-program               → re-evaluate the compiled program
5. module.load("path.json")       → load into production
```

### Optimizer reference

| Flag | LM calls during compile | What it optimises |
|---|---|---|
| `labeled_few_shot` | 0 | Selects k trainset examples as hard-coded demos |
| `bootstrap` | low | Generates demos from passing execution traces |
| `bootstrap_random_search` | medium | Like bootstrap, picks best random demo subset |
| `mipro` | high | Instructions + demos jointly via Bayesian search |

### Adding examples to a dataset

Edit the relevant file in `evals/datasets/`. Each example is a plain `dspy.Example` object — add entries to the `EXAMPLES` list and the changes take effect immediately on the next run.

### Adding a signature variant

Add a new class to the relevant file in `evals/signatures/` and register it in that file's `REGISTRY` dict. The name becomes the `--signature` argument value.

## Phoenix Cloud Traces (optional)

If you want traces in Phoenix Cloud, set these on **both** `web` and `worker`:
- `PHOENIX_COLLECTOR_ENDPOINT` (HTTP collector endpoint, must end with `/v1/traces`)
- `PHOENIX_API_KEY` (optional, if your collector requires auth)
- `PHOENIX_PROJECT_NAME` (optional; defaults to `mba_admissions`)

The backend will emit a `startup.phoenix.tracing` span on startup so you can confirm traces are flowing.

To get LLM/chain observability in Phoenix, ensure real LLM calls are enabled (set `DSPY_MODE=openai` and `OPENAI_API_KEY`), then hit the chat endpoint at least once (e.g. `POST /chat/threads/{thread_id}/messages/stream`).
