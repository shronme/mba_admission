# mba_admission

Phase 0 bootstrap for the AI Admissions OS foundation.

## What's included
- FastAPI backend service with `/health` endpoint.
- Placeholder worker process container.
- Local infrastructure via Docker Compose (API, worker, Postgres, Redis).
- Backend test suite and CI workflow.
- Deployment ADR documenting Railway-first decision and migration triggers.

## Quick start
```bash
make up
```

Then visit `http://localhost:8000/health`.

## Development checks
```bash
make test
```

## Phase 0 artifacts
- Development plan: `AI_Admissions_OS_Development_Plan.md`
- Validation spec: `AI_Admissions_OS_Validation_Spec.md`
- ADR: `infra/adr/ADR-001-railway-first-deployment.md`
- Deployment guide: `DEPLOY.md`
