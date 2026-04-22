# Code Review: Full-Document Retrieval for Generation Tasks (RAG)

## Status

APPROVED

## Review Round

Round 3

## Summary

**Round 3** reviews two post-approval patches: a stricter `RewriteCVSignature` docstring (no placeholder tokens; fixed Markdown subset for the PDF/DOCX pipeline) and artifact download rendering that parses real Markdown for WeasyPrint and python-docx instead of HTML-escaping the body into a `<pre>`. The implementation matches the described scope, keeps FR-1..FR-8 behavior and contracts unchanged, uses `markdown-it-py` with `html: False`, and should not break TC-022/TC-023-style checks that only assert ZIP/`%PDF` magic bytes and status codes.

**Process warning:** `05-dev-log.md` still lists **Status: AWAITING_REVIEW**; Round 3 fixes landed outside the normal dev-log update cycle.

## Round 3 — Post-approval rendering & rewrite prompt

### Scope (verified)

| Area | File | What changed |
|------|------|----------------|
| Prompt only | `backend/app/dspy/rewrite_cv.py` | `RewriteCVSignature` docstring: omit missing fields/sections; explicit placeholder blocklist; strict Markdown shape (single `#` name H1, contact line, `##` sections in canonical order, bold entry lines, `- ` bullets, no H3/tables/HTML/fences/emojis). |
| Download rendering | `backend/app/api/routes/artifacts.py` | `_markdown_to_html` via `markdown-it-py` + `<pre>` fallback; `_render_markdown_to_docx` for headings/bullets/inline `**bold**`; `body_has_leading_h1` skips duplicate title when body already has `# ...`; PDF wrapped with A4/typography CSS. |

### Verification notes

- **`RewriteCVSignature`:** Input/output field names and descriptions unchanged; `OpenAIRewriteCVModule` / `MockRewriteCVModule` signatures and logic unchanged — **FR-3 tool contract intact**.
- **`_markdown_to_html`:** `MarkdownIt("commonmark", {"html": False, "linkify": False, "breaks": True})` — **raw HTML in source is not enabled**, reducing injection/HTML passthrough risk. Rendered fragment is not double-escaped; title injection remains manually escaped when prepended. Import failure → escaped `<pre>` fallback; endpoint should not 500 on missing lib.
- **`_render_markdown_to_docx`:** `_INLINE_BOLD_RE = \*\*(.+?)\*\*` is appropriate non-greedy pairing for multiple spans per line. Unterminated `**` leaves remainder as literal text — acceptable. Headings strip `**` to inner text for `add_heading`. Bullet vs heading precedence is correct (heading check before bullet on same line structure).
- **`body_has_leading_h1`:** First non-blank line `startswith("# ")` is cheap and correct for rewriter output. **Nit:** an essay draft whose first non-blank line is `# Something` would suppress the DB `title` heading in both PDF and DOCX; unlikely; a stricter heuristic (e.g. artifact type–gated) is optional follow-up, not required for CV-focused fix.
- **Regressions (TC-022 / TC-023):** Integration tests only assert `200`, `PK` prefix, `%PDF` prefix, and content-types — **unchanged by this diff**. Auth/403/404/400 paths untouched. `test_candidate_sessions_auth.py` exercises `/files/.../download`, not `/artifacts/...` — **no conflict**.

## Required Changes (must fix before approval)

*None for Round 3.*

## Suggested Improvements (optional, not blocking)

### SI-001: Clarify em dash in `RewriteCVSignature` blocklist vs template

- **File**: `backend/app/dspy/rewrite_cv.py`
- **Suggestion**: The blocklist forbids `—` "to signal missing data" while the template uses an em dash between company/school and location. Add one line clarifying that the structured header line may use an em dash **only** as that separator, not as a filler for unknown fields — avoids ambiguous instructions to the LM.

### SI-002: Optional artifact-type-aware title suppression

- **File**: `backend/app/api/routes/artifacts.py`
- **Suggestion**: If essay downloads ever start with `# ` intentionally or accidentally, consider gating `body_has_leading_h1` on `cv_draft` vs `essay_draft` (or similar) so essay titles from DB are always shown.

## Checklist (Round 3)

- [x] Correctness (rendering + prompt intent)
- [x] Completeness (post-approval bug scope)
- [x] Code quality
- [x] Edge case handling (fallback import, incomplete bold, leading blank lines)
- [x] Security (`html: False` on Markdown-it; escaped title; no new auth surface)
- [x] Tests (per patch author: `test_artifacts_download.py`, `test_rag_rewrite_cv_tool.py`; structural smoke)
- [x] No obvious regressions on artifact download contracts

## Output Artifacts

- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
- `05-dev-log.md` ✅ (content may lag process state)
- `06-code-review.md` ✅

---

## Archived — Round 2 approval record (unchanged)

The following was **Round 2** (approved before the post-approval patches). It is preserved for history.

### Round 2 — Summary (historical)

The implementation continues to meet FR-1..FR-5, FR-7, and the offline eval story from Round 1. **Round 2** confirms the blocking **RC-001** (FR-6 / TC-040 mock four-tool parity) is fixed: `MockAgentAdvisorModule` accepts and exposes the same four `build_agent_tools` callables as `AgentAdvisorModule`, `pipeline.py` passes all four into the mock, and unit tests construct the mock with four dummy async callables. The `intent.py` comment nit from Round 1 is addressed (no "byte-for-byte" claim; documented one-paren correction).

### Round 2 Verification (historical)

- **RC-001 (`MockAgentAdvisorModule` / FR-6):** Re-read `backend/app/dspy/agent_advisor.py` — constructor takes `retrieve_fn`, `save_fn`, `get_full_document_fn`, `rewrite_cv_fn` (optional, default `None`); `self.tools` is a 4-tuple-ordered list for introspection. Re-read `backend/app/dspy/pipeline.py` — `MockAgentAdvisorModule(...)` is invoked with all four keyword args. Re-read `backend/tests/test_agent_advisor_unit.py` — `TestMockAgentAdvisorModule._make_module` passes four `_async_dummy_fn` callables. **Outcome:** matches required fix from Round 1; **APPROVED** for this item.
- **`intent.py` comment (Round 1 nit, addressed in fix):** Module docstring and `NOTE` now state semantic alignment and the unmatched-paren fix; no misleading "byte-for-byte" claim.
- **Migrations / frontend:** No new files under `backend/alembic/versions/` for this feature. Frontend scope for this feature remains out of scope; unrelated `advisor/page.tsx` churn is unchanged in classification.
- **Tests:** Developer dev log (Review Round 1 Fixes) records `DSPY_MODE=mock pytest -q` → 150 passed, 3 skipped, 2 deselected (WeasyPrint pre-existing). No new test regressions claimed.

**Process note (carried from Round 1):** `05-dev-log.md` may still list **Status: AWAITING_REVIEW** until the dev log is updated after merge/close.

### Required Changes — Round 1 RC resolved in Round 2 (historical)

#### RC-001: `MockAgentAdvisorModule` does not satisfy FR-6 tool surface — **[RESOLVED Round 2]**

- **File**: `backend/app/dspy/agent_advisor.py` (class `MockAgentAdvisorModule`, ~138–184)
- **Related**: `backend/app/dspy/pipeline.py` (~252–256); `backend/tests/test_agent_advisor_unit.py` (`TestMockAgentAdvisorModule._make_module`, ~50–69)
- **Issue (Round 1)**: Product spec FR-6 acceptance criteria required **`MockAgentAdvisorModule`** to **include** `retrieve_candidate_context`, `save_artifact`, `get_full_document`, and `rewrite_cv` (same as `AgentAdvisorModule`). The mock only accepted `save_artifact_fn` and did not take or hold the other three callables. QA **TC-040** traces to the same expectation.
- **Required fix (Round 1)**: Align the mock's constructor (and the advisor-stage wiring in `pipeline.py`) with the four-tool contract; update unit tests that instantiate `MockAgentAdvisorModule()` so construction remains valid.
- **Violates (historical)**: `02-product-spec.md` FR-6; `03-qa-plan.md` TC-040
- **Resolution (Round 2)**: `MockAgentAdvisorModule.__init__` now accepts the four callables, stores `self._retrieve_fn`, `self._save_artifact_fn`, `self._get_full_document_fn`, `self._rewrite_cv_fn`, and exposes `self.tools` in `build_agent_tools` order. `pipeline.py` passes all four from `build_agent_tools`. `test_agent_advisor_unit.py` uses four async dummy callables. Meets FR-6 / TC-040 for mock tool surface and future introspection.

### Nits / optional improvements (historical)

*(Deferred per pipeline in Round 1; not re-raised as required in Round 2.)*

- **`intent.py` docstring vs reality** — **Addressed** in this round: comment no longer claims byte-for-byte spec alignment; documents the one-paren correction.
- **Pipeline full-doc detection** (`backend/app/dspy/pipeline.py`, ~288–290): Branching on `first.startswith("[")` and `— full text]` — deferred follow-up.
- **`rewrite_cv` persistence vs return** (`backend/app/dspy/agent_tools.py`): If `save_artifact` raises — deferred follow-up.
- **Repository layering** (`backend/app/dspy/agent_tools.py`, profile/dossier loads): — deferred follow-up.
- **Placement**: `intent.py` under `app/dspy/` — no change.

### Positives (historical)

- **`UploadedFileRepository`** is clear, tested-friendly, and correctly enforces latest-only + non-empty `extracted_text` at the SQL layer with a sensible Python guard.
- **Chat preload** correctly skips `search_async` on intent match and returns an empty list when no CV/life story — no semantic fallback, per v1 replace semantics.
- **`rewrite_cv`** missing-CV path uses the exact spec string and returns before any `save_artifact` call.
- **`MockRewriteCVModule`** intentionally preserves CV body for deterministic CI coverage; header wrapper is honest about mock mode.
- **`max_iters=6`** includes an explicit, accurate comment tying the bump to rewrite trajectories (`agent_advisor.py`, ~115–119).
- **Round 2:** `MockAgentAdvisorModule` docstring explicitly ties behavior to FR-6 and TC-040; `self.tools` gives a stable contract for future tests.

### Coverage matrix (historical)

| FR | Primary implementation | Verdict |
|----|-------------------------|---------|
| FR-1 | `backend/app/dspy/intent.py`, `chat.py` | ✅ (regex compiles; paren fix matches spec intent; `(?i)` applies to `\bSOP\b` — consistent with pinned pattern) |
| FR-2 | `agent_tools.py` (`get_full_document`), `uploaded_file_repository.py` | ✅ (exact error strings; strict enum; full text in success body) |
| FR-3 | `agent_tools.py` (`rewrite_cv`), `rewrite_cv.py` | ✅ (required error string; no `save_artifact` on missing CV; silent dossier skip; success persists `cv_draft`) |
| FR-4 | `chat.py`, `pipeline.py` | ✅ tags exact; ⚠️ join heuristic could be more explicit (deferred nit) |
| FR-5 | `document_processing.py` | ✅ |
| FR-6 | `agent_advisor.py`, `pipeline.py`, `agent_tools.py` | ✅ **mock module mirrors four-tool registration (`self.tools` + pipeline wiring) — RC-001 resolved Round 2** |
| FR-7 | `backend/evals/rewrite_cv/*`, `backend/evals/fixtures/cv/*` | ✅ wiring; ⚠️ mock-mode coverage gate is tautological (regression harness only — see nits in Round 1 summary) |
| FR-8 | (integration tests deferred) | ✅ `build_agent_tools` / real + mock `AgentAdvisorModule` shapes are aligned for trajectory-style tests |

### Appendix — files reviewed (historical)

*Round 1 list retained; Round 2 additionally verified post-fix state of:*

- `backend/app/dspy/agent_advisor.py` (`MockAgentAdvisorModule` constructor, `self.tools`)
- `backend/app/dspy/pipeline.py` (mock construction)
- `backend/tests/test_agent_advisor_unit.py` (`_make_module`)
- `backend/app/dspy/intent.py` (docstring / NOTE re FR-1 paren)

**Out of scope / confirmed:** `apps/web/src/app/advisor/page.tsx` churn is not part of this feature per product spec (no frontend scope). `backend/alembic/versions/` — no *new* migration for this feature. Pre-existing WeasyPrint deselection per `CLAUDE.md` — not flagged.

### Checklist (historical — Round 2)

- [x] Correctness
- [x] Completeness (including FR-6 mock AC)
- [x] Code quality
- [x] Edge case handling (major paths; deferred nits for persistence/heuristic)
- [x] Security (no new obvious exposure; synthetic eval fixtures)
- [x] Tests present (existing unit tests; re-run in CI / local env with `DSPY_MODE=mock`)
- [x] No obvious regressions on non-intent chat path (`search_async` default `top_k=6` preserved)

### Historical footer (Round 2)

Next (at time of Round 2): run `/feature-write-tests rag-full-document-retrieval` to add tests per the QA plan, then `/feature-test` for final verification.
