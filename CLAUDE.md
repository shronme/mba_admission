# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Full stack (recommended)
```bash
make up          # docker-compose (Postgres + FastAPI :8000) + Next.js dev :3000
make down        # tear down containers
make logs        # tail backend logs
```

### Frontend only (requires API running)
```bash
make fe          # Next.js dev server on :3000
make lint-fe     # ESLint
make build-fe    # production build
```

### Backend only
```bash
# From backend/
export PYTHONPATH=.
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions
alembic upgrade head   # run migrations
pytest -q              # run all tests
pytest tests/test_foo.py -k test_name  # single test
```

### Notes (PDF generation)

- `weasyprint` requires OS-level font/rendering deps in the backend image (e.g. `fonts-liberation`/`fonts-noto` + `libpango`). If PDF generation fails in Docker/CI, verify those packages are installed in `backend/Dockerfile`.

## Architecture

This is a full-stack MBA admissions platform. Backend in `backend/`, frontend in `apps/web/`.

### Backend (FastAPI + DSPy)

- **`app/api/routes/`** — FastAPI endpoint handlers. Auth is email-only (no password); session tokens are stored in localStorage on the frontend.
- **`app/dspy/`** — All LLM logic lives here as DSPy modules. The pipeline (`pipeline.py`) orchestrates intake, profile extraction, document classification, program research, and admission evaluation. Use `DSPY_MODE=mock` for deterministic tests without real LLM calls.
- **`app/db/models/`** — SQLAlchemy 2.0 async ORM (18 tables). Key entities: `Candidate`, `ChatThread`/`ChatMessage`, `File`/`DocumentChunk`, `Strategy`, `Essay`, `AIRun`.
- **`app/repositories/`** — Data access layer; all DB calls go through repositories, not direct ORM queries in routes.
- **`app/core/job_runner.py`** — In-process async job runner (no Celery). Tasks in `app/workers/tasks/`.
- **`evals/`** — DSPy evaluation framework for offline LLM quality testing.

### Frontend (Next.js 14 App Router)

- **`src/app/`** — Routes/layouts. Uses App Router conventions.
- **`src/features/`** — Feature slices: `chat`, `profile`, `essays`, `tasks`, `strategy`. Each feature contains its own components and hooks.
- **`src/lib/`** — API client helpers. `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`.
- TanStack Query for all data fetching/caching.

### Data flow

1. User authenticates via `POST /candidates/enter` (email only).
2. Chat messages stream via `POST /chat/threads/{id}/messages/stream` (returns `text/plain` stream).
3. DSPy intake interviewer processes messages; profile extraction and document classification run in background jobs.
4. Program research uses Perplexity API via `program_dossier_researcher.py`.
5. Final admission evaluation produced by `admission_evaluation.py`.

### Environment variables

**Root `.env` (for docker-compose + backend):**
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions
OPENAI_API_KEY=...
PERPLEXITY_API_KEY=...
DSPY_MODE=openai   # or "mock" for tests
DSPY_MODEL=openai/gpt-4o-mini
```

**`apps/web/.env.local`:**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```


## Feature Development Pipeline

Feature work follows a multi-agent pipeline. All feature artifacts live in:
`.claude/features/<feature-id>/`  (01-ba-analysis.md → 07-test-report.md)

Start a new feature with: `/feature <feature-id> <description>`
See `.claude/commands/feature.md` for the full pipeline overview.

### Project-specific notes for agents
- Backend tests: `cd backend && pytest -q` (set `DSPY_MODE=mock` to avoid real LLM calls)
- Frontend lint: `make lint-fe`
- Full stack: `make up`
- All DB access goes through `app/repositories/` — never direct ORM in routes
- LLM logic belongs in `app/dspy/` as DSPy modules