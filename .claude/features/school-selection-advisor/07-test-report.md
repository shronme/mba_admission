# Test Report: School Selection Advisor

## Status
PASS

## Test Run Summary
- Command: `source backend/.venv/bin/activate && cd backend && export PYTHONPATH=. && export DSPY_MODE=mock && pytest -q`
- Total tests: 50
- Passed: 50
- Failed: 0
- Skipped: 0

## Test Results by Case

| TC ID | Test Name | Result | Notes |
|-------|-----------|--------|-------|
| TC-001 | AdvisorModule produces non-empty output with complete context (mock) | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_advisor_module_returns_non_empty_with_complete_context` |
| TC-002 | AdvisorModule handles empty conversation history | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_advisor_module_handles_empty_history_and_multi_turn_history` (empty history sub-assertion) |
| TC-003 | AdvisorModule handles multi-turn conversation history | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_advisor_module_handles_empty_history_and_multi_turn_history` (multi-turn sub-assertion) |
| TC-004 | AdvisorModule receives all required context fields | ⚠️ PARTIAL | No explicit input-spy assertion; functional coverage via pipeline + module tests above |
| TC-005 | Pipeline routes advisor-stage threads to AdvisorModule | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_pipeline_routes_advisor_stage_to_mock_advisor_module` and `backend/tests/test_school_advisor_unit.py::test_advisor_module_mock_returns_non_empty` |
| TC-006 | Pipeline unchanged behaviour for intake-stage thread | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_pipeline_intake_stage_does_not_use_advisor_module` |
| TC-009 | Opening message generator references confirmed school names (mock non-empty) | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_generate_opening_advisor_message_non_empty_in_mock_mode` |
| TC-010 | School selection confirmation API — happy path (200 OK) | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_school_selection_confirm_happy_path_persists_selection_and_advances_stage` |
| TC-011 | Confirmation API — 400 for empty list | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_school_selection_confirm_rejects_empty_list_with_400` and `backend/tests/test_school_selection_advisor_integration.py::test_confirm_selection_requires_evaluation_complete` (empty list sub-assertion) |
| TC-012 | Confirmation API — 401 for missing/invalid token | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_school_selection_confirm_requires_auth_401` |
| TC-013 | Confirmation API — 409 when evaluation not complete | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_school_selection_confirm_returns_409_when_evaluation_not_complete` and `backend/tests/test_school_selection_advisor_integration.py::test_confirm_selection_requires_evaluation_complete` |
| TC-014 | Confirmation API — idempotency (upsert behaviour) | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_school_selection_confirm_is_idempotent_updates_strategy_decision_payload` |
| TC-016 | Create advisor thread (integration) | ✅ PASS* | Implemented/covered via `POST /chat/advisor-threads` in `backend/tests/test_school_selection_advisor.py::test_advisor_threads_create_and_idempotent_and_opening_message_persisted` (*differs from QA plan path `POST /chat/threads` with `stage="advisor"` but validates equivalent behaviour) |
| TC-017 | Advisor thread creation idempotent | ✅ PASS* | Covered by same test as TC-016 (*see note) |
| TC-019 | Streaming endpoint routes advisor threads to AdvisorModule | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_advisor_streaming_routes_and_persists_assistant_message_and_isolated_404` and `backend/tests/test_school_selection_advisor_integration.py::test_confirm_then_create_advisor_thread_then_stream` |
| TC-021 | Streaming/messages isolation across candidates | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_advisor_streaming_routes_and_persists_assistant_message_and_isolated_404` (404 for other candidate) |
| TC-023 | Advisor thread opening message is available before client connects | ✅ PASS | Covered by `backend/tests/test_school_selection_advisor.py::test_advisor_threads_create_and_idempotent_and_opening_message_persisted` (messages endpoint contains assistant message) |
| TC-024 | Confirmation API latency < 500ms | ⏸️ NOT RUN | Not measured in this automated run |
| TC-025 | Advisor thread creation < 3s (mock) | ⏸️ NOT RUN | Not measured in this automated run |
| TC-026 – TC-038 | Frontend component unit tests | ⏸️ NOT RUN | Per code review waiver: no frontend test runner currently in repo |
| TC-039 – TC-045 | System/E2E flows | ⏸️ NOT RUN | Requires full stack (`make up`) + E2E harness/manual execution |

## Failures Detail
None.

## Coverage (if available)
Not collected in this run (no `pytest-cov` flag used).

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
- `05-dev-log.md` ✅
- `06-code-review.md` ✅
- `07-test-report.md` ✅

