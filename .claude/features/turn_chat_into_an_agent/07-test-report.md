# Test Report: Turn Chat Into an Agent with CV Improvement and Essay Review Tools

## Status
FAIL

Two integration tests fail in the artifact-download generation flow (TC-022 / TC-023). The unit layer (42/42) and all other integration suites pass cleanly. Frontend lint passes with a single pre-existing (non-feature) warning.

## Test Run Summary

### Backend (`pytest -q` with `DSPY_MODE=mock`)
- Command: `DSPY_MODE=mock PYTHONPATH=. DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/mba_admissions pytest -q`
  (executed inside `docker-compose run --rm web` so WeasyPrint's native libs — `libpango`, `libgdk-pixbuf`, fonts — are present, per the feature's `backend/Dockerfile`)
- Total tests: 92
- Passed: 88
- Failed: 2
- Skipped: 2
- Warnings: 5 (all pre-existing FastAPI `on_event` / Alembic `path_separator` deprecation noise, unrelated to this feature)

### Frontend lint (`make lint-fe`)
- Command: `make lint-fe` → `cd apps/web && npm run lint`
- Result: exit 0; 0 errors; 1 warning in `apps/web/src/components/SearchableMultiSelect.tsx:141` (`jsx-a11y/role-has-required-aria-props` — pre-existing, outside this feature's scope).

### Environment
- Postgres: `mba_admission-postgres-1` (pgvector/pgvector:pg16) reachable at `localhost:5432`; test DB auto-migrated from `backend/tests/conftest.py`.
- DSPy: `mock` mode — no network calls to OpenAI / Perplexity.
- Python: 3.11 (Docker image). Host venv also exercised but host lacks `libpango` for WeasyPrint; Docker run is the canonical environment per `CLAUDE.md`.

---

## Test Results by Case

### Unit tests (QA-plan TC-001 → TC-023 that are marked Unit)

| TC ID | Test | Result | Notes |
|-------|------|--------|-------|
| TC-001 | `TestAgentAdvisorModuleInstantiation::test_react_attribute_exists_with_correct_config` | PASS | Asserts `max_iters == 4` (spec said 8; implementation lowered it to 4 with an in-code comment; the test matches the current code, not the spec). |
| TC-002 | `TestAgentAdvisorModuleForward::test_forward_delegates_to_react` | PASS | — |
| TC-003 | `TestAgentAdvisorModuleAforward::test_aforward_delegates_to_react_aforward` | PASS | — |
| TC-004 | `TestMockAgentAdvisorModule::test_cv_message_returns_cv_artifact` / `test_cv_uppercase_returns_cv_artifact` | PASS | — |
| TC-005 | `TestMockAgentAdvisorModule::test_essay_message_returns_essay_artifact` / `test_essay_mixed_case` / `test_cv_takes_precedence_over_essay` | PASS | — |
| TC-006 | `TestMockAgentAdvisorModule::test_unrelated_message_returns_generic_response` / `test_empty_message_does_not_crash` | PASS | — |
| TC-007 | `TestMockAgentAdvisorModule::test_aforward_is_awaitable` / `test_aforward_and_forward_return_same_result` | PASS | — |
| TC-008 | `TestRetrieveCandidateContext::test_returns_numbered_chunk_list` | PASS | — |
| TC-008 (edge) | `TestRetrieveCandidateContext::test_returns_empty_string_when_no_chunks` | PASS | — |
| TC-009 | `TestRetrieveCandidateContext::test_candidate_isolation_different_candidate_ids` | PASS | — |
| TC-010 | `TestSaveArtifactTool::test_cv_draft_calls_cv_repository` | PASS | — |
| TC-011 | `TestSaveArtifactTool::test_essay_draft_creates_row_with_source_agent` | PASS | — |
| TC-012 | `TestSaveArtifactTool::test_invalid_artifact_type_returns_error_string` | PASS | — |
| TC-013 | `TestSaveArtifactTool::test_download_url_format` | PASS | — |
| TC-014 | `TestPipelineRouting::test_advisor_stage_routes_to_mock_agent` | PASS | — |
| TC-015 | `TestPipelineRouting::test_intake_stage_does_not_use_advisor` / `test_research_stage_does_not_use_advisor` | PASS | — |
| TC-016 | `TestPipelineRouting::test_essay_guardrail_does_not_fire_for_advisor` | PASS | — |
| TC-017 | `TestPipelineRouting::test_essay_guardrail_fires_for_intake_stage` / `test_essay_guardrail_fires_for_none_stage` | PASS | — |
| TC-018 | `TestArtifactDownloadAuth::test_missing_auth_returns_401` / `test_malformed_token_returns_401` | PASS | — |
| TC-019 | `TestArtifactDownloadFormat::test_invalid_format_returns_400` | PASS | — |
| TC-020 | `TestArtifactDownloadNotFound::test_nonexistent_artifact_returns_404` | PASS | — |
| TC-021 | `TestArtifactDownloadOwnership::test_cross_candidate_access_returns_403` | PASS | — |
| TC-022 | `TestArtifactDownloadGeneration::test_docx_download_returns_valid_zip` | **FAIL** | 422 returned by `/artifacts/{id}/download`; details in Failures section. |
| TC-023 | `TestArtifactDownloadGeneration::test_pdf_download_returns_pdf_bytes` | **FAIL** | Same root cause as TC-022. |

### Integration tests

| TC ID | Test | Result | Notes |
|-------|------|--------|-------|
| TC-024 | `TestStreamingProtocol::test_advisor_stage_stream_content_type_ndjson` | PASS | — |
| TC-025 | `TestStreamingProtocol::test_advisor_stage_stream_lines_are_valid_json` | PASS | — |
| TC-026 | `TestStreamingProtocol::test_intake_stage_stream_remains_text_plain` | PASS | — |
| TC-027 | `TestAdvisorStreamEvents::test_cv_request_emits_artifact_event` | PASS | — |
| TC-028 | `TestAdvisorStreamEvents::test_text_chunks_accumulate_to_full_response` | PASS | — |
| TC-029 | `TestAdvisorStreamErrorEvent::test_agent_exception_emits_error_event` | PASS | — |
| TC-030 | `TestAdvisorStreamEvents::test_artifact_download_url_is_relative` | PASS | — |
| TC-031 | `TestChatMessageExtraPersistence::test_assistant_message_extra_has_artifact_fields` | SKIP | Test self-skips: "ChatMessage.extra persistence not yet implemented or not returned in API". Advisor-stage stream does patch `extra`, but the history endpoint used by the test does not surface it. Coverage is partial. |
| TC-032 | — | DEFERRED | Integration persistence test not authored (per `05-dev-log.md` "TC IDs deferred"). TC-010/TC-011 provide unit-level coverage. |
| TC-033 | — | DEFERRED | Same as TC-032. |
| TC-034 | — | DEFERRED | Schema verified manually via `alembic upgrade head && downgrade -1` in TASK-018; no dedicated pytest. |
| TC-035 | — | DEFERRED | Same as TC-034. |
| TC-036 | — | DEFERRED | Real pgvector round-trip not authored; TC-008 gives structural coverage. |
| TC-037 | — | DEFERRED | Version-increment test not authored. |
| TC-038 | — | DEFERRED | docx round-trip with real DB row not authored (would have masked the TC-022 failure). |
| TC-039 | — | DEFERRED | pdf round-trip with real DB row not authored. |
| TC-040 | — | DEFERRED | Full turn + reload test not authored; partial coverage from TC-027/TC-028/TC-031. |
| TC-041 | — | DEFERRED | Mock module does not model "which school?" ask. |
| TC-042 | — | DEFERRED | Same as TC-041. |
| TC-052 | `TestObservabilityLogging::test_advisor_turn_produces_info_log` | SKIP | Self-skips: "caplog did not capture app logs in this environment". Pre-existing ASGI + caplog limitation documented in dev log. |
| TC-053 | (subsumed by TC-021) | PASS | Covered by `test_cross_candidate_access_returns_403`. |
| TC-054 | (meta: full suite green in mock) | FAIL | Overall suite has 2 failures; condition not met. |

### System / E2E tests (Playwright)

| TC IDs | Tests | Result | Notes |
|--------|-------|--------|-------|
| TC-043 – TC-051 | `apps/web/e2e/advisor-agent.spec.ts` | NOT RUN | Playwright spec exists (per dev log) but the feature pipeline's `/feature-test` step exercises backend pytest + frontend lint only. Running it requires a live `make up` stack and is outside the scope of this test run. |

---

## Failures Detail

### TC-022: `test_docx_download_returns_valid_zip`
- **File**: `backend/tests/test_agent_advisor_integration.py:732`
- **Assertion**: `assert r.status_code == 200` → actual `422`
- **Response body**:
  ```json
  {"detail":[{"type":"uuid_parsing","loc":["path","artifact_id"],
              "msg":"Input should be a valid UUID, invalid character: expected an optional prefix of `urn:uuid:` followed by [0-9a-fA-F-], found `m` at 1",
              "input":"mock-cv-artifact-id"}]}
  ```
- **Likely cause**: The test drives the full advisor stream end-to-end under `DSPY_MODE=mock`. In that mode, `MockAgentAdvisorModule` (`backend/app/dspy/agent_advisor.py:96-114`) returns a hard-coded `artifact_id="mock-cv-artifact-id"` and never invokes the `save_artifact` tool, so no `cv_drafts` row exists. The stream's `artifact` event therefore carries the fake string ID, and the subsequent `GET /artifacts/mock-cv-artifact-id/download` is rejected by FastAPI's `uuid.UUID` path parameter validator (`backend/app/api/routes/artifacts.py:26`).
- **Recommended fix** (choose one):
  1. Make `MockAgentAdvisorModule` call `save_artifact_fn` (the tool closure injected by the pipeline) so a real `cv_drafts` / `essay_drafts` row is written with a real UUID. This matches the spec's intent ("deterministic mock pipeline end-to-end") and makes TC-022/TC-023 pass without tests-only workarounds.
  2. Alternatively, have `MockAgentAdvisorModule` return a valid UUID (e.g., `uuid.uuid4()`) and have the mock tool closure persist a stub row under that UUID.
  3. Lowest-effort workaround: change the two tests to `pytest.skip()` when the returned `artifact_id` is not UUID-shaped, and add a new unit-style test that stubs a real DB row and hits `/artifacts/{id}/download?format=docx` directly.
- Option (1) is strongly preferred: it preserves the QA plan's black-box intent (TC-022/TC-023 are the only coverage for docx/pdf content-type, magic-bytes, and filename headers).

### TC-023: `test_pdf_download_returns_pdf_bytes`
- **File**: `backend/tests/test_agent_advisor_integration.py:799`
- **Assertion**: `assert r.status_code == 200` → actual `422`
- **Error**: Same 422 shape as TC-022 (UUID parse error on `"mock-cv-artifact-id"`).
- **Likely cause**: Identical to TC-022.
- **Recommended fix**: Identical to TC-022.

> Note: a separate "PDF generation smoke" test (`tests/test_artifacts_download.py::test_artifact_download_pdf_smoke`) exercises WeasyPrint directly without going through the mock advisor — it **PASSES** inside Docker, confirming that (a) `weasyprint==62.3` + `libpango` are wired correctly per `backend/Dockerfile` and (b) the two failures above are purely an integration-harness issue, not a PDF-generation defect.

---

## Host-environment caveat (not a failure)

When run against the host venv (no Docker), WeasyPrint's native deps are unavailable on macOS by default:
```
OSError: cannot load library 'gobject-2.0-0'
```
This is explicitly called out as a "Hard-to-Test Area" in `03-qa-plan.md` and is addressed in the feature's own `backend/Dockerfile` (TASK-001 installed `libpango-1.0-0`, `libgdk-pixbuf-2.0-0`, `fonts-liberation`, `fonts-noto`, `shared-mime-info`). Running `pytest` inside `docker-compose run --rm web` (as in this report) is the canonical execution environment and matches CI.

## Coverage (if available)
Not collected (`pytest-cov` is installed but not invoked with `--cov`). The QA plan does not require a coverage threshold.

---

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
- `05-dev-log.md` ✅
- `06-code-review.md` ❌ (not yet authored — `/feature-review turn_chat_into_an_agent` was not run before this tester pass; see "Process deviation" below)
- `07-test-report.md` ✅

## Process deviation
Per the tester-agent contract, code review must be `APPROVED` before running tests. No `06-code-review.md` exists yet for this feature. Tests were still run as explicitly requested in the invocation, and the results above are valid for the current code state; however, the human checkpoint should consider running `/feature-review turn_chat_into_an_agent` before signing off, and re-running `/feature-test` after the TC-022/TC-023 fix lands.
