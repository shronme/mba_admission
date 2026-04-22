# QA Test Plan: Full-Document Retrieval for Generation Tasks (RAG)

## Summary

This plan tests feature **`rag-full-document-retrieval`** against `.claude/features/rag-full-document-retrieval/02-product-spec.md` (Status: COMPLETE). Scope: **FR-1** intent regex (two-way branch); **FR-2** `get_full_document` + repository; **FR-3** `rewrite_cv` + `save_artifact`; **FR-4** chat preload and `pipeline.py` joining; **FR-5** forward-only ingestion (`document_processing.py`); **FR-6** advisor signature and four-tool registration; **FR-7** offline `rewrite_cv` evals; **FR-8** deterministic tool-selection integration tests (mocked trajectories, not live LLM). Non-functional gates: **DSPY_MODE=mock** for default CI, no Q&A-path latency regression on non-matching turns, no schema migration/backfill, synthetic fixtures only.

Context: `.claude/features/rag-full-document-retrieval/01-ba-analysis.md`.

## Status

COMPLETE

## Coverage Summary

- Unit tests: 28
- Integration tests: 14
- System/E2E tests: 3
- Offline evals: 4

## Requirements Traceability (by FR)

### FR-1 — Intent regex (two-way classifier)

| ID | Layer | Description | Inputs / trigger | Expected outcome | FR / AC |
|----|-------|-------------|------------------|------------------|---------|
| TC-001 | Unit | Clear match — verb before doc | e.g. "Please rewrite my CV" | `_REWRITE_INTENT_RE` matches; branch selects full-doc preload path (see FR-4 tests) | FR-1; AC2 (regression path for "no match" tested separately) |
| TC-002 | Unit | Clear match — doc before verb | e.g. "CV please polish" within 6 tokens | Pattern matches | FR-1 |
| TC-003 | Unit | No match — semantic Q&A | "Summarize my leadership", "What's my GMAT?" | No match; unchanged semantic preload path | FR-1; AC2, AC5 |
| TC-004 | Unit | Near-miss — rewrite verb without document noun | e.g. "rewrite that section" | No match | FR-1 |
| TC-005 | Unit | Near-miss — document noun without verb | e.g. "here is my CV" | No match | FR-1 |
| TC-006 | Unit | Near-miss — verb and doc > 6 tokens apart | Constructed string exceeding window | No match | FR-1 |
| TC-007 | Unit | Near-miss — rewrite-like phrase embedded in unrelated context | Long sentence with keywords far apart | No match | FR-1 |
| TC-008 | Unit | Unicode — `résumé` in message | Contains résumé + verb within window | Matches | FR-1 |
| TC-009 | Unit | `SOP` vs `sop` | `\bSOP\b` case / whole-word behavior per spec | `SOP` matches as intended; lowercase `sop` per regex semantics (assert pinned behavior) | FR-1 |
| TC-010 | Unit | `life story` with extra whitespace | Normalized or extra spaces — assert against pinned pattern | Match/no-match per authoritative regex | FR-1 |

### FR-2 — `get_full_document(document_type)`

| ID | Layer | Description | Inputs / trigger | Expected outcome | FR / AC |
|----|-------|-------------|------------------|------------------|---------|
| TC-011 | Unit | Valid `cv` with text | `get_full_document("cv")` | Returns body including full `extracted_text` for latest file | FR-2 |
| TC-012 | Unit | Invalid type — empty string | `""` | Exact: `Unsupported document_type ''. Valid: cv, life_story, recommendation_letter, grade_sheet.` | FR-2 |
| TC-013 | Unit | Invalid type — whitespace | `"  "` | Unsupported string verbatim in message | FR-2 |
| TC-014 | Unit | Invalid type — `"CV"` uppercase | Exact error with `<x>` = `CV` | FR-2 |
| TC-015 | Unit | Invalid type — `"invalid"`, `"irrelevant"`, `"unclassified"` | Each | Exact unsupported string | FR-2 |
| TC-016 | Integration | No row / no usable text | No upload or `extracted_text` null/empty | Exact: `No document of type '<x>' uploaded for this candidate.` | FR-2 |
| TC-017 | Integration | Multiple CVs — latest wins | Two `UploadedFile` rows `document_type=cv`, different `created_at` | Repository / tool returns content matching `ORDER BY created_at DESC LIMIT 1` | FR-2; Flow 4 |

### FR-3 — `rewrite_cv`

| ID | Layer | Description | Inputs / trigger | Expected outcome | FR / AC |
|----|-------|-------------|------------------|------------------|---------|
| TC-018 | Integration | Happy path | CV present, optional life story/profile | Returns rewritten text; `save_artifact` called with `artifact_type=cv_draft`; row in `cv_drafts` | FR-3; AC1 |
| TC-019 | Unit/Integration | Missing CV | No CV with extracted text | Exact error: `Cannot rewrite CV: no CV document with extracted text is available for this candidate.`; **no** `save_artifact` | FR-3; Flow 3 |
| TC-020 | Integration | Missing life story | CV only | Succeeds; no life-story requirement | FR-3 |
| TC-021 | Integration | Empty profile JSON | Profile empty | Tool still runs; no unhandled error | FR-3 |
| TC-022 | Integration | `target_school` with no dossier match | Unknown school | Dossier skipped silently; rewrite still returns | FR-3 |
| TC-023 | Integration | `rewrite_cv` twice in one turn / back-to-back | Two invocations | Deterministic expectations: e.g. two drafts or idempotent policy per implementation — assert documented behavior and `save_artifact` calls | FR-3 |

### FR-4 — Preload + `pipeline.py` joining

| ID | Layer | Description | Inputs / trigger | Expected outcome | FR / AC |
|----|-------|-------------|------------------|------------------|---------|
| TC-024 | Integration | FR-1 match + CV only | Upload CV, no life story | Preload contains `[CV — full text]\n...\n[End CV]` only; no life-story block | FR-4; AC1 |
| TC-025 | Integration | FR-1 match + life story only | No CV, life story present | Life story block only; CV absent or empty per spec | FR-4 |
| TC-026 | Integration | FR-1 match + neither document | Clear rewrite intent | Tagged blocks reflect uploads; edge: empty/missing sections | FR-4; Flow 3 |
| TC-027 | Unit/Integration | Non-English Unicode in `extracted_text` | Embedded unicode in stored text | Full text preserved inside tags | FR-4 |
| TC-028 | Unit | Exact tag strings | Snapshot of assembled preload | `[CV — full text]\n`, `\n[End CV]`, `[Life story — full text]\n`, `\n[End Life story]` exact per spec | FR-4 |
| TC-029 | Unit | `pipeline.py` join — full-doc mode | List of tagged blocks | Joined with `\n\n`; **no** `[{i+1}]` numeric prefixes on full-doc path | FR-4 |
| TC-030 | Integration | No FR-1 match | Non-matching message | Semantic `search_async` preload; same contract as baseline | FR-4; AC2 |

### FR-5 — Ingestion (`document_processing.py`)

| ID | Layer | Description | Inputs / trigger | Expected outcome | FR / AC |
|----|-------|-------------|------------------|------------------|---------|
| TC-031 | Unit | Stored `extracted_text` length cap | Input > previous cap | Stored text respects **200_000** char cap (new processing) | FR-5; AC3 |
| TC-032 | Unit | Chunk count upper bound | ~200k-char synthetic text | **≤200** chunks per file | FR-5 |
| TC-033 | Unit | Very short document | Minimal text | Single chunk; no error | FR-5 |
| TC-034 | Unit | Document shorter than overlap | Edge relative to 50-token overlap | Splitter still completes; assert no infinite loop / reasonable chunk list | FR-5 |
| TC-035 | Unit | Token size per chunk | tiktoken-based splitter | Chunks **≤600** tokens (last chunk may be shorter) | FR-5 |
| TC-036 | Unit | Classifier input unchanged | Code constant | `_CLASSIFY_MAX_CHARS == 4000` unchanged | FR-5 |
| TC-037 | Integration | Forward-only — already processed file | No reprocess trigger | Existing rows not re-chunked until reprocess/reupload | FR-5; NFR forward-only |

### FR-6 — Signature + tool registration

| ID | Layer | Description | Inputs / trigger | Expected outcome | FR / AC |
|----|-------|-------------|------------------|------------------|---------|
| TC-038 | Unit | `build_agent_tools` arity and order | Import and call | Four callables: `(retrieve_candidate_context, save_artifact, get_full_document, rewrite_cv)` | FR-6 |
| TC-039 | Unit | All unpack sites | `pipeline.py`, unit tests | No arity errors; mocks updated | FR-6 |
| TC-040 | Unit | `MockAgentAdvisorModule` | Construction | Receives four tools; tests pass | FR-6 |
| TC-041 | Unit | `max_iters` | Rewrite trajectory | Sufficient iterations for `get_full_document` / `rewrite_cv` paths | FR-6 |

### FR-7 — Offline eval `rewrite_cv`

| ID | Layer | Description | Inputs / trigger | Expected outcome | FR / AC |
|----|-------|-------------|------------------|------------------|---------|
| TC-042 | Eval | Coverage pass — pass | Synthetic fixture rewrite | ≥95% roles/companies/dates/education retained (fuzzy rules in eval code) | FR-7; AC1, AC6 |
| TC-043 | Eval | Coverage pass — fail | Deliberately drop a role in mock rewrite | Below threshold; gate fails | FR-7 |
| TC-044 | Eval | Hallucination judge | `DSPY_MODE=openai` | Judge runs; flags ungrounded facts | FR-7; AC6 |
| TC-045 | Eval | CI default | `DSPY_MODE=mock` | Coverage runs; **no** live OpenAI for judge in default CI | FR-7; AC6 |

### FR-8 — Tool-selection integration (deterministic)

| ID | Layer | Description | Inputs / trigger | Expected outcome | FR / AC |
|----|-------|-------------|------------------|------------------|---------|
| TC-046 | Integration | Seeded rewrite-class prompts | Mocked tool trajectories | ≥95% select `get_full_document` (or equivalent "full doc used") on seeded rewrite set | FR-8; AC4 |
| TC-047 | Integration | Seeded non-rewrite / Q&A prompts | Mocked | Correct preload/tool path; no false full-doc forced path | FR-8; AC2 |

## Non-functional / regression tests

| ID | Layer | Description | Expected outcome |
|----|-------|-------------|------------------|
| TC-048 | Unit/Integration | Q&A latency proxy — no FR-1 match | `search_async` invoked with default `top_k` (e.g. 6 for chat preload); **no** extra full-document DB reads on that path |
| TC-049 | Process | No new Alembic migration for this feature | Spec: no schema change; review that feature delivery does not add hand-authored migrations |
| TC-050 | Process/CI | Dependency | `langchain-text-splitters` declared; `backend` installs in Docker/CI |
| TC-051 | System/E2E | Optional streaming smoke | Non-matching turn still streams end-to-end (manual or thin automated smoke); baseline parity |

## Test Cases

### TC-001: FR-1 — Clear match (verb before document)
- **Type**: Unit
- **Requirement**: FR-1
- **Preconditions**: Regex module / helper under test
- **Steps**:
  1. Feed user message that places an allowed verb within six tokens of an allowed document phrase (verb-first).
  2. Assert pattern match is True.
- **Expected Result**: Match; downstream preload uses full-doc path (verified in TC-024–TC-030).
- **Edge Cases / Variants**: Multiple verbs and document types from pinned list.

### TC-002: FR-1 — Clear match (document before verb)
- **Type**: Unit
- **Requirement**: FR-1
- **Steps**:
  1. Feed message with document phrase first, verb within window.
  2. Assert match.
- **Expected Result**: True.

### TC-003: FR-1 — No match (Q&A prompts)
- **Type**: Unit
- **Requirement**: FR-1, NFR performance
- **Steps**:
  1. "Summarize my leadership", "What's my GMAT?"
  2. Assert no match.
- **Expected Result**: Semantic preload path unchanged (cross-check TC-030, TC-048).

### TC-004–TC-007: FR-1 — Near-miss negatives
- **Type**: Unit
- **Requirement**: FR-1
- **Steps**: Per rows TC-004–TC-007 in traceability table.
- **Expected Result**: No match.

### TC-008–TC-010: FR-1 — Unicode and token edge cases
- **Type**: Unit
- **Requirement**: FR-1
- **Steps**: Exercise `résumé`, `SOP`/`sop`, `life story` spacing variants.
- **Expected Result**: Behavior aligned with authoritative `_REWRITE_INTENT_RE` only.

### TC-011–TC-017: FR-2 — `get_full_document` and repository
- **Type**: Unit / Integration
- **Requirement**: FR-2
- **Preconditions**: DB fixtures or mocked `UploadedFileRepository` / session
- **Steps**: Valid success path; each invalid type; no document; empty `extracted_text`; two CV rows ordered by `created_at`.
- **Expected Result**: Exact error strings from spec; latest-only content on success.

### TC-018–TC-023: FR-3 — `rewrite_cv`
- **Type**: Integration
- **Requirement**: FR-3
- **Preconditions**: `DSPY_MODE=mock` for CI; optional DB fixtures for drafts
- **Steps**: Happy path; missing CV; CV-only; empty profile; dossier miss; double invocation.
- **Expected Result**: See traceability table; `save_artifact` only on success paths per spec.

### TC-024–TC-030: FR-4 — Preload and pipeline
- **Type**: Unit / Integration
- **Requirement**: FR-4
- **Preconditions**: Chat route / `_retrieve_doc_snippets` test harness; sample uploads
- **Steps**: Match vs no-match; CV-only; life-story-only; neither; unicode; assert tag strings and `pipeline.py` join without numeric prefixes in full-doc mode.
- **Expected Result**: FR-4 acceptance criteria.

### TC-031–TC-037: FR-5 — Ingestion
- **Type**: Unit / Integration
- **Requirement**: FR-5
- **Preconditions**: Worker or isolated `_extract_text` tests; large synthetic strings
- **Steps**: Length cap, chunk bound, short doc, overlap edge, token cap, `_CLASSIFY_MAX_CHARS`, skip re-chunk without reprocess.
- **Expected Result**: Forward-only semantics; caps per spec.

### TC-038–TC-041: FR-6 — Tools and mocks
- **Type**: Unit
- **Requirement**: FR-6
- **Steps**: Assert tuple order; update all unpack sites; `MockAgentAdvisorModule`; `max_iters`.
- **Expected Result**: Four tools everywhere; trajectories complete in tests.

### TC-042–TC-045: FR-7 — Evals
- **Type**: Eval (offline)
- **Requirement**: FR-7
- **Preconditions**: `backend/evals/fixtures/cv/` synthetic CVs; eval entrypoint
- **Steps**: Run coverage gate under mock; optional judge with `DSPY_MODE=openai`.
- **Expected Result**: Coverage ≥95% structured fields; judge optional outside default CI.

### TC-046–TC-047: FR-8 — Tool selection
- **Type**: Integration
- **Requirement**: FR-8
- **Preconditions**: `backend/tests/test_agent_advisor_integration.py` seeded messages; mocked trajectories (not live LLM eval)
- **Steps**: Aggregate tool-choice or preload-path assertions over seeded rewrite vs non-rewrite sets.
- **Expected Result**: ≥95% on rewrite-class seeded set.

### TC-048–TC-051: Non-functional
- **Type**: Unit / Integration / Process / System
- **Requirement**: NFR
- **Steps**: See Non-functional table.
- **Expected Result**: No Q&A regression; deps and process gates satisfied.

## Test Data Requirements

- **Synthetic CV fixtures (~5):** Under `backend/evals/fixtures/cv/` — varied length, sections, non-English names, gaps, multi-role company; **no PII**.
- **Life story sample text:** For preload and `rewrite_cv` integration tests.
- **Recommendation letter / grade sheet samples:** For `get_full_document("recommendation_letter" | "grade_sheet")` success paths.
- **Seeded chat messages:** Rewrite-class prompts (for FR-8 and FR-1 integration); Q&A-class ("summarize leadership", GMAT, factual) for regression.
- **Mock `knowledge_chunks` row:** Optional dossier row for `target_school` match; absent row for silent-skip test.
- **DB fixtures:** Multiple `UploadedFile` rows per type for latest-only ordering; rows with empty/null `extracted_text` for negative paths.

## Environment Requirements

- **Default CI:** `DSPY_MODE=mock` — no live OpenAI for unit/integration/eval coverage gate.
- **Optional / nightly:** `DSPY_MODE=openai` for LLM-judge hallucination pass (FR-7).
- **Postgres:** Integration tests that hit `UploadedFile` / `cv_drafts` / `knowledge_chunks` (or equivalent test DB) as per existing backend test patterns.
- **Env vars:** `OPENAI_API_KEY` only where embedding/search tests require (or mock clients per existing tests).

## Hard-to-Test Areas

- **End-to-end stream latency (AC5):** "No material regression" is environment-dependent. **Workaround:** Unit/integration proxies — no extra DB reads on non-match path (TC-048); optional manual timing smoke on staging.
- **Exact OpenAI embedding behavior:** Mock `AsyncOpenAI` / vector store in tests; assert call counts and `top_k`.
- **LLM-judge flakiness:** Excluded from default CI; run only in `DSPY_MODE=openai` with fixed seeds if available.
- **tiktoken / splitter parity across platforms:** Pin dependency versions; run ingestion tests in CI Docker image matching prod.

## Exit Criteria (spec acceptance criteria → test IDs)

| # | Acceptance criterion | Test IDs proving the criterion |
|---|----------------------|--------------------------------|
| 1 | **Preservation** — offline coverage eval ≥95% on structured fields (FR-7) | TC-042, TC-043 |
| 2 | **Regression** — leadership/summary Q&A still semantic retrieval | TC-003, TC-030, TC-047, TC-048 |
| 3 | **Long life stories** — up to 200k chars stored; chunking coverage (FR-5) | TC-031, TC-032, TC-035 |
| 4 | **Tool selection** — ≥95% seeded rewrite-class via mocked integration (FR-8) | TC-046 |
| 5 | **Latency** — no material regression for non-matching Q&A turns | TC-048, TC-051 (smoke) |
| 6 | **Module quality** — hallucination judge only in `DSPY_MODE=openai`; coverage in CI | TC-044, TC-045 |

## Tooling / run instructions

- **Full backend suite (default CI):**
  ```bash
  cd backend && DSPY_MODE=mock pytest -q
  ```
- **Targeted examples:**
  ```bash
  pytest tests/test_agent_advisor_unit.py -k rewrite_intent
  pytest tests/test_agent_advisor_integration.py -k tool_selection
  pytest tests/test_document_processing.py -k chunk
  ```
  (Adjust `-k` names to match implemented test node IDs; add `test_document_processing.py` if created per tasks.)

- **Offline eval (coverage gate):** Run entrypoint documented in `backend/evals/rewrite_cv/` (module docstring or package `__main__` per implementation), e.g.:
  ```bash
  cd backend && DSPY_MODE=mock python -m evals.rewrite_cv  # example; follow shipped CLI
  ```
- **Optional LLM-judge pass:** `DSPY_MODE=openai` plus API key; not part of default CI.

## Output Artifacts

- `01-ba-analysis.md`
- `02-product-spec.md`
- `03-qa-plan.md`

---

> Human checkpoint: review `03-qa-plan.md`, then run `/feature-tasks` to continue.
