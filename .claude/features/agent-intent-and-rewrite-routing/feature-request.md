# Feature Request: Agent Intent Classification and Rewrite-CV Routing

## Context / What triggered this feature

The preceding feature `rag-full-document-retrieval` shipped three pieces:

- `UploadedFileRepository.get_latest_full_text_by_document_type` (full-text access).
- `get_full_document` and `rewrite_cv` tools on the ReAct advisor.
- A regex-based rewrite-intent pre-fetch (`classify_rewrite_intent`) that replaces semantic RAG with full-document preload on the `/chat/threads/{id}/messages/stream` hot path.

After rollout the user reported two defects on produced CV drafts:

1. **Content loss** — the rewritten CV omits most of the source content (roles, education, dates, awards), even though the full CV is stored and retrievable.
2. **No research-phase feedback reflected** — prior advisor conversation (e.g. "emphasize cross-border transactions", "quantify venture outcomes", "lead with builder-leader story") is NOT reflected in the rewritten CV artifact.

Triage located three root causes that together explain both defects:

1. **Intent classifier is brittle.** The regex only fires on
   `rewrite|revise|redo|polish|improve|edit|redraft|rework` within 6 tokens
   of `cv|resume|résumé|essay|life story|SOP`. Natural phrasings miss
   ("apply those suggestions to my CV", "make it stronger", pronoun
   references, non-English input). On a miss, semantic top-k RAG returns
   only ~5 KB of excerpt chunks — the rewriter never sees the full CV.

2. **Tool routing is soft.** `AgentAdvisorSignature` *prefers* full text
   but does NOT require the advisor to call `rewrite_cv`. The ReAct agent
   can choose to inline-write a CV into `response`, or call `save_artifact`
   directly with its own ad-hoc body. In both cases the hardened
   `RewriteCVSignature` prompt (the single source of truth for CV format
   and completeness) is bypassed.

3. **Rewriter has no feedback channel.** `rewrite_cv(target_school,
   emphasis)` only takes a target school and a free-text `emphasis` hint.
   The prior conversation (advisor commentary / critique) is visible to
   the ReAct agent in `conversation_history` but never flows into the
   rewriter module, so the rewriter can't incorporate that feedback.

## Proposed solution

Replace the regex-based pre-fetch with a proper LLM-driven intent classifier
that is implemented as a ReAct tool. The agent is the first thing to run on
a user turn; its first action is to call the classifier, receive a
structured intent + curated feedback block, and then invoke the matching
rewrite tool. The rewriter receives the feedback block as an additional
input field and is responsible for reflecting it alongside preserving all
source content.

Concretely:

- New DSPy module `OpenAIIntentClassifier` / `MockIntentClassifier` with a
  `ClassifyIntentSignature` producing:
    - `task_kind: str` — one of `rewrite_cv | qa | other` (narrow to CV
      per scope decision below).
    - `target_doc: str` — document the task targets, empty when N/A.
    - `emphasis: str` — short hint derived from the user's latest message
      plus recent advisor turns (one sentence).
    - `prior_feedback: str` — curated bullet list of applicable advisor
      guidance extracted from recent conversation. Empty if none.

- New ReAct tool `classify_intent(user_message, conversation_history)` that
  wraps the module and returns the four fields as a JSON string the agent
  can parse.

- Update `AgentAdvisorSignature` RULES:
    - Always call `classify_intent` as the first tool on every turn.
    - If `task_kind == "rewrite_cv"`, MUST call `rewrite_cv(target_school,
      emphasis, prior_feedback)`. Must NOT emit a CV body in `response`.
      Must NOT call `save_artifact` directly for CV content.
    - Otherwise proceed as today.

- Extend `RewriteCVSignature` with a new input field `prior_feedback: str`
  (default empty) and tighten the docstring so the rewriter reflects the
  feedback in the rewrite *without* losing source content. Keep the strict
  Markdown output contract from the prior feature.

- Extend `rewrite_cv` tool signature in `agent_tools.py` to accept and
  forward `prior_feedback`.

- Delete `app/dspy/intent.py` (regex classifier) and its sole caller,
  `_retrieve_doc_snippets`'s rewrite-intent branch in `chat.py`. Full-
  document preload for rewrite turns is no longer route-level; the agent
  now owns that decision via the classifier tool + `get_full_document`.

- Keep the rest of `rag-full-document-retrieval`'s work (full-doc repo,
  `get_full_document`, chunker changes, `evals/rewrite_cv`, renderer).

## User-confirmed clarifications (kickoff)

- **1a.** Scope is CV rewrite only. No essay / life-story / SOP rewriter
  work in this feature (those can be separate features later).
- **2a.** LLM intent classifier is implemented as a **ReAct tool** the
  agent can call, not as a pre-agent stage. This keeps the agent in
  charge of tool orchestration.
- **3a.** Regex classifier is **removed entirely**. The LLM classifier
  is the only gate. There is no fast-path fallback.
- **4b.** The classifier is responsible for producing the curated
  `prior_feedback` block (it runs one LLM call and returns both intent
  and feedback). The agent passes that block to `rewrite_cv`; the
  rewriter consumes it as a first-class input.
- **5a.** Adding one ~300 ms LLM call per chat turn is acceptable.

## Success criteria

- For a source CV of arbitrary length (up to the stored 200 KB cap), the
  rewritten draft preserves every role, company, date range, education
  entry, award, and quantified metric that appears in the source (same
  ≥95% coverage target as the prior feature's eval harness).
- When the conversation contains applicable advisor feedback in the last
  N turns, the rewritten CV reflects that feedback (manually verifiable;
  QA will define how to measure).
- Natural phrasings like "apply those suggestions to my CV", "make it
  stronger based on what we discussed", and equivalent non-English
  phrasings all route to `rewrite_cv` via the classifier.
- The ReAct advisor never emits a CV body inline in `response` and never
  calls `save_artifact` directly for `cv_draft` content. All CV drafts
  flow through `rewrite_cv` → `RewriteCVSignature` → `save_artifact`.
- `DSPY_MODE=mock` tests stay deterministic (classifier mock returns a
  canned prediction derived from simple keyword heuristics; no real LLM).

## Explicitly out of scope

- Essay / life-story / SOP / recommendation-letter rewriters.
- Reintroducing any regex fast-path.
- Changing the PDF/DOCX renderer shipped in the prior feature.
- Changing the chunker, extraction cap, or `UploadedFileRepository`.
- Any database schema changes (hence no Alembic migration in this
  feature).
- Frontend changes (the feature is backend-only).
