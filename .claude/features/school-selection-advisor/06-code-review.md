# Code Review: School Selection Advisor

## Status
APPROVED

## Review Round
Round 2

## Summary
Round 1 items RC-001, RC-003, and RC-004 are verified in code: `/advisor` only navigates to existing App Router routes (`/`, `/documents`, `/advisor`), the home dashboard consumes `?notice=select-schools` with a dismissible banner, and empty `selected_schools` returns **400** with pytest coverage aligned. RC-002 is accepted as a **documented, non-blocking** gap: there is no frontend test runner or scripts in `apps/web`, matching the dev-log waiver for TASK-016.

## Required Changes (must fix before approval)

_No blocking items in Round 2._

## Suggested Improvements (optional, not blocking)

### SI-001: Missing `selected_schools` key vs API table
- **File**: `backend/app/api/routes/candidates_enter.py` (`confirm_school_selection`)
- **Suggestion**: The product API table lists **400** when `selected_schools` is missing; a body without the field may still produce **422** (Pydantic). If strict parity matters, validate in-route or document 422 for malformed/missing body per existing `422` row.

### SI-002: Streaming error copy
- **File**: `apps/web/src/components/StreamingChat.tsx`
- **Suggestion**: NFR error states ask for a friendly line after stream failure; ensure user-visible text matches spec.

### SI-003: TASK-016 / frontend tests (tracked gap)
- **File**: `apps/web/package.json`, future `*.test.tsx`
- **Suggestion**: When the repo adopts Vitest (or Jest) + RTL, add minimal tests for `SchoolSelectionConfirm`, `/advisor` redirects, and `StreamingChat` to close QA TC-026–TC-038.

## Round 1 resolution checklist

| ID | Resolution |
|----|------------|
| RC-001 | **Fixed**: Invalid `/dashboard` / `/sign-in` removed; `/advisor` uses `/`, `/documents`, and `/` for unauth. |
| RC-002 | **Waived (non-blocking)**: No FE test harness in repo; TASK-016 remains blocked per dev log; rationale documented. |
| RC-003 | **Fixed**: `CandidateDashboard` shows dismissible banner for `notice=select-schools` after redirect from `/advisor`. |
| RC-004 | **Fixed**: Empty list returns **400** in route; tests expect **400**. |

## Checklist
- [x] Correctness
- [x] Completeness (with documented FE test waiver for TASK-016)
- [x] Code quality
- [x] Edge case handling
- [x] Security
- [x] Tests present (backend strong; FE unit tests waived per repo state)
- [x] No obvious regressions (routing verified)

## QA / tasks alignment notes
- Backend integration/unit coverage remains aligned with confirm, advisor threads, and streaming.
- Frontend QA cases TC-026–TC-045 remain **manual / future automation** until a test runner exists (TASK-016).

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
- `05-dev-log.md` ⚠️ (still `IN_PROGRESS` / TASK-016 blocked — process note only)
- `06-code-review.md` ✅

