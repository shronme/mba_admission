# Test Report: Agent intent classification and rewrite-CV routing

## Status
PASS

## Test Run Summary
- Command: `docker compose exec -T web bash -lc 'cd /app/backend && export PYTHONPATH=. && export DSPY_MODE=mock && pytest -q'`
- Total tests: 163
- Passed: 158
- Failed: 0
- Skipped: 5
- Duration: 32.85s

## Summary
- Backend suite passes under `DSPY_MODE=mock`.
- Updated guard + rewrite-CV tests to match `rewrite_cv`’s JSON return payload (artifact metadata), while still asserting the persisted `cv_draft` body is the rewritten CV text.
- Removed ASGI `/candidates/enter` usage from one integration test to avoid async event-loop mismatch in full-suite runs.

## Failures Detail (with traces)

None.

## Warnings / Non-blocking notes
- Phoenix collector warnings appear but are not treated as failures.

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
- `05-dev-log.md` ✅
- `06-code-review.md` ✅
- `07-test-report.md` ✅

