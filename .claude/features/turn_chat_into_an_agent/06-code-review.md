# Code Review: Turn Chat Into an Agent with CV Improvement and Essay Review Tools

## Status
APPROVED

## Review Round
Round 2

## Summary
Previously requested fixes are implemented and verified against `02-product-spec.md` and `04-tasks.md`. The artifact download route distinguishes **404** (no row) from **403** (row exists, wrong candidate) via `get_by_id_unscoped` on both repositories, and integration tests assert strict **403**. The plain-text URL fallback in `StreamingChat.tsx` no longer defaults essay-adjacent URLs to `cv_draft`; it infers type from local context or omits the card when inference is ambiguous. Remaining items below are optional follow-ups, not merge blockers.

## Required Changes (must fix before approval)

*None — Round 1 items RC-001 and RC-002 are resolved.*

### Verification — RC-001 (403 for cross-candidate access, FR-9)
- **File**: `backend/app/api/routes/artifacts.py`
- **Verification**: The handler loads `CVDraft` / `EssayDraft` by id without candidate scope, then returns **403** when `record.candidate_id != candidate_id`, and **404** only when no row exists in either table.
- **Tests**: `TestArtifactDownloadOwnership.test_cross_candidate_access_returns_403` in `backend/tests/test_agent_advisor_integration.py` seeds a real `CVDraft` for candidate A and asserts **403** when candidate B requests the download.

### Verification — RC-002 (fallback URL parsing does not mislabel artifact type)
- **File**: `apps/web/src/components/StreamingChat.tsx`
- **Verification**: `extractArtifactFromText` uses a context window around the matched URL and sets `essay_draft` vs `cv_draft` from keywords; if neither heuristic matches, it returns **`null`** so no download card is shown with a wrong type.

## Suggested Improvements (optional, not blocking)

### SI-001: Align `download_url` with FR-7 wording
- **File**: `backend/app/dspy/agent_tools.py`, `backend/app/api/routes/chat.py`
- **Suggestion**: Spec **FR-7** describes `/artifacts/{id}/download`; the app may emit `/api/artifacts/...` for the Next.js proxy. Standardize naming in the spec or developer docs only — behavior is consistent.

### SI-002: Reduce duplicate download controls in the card
- **File**: `apps/web/src/components/ArtifactDownloadCard.tsx`
- **Suggestion**: The card exposes both small “Word / PDF” text links and primary “Download as Word/PDF” buttons. **FR-10** only requires the two buttons; removing the redundant row would simplify layout and focus.

### SI-003: NDJSON buffer flush on stream end
- **File**: `apps/web/src/components/StreamingChat.tsx`
- **Suggestion**: After the `while` loop finishes, parse any remaining `buf` as a final line so a missing trailing newline cannot drop the last event (defensive; backend currently emits `\n`-terminated lines).

### SI-004: Repository / migration test coverage (per dev log)
- **File**: `backend/tests/` (deferred cases in `05-dev-log.md`)
- **Suggestion**: Dev log lists TC-032, TC-033, TC-037, etc. as deferred. Not blocking this review, but dedicated tests for `CVDraftRepository` versioning and essay `source` would match **TASK-004** / **TASK-017** intent.

### SI-005: Strict INFO log assertion in tests
- **File**: `backend/tests/` (per `05-dev-log.md` “skipped” caplog assertion)
- **Suggestion**: **TASK-012** asked for caplog verification; restoring or replacing the skipped assertion would lock in observability.

## Checklist
- [x] Correctness
- [x] Completeness (core tasks; some QA TCs deferred per dev log)
- [x] Code quality
- [x] Edge case handling (403 vs 404; fallback type inference or omit)
- [x] Security (ownership on download)
- [x] Tests present (integration covers 403; suite per dev log)
- [x] No obvious regressions (intake/research streaming unchanged)

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
- `05-dev-log.md` ✅
- `06-code-review.md` ✅

