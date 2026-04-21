# Dev Log: School Selection Advisor

## Status
IN_PROGRESS

## Progress

| Task | Status | Notes |
|------|--------|-------|
| TASK-001 | DONE | Added `StreamingChat` (history load + streaming) and refactored intake step 4 to use it; added `createChatThread` API helper and profile-complete polling to preserve Continue gating. |
| TASK-002 | DONE | Added typed API helpers `confirmSchoolSelection` + `createAdvisorThread` to `apps/web/src/lib/api.ts`. |
| TASK-003 | DONE | Implemented `SchoolSelectionConfirm` and wired it into evaluation footer (skips when selection already exists; confirm flow calls confirm + advisor thread + navigates). |
| TASK-004 | DONE | Updated evaluation failed state CTA to primary “Retry evaluation” button and ensured it restarts evaluation via existing `retryStart`. |
| TASK-005 | DONE | Added Pydantic schemas for school selection confirm payload in `backend/app/schemas/school_selection.py`. |
| TASK-006 | DONE | Implemented `POST /candidates/me/school-selection/confirm` with auth, evaluation gating (409), profile attribute persistence, StrategyDecision upsert, and stage advance to STRATEGY. |
| TASK-007 | DONE | Implemented `POST /chat/advisor-threads` (reuse or create; `?new=true` archives existing) with selected_schools prerequisite + opening assistant message persisted. |
| TASK-008 | DONE | Added `backend/app/dspy/school_advisor.py` opening message generator (mockable) + advisor module scaffolding. |
| TASK-009 | DONE | Implemented `OpenAIAdvisorModule` + `MockAdvisorModule` (DSPy) for advisor-stage chat turns. |
| TASK-010 | DONE | Updated streaming chat routing: reads `thread.extra.stage` and dispatches advisor threads to advisor module via `generate_assistant_response(thread_stage=...)`. |
| TASK-011 | DONE | Ensured advisor thread discoverability via `POST /chat/advisor-threads` default behavior + added repo helper `get_latest_active_thread_by_stage`. |
| TASK-012 | DONE | Added `/advisor` page (App Router) using `StreamingChat`, selected-school pills, quick-action chips (prefill), and “Start new conversation” (forces `?new=true`). |
| TASK-013 | DONE | Updated dashboard CTAs + phase indicator to show strategy phase and “Continue with your advisor” when `selected_schools` exists or stage is strategy+. |
| TASK-014 | DONE | Added unit test for advisor-stage routing in `backend/tests/test_school_advisor_unit.py` (mock mode). |
| TASK-015 | DONE | Added integration tests for confirm selection + advisor thread gating + advisor streaming routing in `backend/tests/test_school_selection_advisor_integration.py`. |
| TASK-016 | BLOCKED | No frontend test runner configured in `apps/web` (no Jest/Vitest scripts); skipped adding new test infra (RC-002 scope decision retained). |

## Code Review Fixes (Round 1)

- **RC-001**: Fixed invalid `/advisor` navigation/redirect routes to use real App Router pages (`/` and `/documents`).
- **RC-003**: Implemented `?notice=select-schools` consumption on home dashboard with a dismissible banner; advisor redirect now targets `/?notice=select-schools`.
- **RC-004**: Aligned empty `selected_schools` to **400** (explicit route validation) and updated backend tests accordingly.
- **RC-002**: Kept TASK-016 as **BLOCKED** (no existing FE test harness; adding Vitest/Jest would expand scope + config surface beyond “small changes” for this review round).

## Test Coverage Notes

- **Covered (backend)**: TC-001, TC-005, TC-006, TC-009, TC-010, TC-012, TC-019, TC-021, TC-023
- **Covered partially (backend)**:
  - TC-015: Verified cross-candidate isolation for thread message access (404); did not implement the “crafted candidate_id” variant (endpoints are `/me`/thread-owned).
  - TC-020: Not implemented (no deterministic spy to assert IntakeInterviewer vs AdvisorModule on intake threads), but existing `test_candidate_sessions_auth.py::test_chat_stream_persists_assistant_message` continues to exercise intake-stage streaming.
- **Not covered (no FE test infra / system tests)**: TC-026–TC-045

## Blockers
- **Frontend unit tests (TASK-016)**: blocked (no test runner configured in `apps/web`).

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
- `05-dev-log.md` ✅ (in progress)

