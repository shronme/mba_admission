# Product Specification: Full-Document Retrieval for Generation Tasks (RAG)

## Status
COMPLETE

## Overview
This feature fixes **generation-over-completeness** tasks (especially CV rewrite and life-story–grounded drafting) by giving the advisor **full source text** from `uploaded_files.extra["extracted_text"]` instead of relying only on semantic top-k chunks that can omit structure and tail content. It adds **strict two-way intent detection** on the user message: on a **clear rewrite/redraft match**, chat **replaces** the usual semantic preload with tagged full-document blocks (CV + life story when present); otherwise behavior stays **unchanged** (semantic search via `search_async` in `backend/app/api/routes/chat.py::_retrieve_doc_snippets`, default `top_k=6` in `backend/app/core/vector_store.py::search_async`). Ingestion is updated **forward-only**: raise the stored `extracted_text` cap to **200k** characters, chunk with **`langchain-text-splitters`** (tiktoken encoder aligned with `text-embedding-3-small` / `cl100k_base`), **600** tokens per chunk and **50** overlap, and raise the chunk ceiling to **200** — **only for new or reprocessed uploads** (`backend/app/workers/tasks/document_processing.py::_extract_text` today uses `[:20_000]` and `[:25]`). New agent tools **`get_full_document`** and **`rewrite_cv`** live in `backend/app/dspy/agent_tools.py::build_agent_tools`; `AgentAdvisorSignature` and ReAct tool lists in `backend/app/dspy/agent_advisor.py` and wiring in `backend/app/dspy/pipeline.py` (currently `retrieve_fn, save_fn = build_agent_tools(...)`) are updated accordingly. Offline quality for `rewrite_cv` is gated under `backend/evals/rewrite_cv/` per D4.

## User stories
- **As a candidate**, when I ask to rewrite or polish my CV, the advisor uses my **complete** latest CV (and life story if I uploaded one) so roles, dates, and education are not dropped or invented.
- **As a candidate**, when I want an essay grounded in my life story, I can ask in natural language; on **clear** rewrite/redraft intent the model receives **full** CV and life-story text in preload, and can use **`get_full_document`** when it needs a full doc on demand.
- **As a candidate**, when I ask summary or factual questions ("summarize my leadership", "what did I say about X?"), behavior stays **semantic top-k** — no regression vs `retrieve_candidate_context` (`backend/app/dspy/agent_tools.py`, `top_k=8`) and chat preload.
- **As a candidate**, when I upload a **long** life story, new processing stores up to **200k** characters and embeds more chunks so search coverage improves; I understand old uploads are **not** backfilled automatically.
- **As a candidate**, when the agent runs **`rewrite_cv`**, I still get a **downloadable CV draft** in chat (`ArtifactDownloadCard`) because the tool **always** persists via `save_artifact` (`backend/app/dspy/agent_tools.py::save_artifact` / `CVDraftRepository`).

## Goals & Success Metrics
- **Goal:** Factual fidelity and trust on rewrite/draft tasks; no regression on Q&A-style turns.
- **Metric:** Meets acceptance criteria below (preservation, regression, long docs, tool selection via integration tests, Q&A latency, `rewrite_cv` eval gates).

## Functional Requirements

### FR-1: Clear rewrite intent — regex (two-way branch only)
- **Description:** Classify the raw user message with a **single strict regex** (case-insensitive). **Clear match** iff the pattern matches. **No** borderline/augment mode in v1.
- **Pinned pattern (Python, `(?i)`):** verb and document phrase within **at most six whitespace-separated tokens** of each other (count **words**, not characters), in **either order**:
  - **Verbs:** `rewrite`, `revise`, `redo`, `polish`, `improve`, `edit`, `redraft`, `rework`
  - **Document phrases:** `cv`, `resume`, `résumé`, `essay`, `life story` (two words), `statement of purpose` (three words), or `SOP` as a whole word (`\bSOP\b`).
- **Regex (authoritative):**

```python
_REWRITE_INTENT_RE = re.compile(
    r"(?i)(?:(?:\b(?:rewrite|revise|redo|polish|improve|edit|redraft|rework)\b"
    r"(?:\s+\S+){0,6}\s+"
    r"(?:cv|resume|résumé|essay|life\s+story|statement\s+of\s+purpose|\bSOP\b))"
    r"|(?:cv|resume|résumé|essay|life\s+story|statement\s+of\s+purpose|\bSOP\b)"
    r"(?:\s+\S+){0,6}\s+"
    r"\b(?:rewrite|revise|redo|polish|improve|edit|redraft|rework)\b))"
)
```

- **Acceptance Criteria:**
  - [ ] **Clear match** → preload path in FR-4 (full CV + life story if present) **replaces** semantic `search_async` preload for that turn (see `backend/app/api/routes/chat.py::_retrieve_doc_snippets`).
  - [ ] **No match** → current behavior: embed user message, `search_async` with default `top_k`, unchanged contract.
  - [ ] Unit tests cover true/false examples (including near-misses outside the 6-token window).

### FR-2: `get_full_document(document_type)` tool
- **Description:** Async tool on the advisor ReAct loop; reads latest stored full text per D5.
- **Signature:** `async def get_full_document(document_type: str) -> str`
- **Validation (strict):** Accept **exactly** `cv`, `life_story`, `recommendation_letter`, `grade_sheet` (mirror `DocumentType` in `backend/app/db/enums.py`; **not** `irrelevant` / `unclassified`).
- **Return strings (exact):**
  - Invalid type: `Unsupported document_type '<x>'. Valid: cv, life_story, recommendation_letter, grade_sheet.` (replace `<x>` with the caller's argument verbatim).
  - Valid type, no usable document: `No document of type '<x>' uploaded for this candidate.`
  - Success: implementation-defined wrapping may include filename/metadata if helpful, but must include the **full** `extracted_text` body for the latest file.
- **Data access:** `UploadedFileRepository.get_latest_full_text_by_document_type(candidate_id, document_type) -> FullDoc | None` (`backend/app/repositories/uploaded_file_repository.py`); **no** raw ORM in route/tool layers beyond the repository.
- **Latest-only:** Single `UploadedFile` row: `ORDER BY created_at DESC LIMIT 1` among rows matching `candidate_id` and `document_type`; **never** concatenate multiple files of the same type; **no** disambiguator parameter in v1.
- **Acceptance Criteria:**
  - [ ] Tool registered from `build_agent_tools`; `candidate_id` injected in closure (same pattern as `retrieve_candidate_context`).
  - [ ] Repository returns `None` when no row or empty/missing `extracted_text` → "no document" string.

### FR-3: `rewrite_cv` tool
- **Description:** DSPy-backed CV rewrite exposed as a ReAct tool; loads context and **always** persists a draft.
- **Signature:** `async def rewrite_cv(target_school: str = "", emphasis: str = "") -> str`
  - Both arguments optional: empty `target_school` → school-agnostic rewrite; empty `emphasis` → no emphasis hint.
- **Inputs (loaded inside tool wrapper; `candidate_id` injected):**
  - **CV** full text (latest by `document_type=cv`): **required**. If missing → return explicit error string, e.g. `Cannot rewrite CV: no CV document with extracted text is available for this candidate.`
  - **Life story** full text (latest): use if present; omit if absent.
  - **Candidate profile JSON:** use if populated (same source as advisor profile fields).
  - **Target school dossier:** if `target_school` is non-empty **and** a matching dossier exists in `knowledge_chunks`, load it; otherwise **skip silently**. General advisor wiring of `knowledge_chunks` remains out of scope except for this narrow use.
- **Output and side effects:** Return the **rewritten CV text** (body string suitable for chat). **Internally** call `save_artifact` with `artifact_type="cv_draft"` (title/metadata per existing conventions) so the draft appears in **`cv_drafts`** and the UI download flow unchanged.
- **Acceptance Criteria:**
  - [ ] Module implemented (e.g. `backend/app/dspy/rewrite_cv.py`) and invoked from the tool.
  - [ ] Successful run returns rewritten text **and** creates a CV draft row.
  - [ ] Missing CV returns the explicit error string and does **not** call `save_artifact`.

### FR-4: Preload behavior (`_retrieve_doc_snippets` + `pipeline.py`)
- **Description:** When FR-1 **matches**, **do not** call `search_async` for preload. Instead build `preloaded_document_snippets` content from **latest** full `extracted_text` for **CV** and, if present, **life story** only (not profile JSON). **Replace** semantic snippets for that turn (no top-k augmentation in v1).
- **Tag format (exact text per block):**
  - CV: `[CV — full text]\n<text>\n[End CV]`
  - Life story: `[Life story — full text]\n<text>\n[End Life story]`
- **When FR-1 does not match:** Keep today's semantic path (`AsyncOpenAI` embed + `search_async`) and existing fallback without API key (naive `extracted_text` from up to three files in `chat.py`).
- **`pipeline.py` joining:** Today `docs_snippets` are joined as `[{i+1}] {snippet}` (`backend/app/dspy/pipeline.py` ~263–266). For **full-document preload**, join tagged blocks with `\n\n` **without** numeric prefixes so the model sees exactly the tag format above. Semantic top-k path may keep numbered chunks for parity with existing behavior (implementation: branch on preload mode or detect tagged full-doc list).
- **Acceptance Criteria:**
  - [ ] Clear intent + CV uploaded → model input contains full CV block; life story block only if file exists.
  - [ ] No match → unchanged semantic preload; Q&A flows unaffected.

### FR-5: Ingestion (`document_processing.py`)
- **Description:** Forward-only ingestion changes for **new/reprocessed** documents only; **no** backfill job.
- **Constants:** `extracted_text` stored up to **200_000** characters (classifier cap `_CLASSIFY_MAX_CHARS = 4000` unchanged in `document_processing.py`).
- **Chunker:** `langchain_text_splitters.RecursiveCharacterTextSplitter.from_tiktoken_encoder` with encoder name compatible with **`text-embedding-3-small`** / **`cl100k_base`**; **chunk_size=600** tokens, **chunk_overlap=50** tokens.
- **Chunk list cap:** Raise from **25** to **200** chunks per file (safety ceiling).
- **Dependencies:** Add `langchain-text-splitters` to `backend/` dependencies; `tiktoken` is already in `backend/requirements.txt` (verify version at task time). Accept transitive `langchain-core` if required by the package resolver.
- **Acceptance Criteria:**
  - [ ] Re-upload or reprocess applies new caps and chunking; existing `document_chunks` rows unchanged until reprocessed.
  - [ ] Tests cover chunk count bound and long text preservation (where practical).

### FR-6: `AgentAdvisorSignature` and ReAct tools
- **Description:** Update `backend/app/dspy/agent_advisor.py` class docstring / rules to describe:
  - `get_full_document` vs `retrieve_candidate_context` vs `rewrite_cv`.
  - **Explicit rule:** For rewrite/redraft of a **specific uploaded document**, prefer full text — either already in `preloaded_document_snippets` (tagged full blocks) or via `get_full_document`; **do not** rely on `retrieve_candidate_context` alone for those tasks.
  - **Existing rule retained:** Read `preloaded_document_snippets` first.
- **Tool registration:** `AgentAdvisorModule` / `MockAgentAdvisorModule` include **`retrieve_candidate_context`**, **`save_artifact`**, **`get_full_document`**, **`rewrite_cv`** (adjust `max_iters` if needed so trajectories can complete).
- **`build_agent_tools` return type:** Four callables, in this order:
  `(retrieve_candidate_context, save_artifact, get_full_document, rewrite_cv)`
  Update all unpack sites (e.g. `backend/app/dspy/pipeline.py` currently assigns two; tests in `backend/tests/test_agent_advisor_unit.py` that unpack `build_agent_tools`).

### FR-7: Offline evaluation — `rewrite_cv` (D4)
- **Description:** New eval package `backend/evals/rewrite_cv/` following patterns in `backend/evals/run_evals.py`, `metrics.py`, and existing evaluators/datasets.
- **Fixtures:** ~5 hand-crafted synthetic CVs under `backend/evals/fixtures/cv/` (varied length, sections, non-English names, gaps, multi-role company). **No** gold rewrites; **no** real PII or secrets.
- **Coverage pass (deterministic, CI-friendly):** For each fixture source `extracted_text`, assert **≥95%** of extracted roles, companies, date ranges, and education entries appear in the rewrite (**fuzzy** string match rules defined in eval code).
- **Hallucination pass (LLM judge):** Flags facts in rewrite not grounded in source; runs **only** when `DSPY_MODE=openai`, **not** default CI.
- **Acceptance Criteria:**
  - [ ] Eval entry point documented in package README or module docstring (no new top-level markdown file required if inconsistent with repo — use minimal inline doc in eval module per team norm).
  - [ ] Coverage gate enforced in CI; hallucination optional/manual or nightly per env.

### FR-8: Tool-selection quality (success criterion #4)
- **Description:** **≥95%** selection of `get_full_document` (or equivalent "full doc used") for rewrite-class tasks is validated via **deterministic integration tests** in `backend/tests/test_agent_advisor_integration.py` with **mocked** tool calls / trajectory — **not** a live-trajectory LLM eval in this feature.
- **Acceptance Criteria:**
  - [ ] Seeded prompts cover rewrite-class vs non-rewrite cases; assertion on tool choice or preload path as designed.

## Non-Functional Requirements
- **Performance / latency:** For **Q&A-class** user turns (no FR-1 match), end-to-end streaming must show **no material regression** vs baseline: preload remains embedding + `search_async` (same `top_k` defaults); no extra full-document DB reads on those turns.
- **Determinism:** Unit and integration tests run with **`DSPY_MODE=mock`** where applicable; no live OpenAI requirement for default CI.
- **Security / data:** Eval fixtures are synthetic; no production or personal data.
- **Forward-only data:** No migration or job to re-embed historical files; behavior change applies when documents are **newly processed or reprocessed** only.
- **No per-turn token budget** on preload beyond the **200k** character source-of-truth cap (per product decision).

## User Flows / API Contracts

### Flow 1: User asks to rewrite CV (happy path)
1. User uploads CV (processed → `extracted_text` + chunks).
2. User message matches FR-1 (e.g. "Please rewrite my CV").
3. `chat.py::_retrieve_doc_snippets` returns full CV (and life story if any) as tagged blocks; semantic search skipped for preload.
4. `pipeline.py` passes tagged text into `preloaded_document_snippets`.
5. Advisor may answer from preload and/or call `rewrite_cv` / `get_full_document` as needed.
6. If `rewrite_cv` runs → response text + artifact persisted → **ArtifactDownloadCard** shows download.

### Flow 2: User asks a semantic / Q&A question (no regression)
1. User message does **not** match FR-1.
2. Preload: embed message, `search_async` (`top_k=6`), same as today.
3. Advisor uses snippets and/or `retrieve_candidate_context` (`top_k=8`) as today.

### Flow 3: No CV uploaded yet
1. User asks to rewrite CV (FR-1 match); preload may include only life story or empty CV block depending on uploads.
2. If agent calls `rewrite_cv` → tool returns **`Cannot rewrite CV: no CV document with extracted text is available for this candidate.`** (or preload makes missing CV obvious); **no** `save_artifact` for CV draft.

### Flow 4: User uploads a new CV then asks to rewrite
1. New `UploadedFile` row with newer `created_at` and `document_type=cv`.
2. `get_full_document("cv")` and preload always use **latest** row only; rewrite uses new content automatically.

## API contract (consolidated)

**Repository (`backend/app/repositories/uploaded_file_repository.py`):**
```python
@dataclass(frozen=True)
class FullDoc:
    filename: str
    document_type: str  # DocumentType value
    text: str
    created_at: datetime  # timezone-aware as stored by ORM

async def get_latest_full_text_by_document_type(
    self,
    candidate_id: UUID,
    document_type: str,
) -> FullDoc | None: ...
```

**`build_agent_tools` (`backend/app/dspy/agent_tools.py`):**
```python
def build_agent_tools(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    openai_client: Any,
) -> tuple[
    Callable[[str], Awaitable[str]],  # retrieve_candidate_context
    Callable[[str, str, str, str | None], Awaitable[str]],  # save_artifact
    Callable[[str], Awaitable[str]],  # get_full_document
    Callable[..., Awaitable[str]],  # rewrite_cv(target_school="", emphasis="")
]:
```

**`get_full_document` errors (exact):**
- `Unsupported document_type '<x>'. Valid: cv, life_story, recommendation_letter, grade_sheet.`
- `No document of type '<x>' uploaded for this candidate.`

**`rewrite_cv` missing CV (example exact):**
- `Cannot rewrite CV: no CV document with extracted text is available for this candidate.`

**Preload tags (exact):** as in FR-4.

## Data model changes
**None** at the schema level: no new tables or columns. Limits (**200k** text, **200** chunks, chunker settings) are **code constants** in `document_processing.py` and related modules. Existing rows unchanged until reprocessing. **No Alembic migration** is required for this feature (per repository rule: do not hand-author migrations).

## Out of scope
- Retroactive backfill or bulk re-embedding of existing uploads.
- Concatenating multiple files of the same `document_type` for `get_full_document`.
- Borderline / hybrid preload (full doc **plus** semantic top-k) in v1.
- Cross-candidate search; BM25/hybrid retrieval; reranking.
- Normalized CV schema extraction.
- General wiring of program dossiers (`knowledge_chunks`) into advisor retrieval (except **narrow** dossier lookup for `rewrite_cv` when `target_school` is set).
- Live LLM trajectory eval for tool selection (deferred); replaced by integration tests per FR-8.
- Frontend changes (`apps/web/`); existing artifact download UX only.
- Per-turn preload token budget beyond the 200k source cap.

## Open Questions
None. Resolved by D1–D5 and this spec.

## Dependencies (from BA + spec)
- **New:** `langchain-text-splitters` (and any required transitive deps, e.g. `langchain-core`).
- **Existing:** `tiktoken` (`backend/requirements.txt`), OpenAI embeddings (`text-embedding-3-small`), DSPy advisor stack, `UploadedFile` / `DocumentChunk` / `DocumentType`, `app.core.vector_store`, `CVDraftRepository`, chat streaming (`backend/app/api/routes/chat.py`).

## Acceptance criteria / success metrics (aligned with BA)
1. **Preservation:** CV rewrite output is checkable against source `extracted_text`; offline **coverage** eval **≥95%** on structured fields (FR-7).
2. **Regression:** Leadership/summary-style Q&A still driven by semantic retrieval; integration tests guard behavior.
3. **Long life stories:** New processing retains up to **200k** chars in `extracted_text`; chunking improves embed coverage (FR-5).
4. **Tool selection:** **≥95%** on seeded rewrite-class cases via **mocked** integration tests in `backend/tests/test_agent_advisor_integration.py` (FR-8); live trajectory eval **out of scope**.
5. **Latency:** No material regression for **non-matching** Q&A turns (NFR above).
6. **Module quality:** Hallucination judge in **`DSPY_MODE=openai`** only; coverage gate in CI (FR-7).

## Implementation touchpoints (for task-writer)
- `backend/app/api/routes/chat.py::_retrieve_doc_snippets` — intent branch, full-doc preload vs `search_async`.
- `backend/app/core/vector_store.py::search_async` — default `top_k=6` (unchanged contract).
- `backend/app/dspy/pipeline.py` — unpack **four** tools; conditional formatting of `preloaded_snippets_text`.
- `backend/app/dspy/agent_tools.py::build_agent_tools` — new tools + return arity.
- `backend/app/dspy/agent_advisor.py` — `AgentAdvisorSignature`, `AgentAdvisorModule`, `MockAgentAdvisorModule`.
- `backend/app/workers/tasks/document_processing.py` — `_extract_text`, chunking, caps; `_CLASSIFY_MAX_CHARS` unchanged.
- `backend/app/repositories/uploaded_file_repository.py` — **new** repository module.
- `backend/tests/test_agent_advisor_integration.py`, `backend/tests/test_agent_advisor_unit.py` — unpack and behavior updates.
- `backend/evals/rewrite_cv/`, `backend/evals/fixtures/cv/` — new eval and fixtures.

## Output Artifacts
- `01-ba-analysis.md`
- `02-product-spec.md`

> Human checkpoint: review `02-product-spec.md`, then run `/feature-qa` to continue.
