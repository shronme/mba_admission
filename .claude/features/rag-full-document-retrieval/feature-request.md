# Feature Request: Full-Document Retrieval for Generation Tasks

## Problem

The current candidate-document RAG pipeline is optimized for **recall** (find the most relevant passages for a question), but many advisor tasks are **generation-over-completeness** tasks where the model needs the entire source document — verbatim, in order, with nothing dropped.

The most obvious failure case is **CV rewriting**. Today, when a candidate asks the advisor to rewrite their CV, the agent receives only top-k semantically similar chunks (8 at most), plus 6 pre-fetched snippets. The LLM is therefore rewriting a CV it has never fully seen. It will hallucinate missing sections, drop roles, lose chronology, and invent dates. The same problem applies to essay drafting when the candidate wants their life story preserved, and to any task where document integrity matters.

## Current Behavior (as of this request)

### Chunking (`backend/app/workers/tasks/document_processing.py`)
- Text is extracted (via `gpt-4o` for LLM path, `pypdf`/regex for fallback) and stored on `uploaded_files.extra.extracted_text`.
- Chunking is a single line:
  ```python
  cleaned = extracted.strip()[:20_000]
  chunks = [c.strip() for c in cleaned.split("\n\n") if c.strip()][:25]
  ```
- So: **paragraph-split on blank lines, capped at 25 chunks per document, underlying text capped at 20,000 chars**. No token awareness, no overlap, no sliding window.
- Chunks are embedded with `text-embedding-3-small` and upserted into `document_chunks` (pgvector, HNSW cosine).

### Retrieval (`backend/app/core/vector_store.py::search_async`)
- Straight `ORDER BY embedding <=> query_embedding LIMIT k`.
- Candidate-scoped via `candidate_id`. No `document_type` filter. No reranking. Returns only `text` strings (no source attribution).

### Invocation paths
1. **Pre-retrieval in the chat route** (`backend/app/api/routes/chat.py::_retrieve_doc_snippets`): embeds the raw user message, pulls top-6 chunks, passes them to the advisor as `preloaded_document_snippets`. Fallback with no `OPENAI_API_KEY`: dumps `extra.extracted_text` from up to 3 files.
2. **Agent tool `retrieve_candidate_context`** (`backend/app/dspy/agent_tools.py`): same embed + `search_async` at top-k=8. The ReAct agent is capped at `max_iters=4` and instructed to call it at most once per turn.

### Why this breaks CV rewriting
- The agent receives maybe 6–8 paragraphs out of ~10–15 in a typical CV. Any section whose paragraph didn't semantically match the user's message (e.g. "rewrite my CV") is invisible to the model.
- Because chunks are stripped of source/order metadata, the model can't reconstruct document structure even from what it does see.
- The 20k-char cap silently truncates long life stories; the 25-chunk cap compounds it.
- Full `extracted_text` **is** stored on `uploaded_files.extra`, but the advisor pipeline never reaches for it.

---

## Proposed Solution

Give the advisor three clearly-named primitives instead of one blunt semantic search, and route to them based on task shape:

| Task shape | Needs | Primitive |
|------------|-------|-----------|
| "Summarize my leadership experience" | Sparse facts, possibly across docs | **Semantic top-k** (keep today's `retrieve_candidate_context`) |
| "Rewrite my CV" / "Draft my HBS essay using my life story" | A whole document, in order, nothing missing | **Full-document fetch** (new) |
| "What GMAT score did I report?" | Precise field lookup | **Structured profile** (already exists) |

### Scope

#### 1. New tool: `get_full_document(document_type)`

- Add to `backend/app/dspy/agent_tools.py` alongside `retrieve_candidate_context`.
- Reads `uploaded_files.extra.extracted_text` for the given candidate + `document_type`.
- Returns the full text, tagged with filename and doc type; if multiple files of the same type exist, concatenate with clear separators.
- Returns a well-defined "no document of that type" string if missing.

Tool signature (indicative):

```python
async def get_full_document(document_type: str) -> str:
    """
    Return the full extracted text of the candidate's document(s) of the
    given type ('cv', 'life_story', 'recommendation_letter', 'grade_sheet').

    Use this whenever you need the complete content (rewriting a CV,
    editing an essay, preserving tone and structure, verifying ordering
    of experiences). Do NOT use this for broad semantic lookups — use
    retrieve_candidate_context for that.
    """
```

Implementation note: respect the "no raw SQL in routes/tools" convention — add `FileRepository.get_full_text_by_type(candidate_id, document_type) -> list[FullDoc]` and call it from the tool.

#### 2. Intent-aware preloading in the chat route

Replace the unconditional top-k preload in `_retrieve_doc_snippets` with a cheap branch:

- If the user message clearly signals a full-document task (regex v1: `(rewrite|revise|redo|polish|improve|edit) .* (cv|resume|résumé|essay)`), preload the full `extracted_text` of the relevant documents (CV, and life story if present) instead of semantic chunks. Label them `[CV — full text]` / `[Life story — full text]` in `preloaded_document_snippets`.
- Otherwise: current semantic-top-k preload.

Consequence: for the common CV-rewrite case the agent already has the full document in its opening context and does not need to call any tool at all.

A future iteration can replace the regex with a small DSPy intent classifier if the heuristic proves brittle.

#### 3. Remove silent truncation on the source-of-truth text

This is a latent bug independent of the above:

- `cleaned = extracted.strip()[:20_000]` — a detailed life story can easily exceed this and the tail is lost forever.
- `[:25]` chunk cap compounds with paragraph-level splitting.

Changes:

- Store the **untruncated** extracted text as the source of truth (raise the cap to e.g. 200k chars, or move it to a dedicated column / blob). Only the classifier's input should be truncated (`_CLASSIFY_MAX_CHARS = 4000` is already separate — fine).
- For chunks used by semantic search, switch to a token-aware splitter (target ~400–600 tokens per chunk with ~50-token overlap). This improves recall on long docs independently of the new full-document tool.
- Drop the 25-chunk hard cap or raise it sufficiently (e.g. 200) for long life stories.

#### 4. Advisor prompt update

Update `AgentAdvisorSignature` in `backend/app/dspy/agent_advisor.py`:

- Describe both tools and when to pick each.
- Explicit rule: *"For rewrite/redraft tasks on a specific document (CV, life story, essay), call `get_full_document` — do NOT rely on `retrieve_candidate_context` snippets."*
- Keep the existing "read `preloaded_document_snippets` first" rule.

#### 5. (Optional, v2) Dedicated `rewrite_cv` DSPy module

If we want to eval and evolve the CV rewriter independently of the general advisor:

- New DSPy signature/module in `backend/app/dspy/` with inputs: full CV text, life story, profile attributes, target school dossier (from `knowledge_chunks`), emphasis hints.
- The ReAct agent calls it as a tool (`rewrite_cv(target_school, emphasis)`). The tool internally loads the full documents, runs the module, and calls `save_artifact`.
- Gives us a clean offline eval surface (`DSPY_MODE=mock`, gold CVs in `backend/evals/`) and lets us swap prompts/models without touching the advisor.

---

## Out of Scope

- Cross-candidate search.
- Structured CV extraction into a normalized schema (work history rows, education rows, etc.). Worth doing eventually but orthogonal to this feature.
- Hybrid BM25 + vector search and reranking.
- Wiring `knowledge_chunks` (program dossiers) into the advisor's retrieval loop — useful but separate work.

---

## Token-Cost Sanity Check

For a typical MBA candidate:

- CV: ~2–5k tokens
- Life story: ~2–10k tokens
- Profile JSON + selected schools + conversation history: ~2k tokens

Well under 20k tokens total — trivial for `gpt-4o-mini` (128k context) or `gpt-4o` (128k). Dumping full documents is cheap; the real cost of RAG for full-doc tasks is **quality loss**, not tokens saved.

---

## Success Criteria

1. Asking the advisor "rewrite my CV" results in a rewritten artifact that preserves every role, date, and section from the source CV (verifiable against the stored `extracted_text`).
2. Asking "summarize my leadership experience" still works via semantic retrieval (no regression).
3. Life stories longer than 20,000 chars are preserved in full and usable by the advisor.
4. The ReAct agent chooses `get_full_document` for rewrite-class tasks in ≥95% of test cases (measured via an offline eval of ~20 seeded prompts).
5. No increase in end-to-end stream latency for Q&A-class turns (preload remains semantic).

---

## Affected Files (Expected)

**Backend**
- `backend/app/dspy/agent_tools.py` — add `get_full_document`; return tuple of three tools from `build_agent_tools`.
- `backend/app/dspy/agent_advisor.py` — update signature docstring + tool registration.
- `backend/app/dspy/pipeline.py` — pass the new tool through; no other changes expected.
- `backend/app/api/routes/chat.py::_retrieve_doc_snippets` — add intent-aware branch.
- `backend/app/repositories/files_repository.py` (or equivalent) — add `get_full_text_by_type`.
- `backend/app/workers/tasks/document_processing.py` — remove/raise the 20k + 25-chunk caps for the source text; introduce token-aware chunker for embeddings.
- `backend/tests/test_agent_advisor_integration.py`, `test_agent_advisor_unit.py` — new tests for full-doc tool, intent branch, and rewrite-task trajectory.

**Frontend**
- No changes expected. The existing `ArtifactDownloadCard` flow surfaces the saved CV artifact identically.

---

## Open Questions

1. When multiple recommendation letters exist, should `get_full_document("recommendation_letter")` return all concatenated, or require a `filename`/`recommender_name` disambiguator argument?
2. Should the intent-aware preload replace or augment the semantic preload (i.e. include both full doc + top-k snippets when the task is ambiguous)?
3. Do we want a hard per-turn token budget on the preload (to protect against someone uploading a 100-page document)?
4. Should the rewriter be a ReAct tool call or a dedicated `pipeline.py` branch (similar to how the advisor stage is routed)?
