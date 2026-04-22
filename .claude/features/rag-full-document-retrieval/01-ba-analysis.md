# BA Analysis: Full-Document Retrieval for Generation Tasks (RAG)

## Status

COMPLETE

## Feature Request Summary

Introduce **full-document retrieval** and **intent-aware preloading** so the advisor can run **generation-over-completeness** tasks (CV rewrite, life-story–grounded drafting) using the candidate's complete source text from `uploaded_files.extra.extracted_text`, instead of relying only on semantic top-k chunks that optimize recall and drop structure. Complement this with **removing silent truncation** and a **token-aware chunking strategy** for embeddings (forward-only; no backfill), **prompt/tooling guidance** so the ReAct agent prefers full documents for rewrite-class work, and an in-scope **`rewrite_cv` DSPy module** exposed as a ReAct tool (`rewrite_cv(target_school, emphasis)`) with **offline evaluation** under `backend/evals/`.

**Authoritative scope decisions (user):** All five workstreams are in scope. Intent preload follows **option (c)**: on **clear** rewrite/redraft intent, **replace** semantic top-k with full-document dumps; on **borderline** matches, **augment** with full doc **plus** top-k snippets. `get_full_document(document_type)` returns **only the latest file per type** (by upload / `created_at`), with **no** concatenation or disambiguator. **No** separate per-turn preload token budget beyond relying on a raised ~200k-char source-of-truth cap. Chunker implementation choice is **deferred** to PM/tasks; **no retroactive backfill** of `document_chunks` or reprocessing of historical extractions unless the file is re-uploaded or reprocessed.

---

## Problem Statement & User Impact

- **Problem:** Today's pipeline stores full extracted text but the advisor path primarily injects **semantic search results** (chat preload: default top_k=6 in `search_async`; agent tool: top_k=8). Chunking uses **paragraph splits with a 20k character cap and max 25 chunks** (`document_processing._extract_text`), so long life stories are silently truncated and RAG coverage is incomplete.
- **User impact:** For "rewrite my CV" and similar tasks, the model may **omit roles, scramble order, or invent facts** because it never sees the full source. Quality loss dominates token cost; fixing retrieval improves **factual fidelity and trust** in generated artifacts.

---

## Codebase Findings

### Current-State Summary (verified / cited paths)

| Area | Behavior |
|------|----------|
| **Chunking** | `backend/app/workers/tasks/document_processing.py` — `_extract_text` uses `cleaned = extracted.strip()[:20_000]` and `chunks = ...[:25]` from `"\n\n"` splits. |
| **Embedding storage** | Chunks upserted via `app.core.vector_store.upsert_chunks_sync`; search is cosine order, candidate-scoped. |
| **Retrieval** | `backend/app/core/vector_store.py::search_async` — `ORDER BY` embedding distance, `top_k` default **6**. |
| **Chat preload** | `backend/app/api/routes/chat.py::_retrieve_doc_snippets` — embeds user message, `search_async` when `OPENAI_API_KEY` set; else naive `extracted_text` from up to 3 files. |
| **Agent tools** | `backend/app/dspy/agent_tools.py::build_agent_tools` returns **`retrieve_candidate_context`** (top_k=8) and **`save_artifact`** only — no full-document tool yet. |
| **Advisor** | `backend/app/dspy/agent_advisor.py` (`AgentAdvisorSignature`) documents `preloaded_document_snippets` + `retrieve_candidate_context`. |
| **Pipeline** | `backend/app/dspy/pipeline.py` — advisor stage calls `build_agent_tools`, passes `docs_snippets` into `preloaded_document_snippets`. |

**Gap:** No repository abstraction today for "latest full text by `document_type`"; file access is via models (`UploadedFile` on `candidate.uploaded_files`) and inline queries in chat. Implementers should follow the repo rule: **data access via repositories**, not raw SQL in routes/tools.

### Files Likely Requiring Changes

**Core RAG & ingestion**

- `backend/app/workers/tasks/document_processing.py` — Raise effective cap on stored `extracted_text` (~200k); replace paragraph/`[:25]` chunk pipeline with **token-aware** splitter + overlap; relax or remove 25-chunk ceiling appropriately. **Applies only to new/reprocessed runs** (no bulk backfill).
- `backend/app/core/vector_store.py` — Possibly unchanged behavior contract; may need typing/metadata later (out of scope per FR unless required for debugging).

**API & advisor**

- `backend/app/api/routes/chat.py` — `_retrieve_doc_snippets`: **intent branch** (clear → full-doc preload replacing semantic; borderline → full + top-k; default → semantic only). Label full-text sections (e.g. `[CV — full text]`). Respect "latest per type" when selecting which file's `extracted_text` to inject.
- `backend/app/dspy/agent_tools.py` — Add **`get_full_document(document_type)`**; extend `build_agent_tools` to register **`rewrite_cv`** tool; return tuple arity updates (callers must unpack).
- `backend/app/dspy/agent_advisor.py` — Update `AgentAdvisorSignature` instructions: when to use full doc vs semantic retrieval; **mandate `get_full_document` for rewrite/redraft** on specific documents; document new tools.
- `backend/app/dspy/pipeline.py` — Wire new tools into `AgentAdvisorModule` / mock; pass any extra context if needed for `rewrite_cv`.

**New / extended data access**

- New module such as `backend/app/repositories/uploaded_file_repository.py` (name TBD) **or** methods on an existing repository — **`get_latest_full_text_by_document_type(candidate_id, document_type)`** (and helpers as needed). *The feature request referenced `files_repository.py`; the codebase currently has no file named that — implementation should add a dedicated repository per convention.*

**Dedicated CV rewrite module & evals**

- `backend/app/dspy/rewrite_cv.py` (or similarly named) — DSPy `Module` + signature: inputs to include full CV (and optionally life story, profile JSON, target school dossier from `knowledge_chunks` where available), `target_school`, `emphasis`; output is rewrite body suitable for `save_artifact` or return to the tool wrapper.
- `backend/evals/` — New eval entry points / fixtures for **`rewrite_cv`** (e.g. gold CV pairs, `DSPY_MODE=mock` harness), consistent with existing `evals/` patterns.

**Tests**

- `backend/tests/test_agent_advisor_integration.py`, `backend/tests/test_agent_advisor_unit.py` — Full-document tool, intent routing on preload, trajectory tests for `rewrite_cv` tool, regression on semantic Q&A.
- Additional tests for document processing / chunk count bounds if behavior changes warrant.

**Frontend**

- None expected (artifacts still surfaced via existing download flow per FR).

### Existing Capabilities Relevant to This Feature

- **Semantic retrieval:** `search_async` + `retrieve_candidate_context` for recall-oriented Q&A — **retain** for non-rewrite tasks.
- **Artifacts:** `save_artifact` + `CVDraftRepository` / `EssayDraftRepository` — reuse for persisting CV draft output from `rewrite_cv` or advisor.
- **Source of truth:** `uploaded_files.extra["extracted_text"]` already populated in `process_uploaded_document`.
- **Advisor ReAct:** `AgentAdvisorModule` with trajectory length limits — new tools participate in same loop.
- **Mock path:** `MockAgentAdvisorModule` — extend so tests cover new tools without live LLM.

### New Capabilities Required

1. **Repository-level** "latest document by type" query over `UploadedFile` + `document_type` + timestamp.
2. **Agent tool** `get_full_document` with stable "missing document" messaging.
3. **Intent-aware preload** in chat (three-way: replace / augment / semantic-only) driven by regex/heuristics with **PM-defined "clear vs borderline"** rules.
4. **Ingestion changes** for uncapped (within ~200k) stored text and **token-aware** chunks for new processing only.
5. **`rewrite_cv` DSPy module** + ReAct tool wrapper + **`backend/evals/`** coverage.

### Proposed Solution — Five Workstreams

| # | Workstream | User-facing implication | Technical implication |
|---|------------|-------------------------|------------------------|
| **1** | `get_full_document(document_type)` | Advisor can fetch the **entire** latest CV, life story, recommendation letter, or grade sheet on demand, with consistent labeling. | New async repository method; tool in `agent_tools.py`; returns tagged full text or explicit not-found string; **one row per type — latest by `created_at`**. |
| **2** | Intent-aware preload | For obvious "rewrite my CV" messages, the **first** model turn already includes full CV/life story — fewer tool calls, better answers. | Extend `_retrieve_doc_snippets`: **clear** regex → full-doc **replaces** semantic preload; **borderline** → full doc **+** top-k; **no match** → current behavior. **No extra token budget layer** beyond ~200k stored text cap. |
| **3** | Truncation + chunking | Long uploads are **fully preserved** in `extracted_text`; semantic search **covers** long documents better (more/smarter chunks). | Remove 20k silence on stored text for new runs; token-targeted chunks (~400–600 tokens, ~50 overlap); chunk count limit revisited; **no DB migration for old chunk rows**. |
| **4** | Advisor prompt update | Users see fewer hallucinations on redrafts because the model is **instructed** to use full documents for those tasks. | Update `AgentAdvisorSignature` docstring / instructions; register new tools in module construction. |
| **5** | `rewrite_cv` module + eval | CV rewrites can be **evaluated and iterated** independently; optional emphasis and school-aware behavior. | New DSPy module file; tool `rewrite_cv(target_school, emphasis)` loads data, runs module, may call `save_artifact`; gold-set / metric **TBD in PM spec** (see risks). |

### Success Criteria (lifted from FR, sharpened)

From the feature request:

1. **Preservation:** "Rewrite my CV" produces an artifact **verifiable** against stored `extracted_text` (every role, date, section retained unless user asked otherwise).
2. **Regression:** Leadership / summary-style questions still use semantic retrieval effectively.
3. **Long life stories:** Text **> 20k chars** fully stored and usable post-change (new processing).
4. **Tool selection:** Agent chooses `get_full_document` for rewrite-class tasks in **≥95%** of ~20 seeded offline prompts (per FR).
5. **Latency:** No material increase in end-to-end stream time for **Q&A-class** turns (preload stays semantic).

**Additional (in-scope `rewrite_cv`):**

6. **Module quality (measurable, PM to finalize metric):** e.g. composite of (a) **structured section coverage** vs source (automated checklist), (b) **contradiction rate** against source fields (automated spot checks), (c) optional **semantic similarity band** to a **gold rewrite** where gold exists, or human rubric in pilot. At minimum the spec should require a **defined eval dataset location** under `backend/evals/` and pass/fail gates for CI or manual release checks.

### Scope Boundaries

**In scope:** All five workstreams above; latest-only semantics for `get_full_document`; replace/augment preload semantics; ~200k source cap; forward-only chunking; `rewrite_cv` tool + eval surface.

**Out of scope (from FR, unchanged):** Cross-candidate search; normalized CV schema extraction; BM25/hybrid + reranking; general wiring of `knowledge_chunks` into advisor retrieval (except as **inputs** to `rewrite_cv` where already available or minimally loaded — PM to clarify).

**Explicitly not in scope (user clarifications):** Per-turn preload budget; retroactive re-embedding of existing uploads; concatenating multiple files of the same type in `get_full_document`.

---

## Dependencies

**External**

- OpenAI (or configured provider) for embeddings (`text-embedding-3-small`) and advisor/rewrite LLM calls — unchanged pattern.
- Optional: tokenizer library **TBD** (`tiktoken`, LangChain splitter, etc.) for chunking — product/eng choice.

**Internal**

- `UploadedFile`, `DocumentChunk`, `DocumentType` enums and existing upload pipeline.
- `app.core.vector_store` search/upsert.
- `CVDraftRepository`, artifact routes for download UX.
- DSPy module patterns in `app/dspy/` and `evals/` conventions.

---

## Risks & Constraints

- **Clear vs borderline intent:** Regex v1 will misfire; product must define **criteria** (e.g. strict multi-token regex = clear, loose keywords = borderline) and acceptance tests. Future DSPy classifier noted in FR as iteration.
- **"Latest only" per type:** If users upload a **new** CV without deleting the old, behavior is **correct by spec** but may surprise users who expected an older letter — document in UX/help if needed (out of band for this BA).
- **Chunker library selection:** Affects dependencies and determinism; defer to PM/tasks; must stay compatible with **sync worker** context in `document_processing`.
- **`rewrite_cv` eval gold sourcing:** Curated before/after pairs, rubric, or synthetic checks — **needs PM decision** on dataset ownership and CI gating.
- **Tool surface growth:** More tools may increase wrong-tool calls; mitigated by prompt rules + offline evals for trajectory.
- **No backfill:** Existing candidates' vector indices stay **stale** until re-upload; acceptable per decision but may confuse testers comparing old vs new accounts.

---

## Recommended Next Step

Hand off to the **Product Manager** to produce a specification that: (1) locks **clear vs borderline** preload rules and labels, (2) selects **chunking approach**, (3) defines **rewrite_cv** eval metrics and gold-set plan, and (4) aligns API/tool signatures (`build_agent_tools` return shape, `pipeline` wiring) for the **task-writer** phase.

---

## Output Artifacts

- `01-ba-analysis.md` ✅
