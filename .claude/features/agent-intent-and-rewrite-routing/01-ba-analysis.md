# BA Analysis: Agent intent classification and rewrite-CV routing

## Status
COMPLETE

## Feature Request Summary
Replace the shipped regex rewrite-intent path (`app/dspy/intent.py` + `chat.py` preload branch) with an **LLM-based intent classifier** exposed as a **fifth ReAct tool** (`classify_intent`) that runs in the agent loop (not as a pre-agent gate). The tool returns, in one call, `task_kind`, `target_doc`, `emphasis`, and a curated `prior_feedback` string distilled from recent turns. **Routing policy:** when `task_kind == "rewrite_cv"`, the advisor is hard-bound to call `rewrite_cv` (and not inline CV in `response` or `save_artifact` for that content). **Rewriter change:** add `prior_feedback` to `RewriteCVSignature` and thread it from the tool into `OpenAIRewriteCVModule` / `MockRewriteCVModule`. **Route change:** delete regex preload — `_retrieve_doc_snippets` reverts to semantic top-k (plus existing no-API-key fallback) for every turn, matching the pre–FR-1 RAG path. **Scope:** CV rewrite only; **no** new regex fast-path. **Mock:** deterministic keyword heuristics for `MockIntentClassifier` so `DSPY_MODE=mock` stays offline.

## Codebase Findings

### Files Likely Requiring Changes

- **`backend/app/dspy/intent.py`** (lines 1–48: `_REWRITE_INTENT_RE`, `classify_rewrite_intent`) — **remove** entire module per fixed decision 3a; update/remove tests that import it.
- **`backend/app/api/routes/chat.py`** — Remove `from app.dspy.intent import classify_rewrite_intent` (line 28) and the rewrite-intent branch in `_retrieve_doc_snippets` (lines 55–81: `if classify_rewrite_intent(user_message):` through `return blocks`). Docstring (lines 49–53) and behavior revert to “always semantic + fallback” for preload.
- **`backend/app/dspy/agent_tools.py`** — Extend `build_agent_tools` (lines 35–44 return type, lines 379–384 return tuple) from a **4-tuple** to a **5-tuple** with new async `classify_intent(user_message, conversation_history)` (or equivalent signature per PM) wrapping the new DSPy module; add `prior_feedback: str = ""` to `rewrite_cv` (lines 277–342) and pass `prior_feedback` into `module.aforward(...)` in the `MockRewriteCVModule` / `OpenAIRewriteCVModule` call (lines 335–342).
- **`backend/app/dspy/rewrite_cv.py`** — `RewriteCVSignature` (lines 23–88): new input `prior_feedback`; docstring must instruct incorporating feedback **without** dropping source content (complements existing preservation rules, lines 27–44). `OpenAIRewriteCVModule` / `MockRewriteCVModule` `forward`/`aforward` (lines 98–189): add `prior_feedback` parameter; mock header may echo `prior_feedback` for determinism/visibility in tests.
- **`backend/app/dspy/agent_advisor.py`** — `AgentAdvisorSignature` docstring: replace preload rule that claims tagged full CV on “rewrite turns” (lines 22–27, 52–57) with guidance that full CV comes from `get_full_document` / classifier-driven flow; add fifth tool in TOOLS (today four tools, lines 29–45); add RULES for “first tool = `classify_intent`” and hard-binding for `rewrite_cv` when `task_kind == "rewrite_cv"`. `AgentAdvisorModule.__init__` (lines 107–128): add `classify_intent_fn`, register **five** tools in `dspy.ReAct` (line 120–127), re-evaluate `max_iters=6` (lines 115–119) if an extra tool step is always required. `MockAgentAdvisorModule` (lines 138–184): add fifth callable + `self.tools` order parity (FR-6 precedent from `rag` review: four-tool parity was RC-001 fix — now **five**-tool parity).
- **`backend/app/dspy/pipeline.py`** — Unpack and pass five tools from `build_agent_tools` (lines 239–264); comments on “full-doc preload” shapes (lines 277–285, 290–291) need alignment once route no longer injects tagged blocks for intent.
- **`backend/tests/test_agent_advisor_unit.py`** — All `build_agent_tools` unpacks (e.g. ~333, 358, 384–385, 413, 435, 462, 485, 515) and `MockAgentAdvisorModule` construction: extend to **five** callables.
- **`backend/tests/test_rag_rewrite_cv_tool.py`** — Unpacks (e.g. lines 162, 216, 253, 301, 344, 390, 438): arity + `rewrite_cv` tests for `prior_feedback` forwarding.
- **`backend/tests/test_rag_tool_wiring.py`** — Expects **4** callables and greps for stale unpacks (lines 6–7, 96–104); update to **5** and adjust regression grep rules.
- **`backend/tests/test_rag_chat_preload.py`** — TC-024+ assume intent-match → full-text preload (`[CV — full text]`, etc., lines 5–6, 74–81, …). **Obsolete or must be re-authored** to assert semantic-only behavior after `chat.py` change.
- **`backend/tests/test_rag_tool_selection.py`** — Couples `classify_rewrite_intent` + `_retrieve_doc_snippets` full-doc expectations (lines 25–26, 94–107, 120–210). **Replace** with tests aligned to the new design (agent tool / no route preload), not regex.
- **`backend/tests/test_rag_rewrite_intent_regex.py`** — **Delete** with `intent.py` or repurpose; entire file is FR-1 regex matrix (lines 18–201).

### Existing Capabilities Relevant to This Feature

- **Full-document access:** `UploadedFileRepository.get_latest_full_text_by_document_type` and `get_full_document` in `agent_tools.py` (lines 91–145) — **unchanged**; agent uses `get_full_document` when the classifier + rules require full CV.
- **CV rewrite pipeline:** `rewrite_cv` loads CV/life story/profile/dossier and calls `OpenAIRewriteCVModule` / `MockRewriteCVModule` (`agent_tools.py` 277–377, `rewrite_cv.py`).
- **Preload join logic:** `generate_assistant_response` in `pipeline.py` (lines 288–296) — still supports tagged full blocks **if** snippets ever start with `"["` and `"— full text]"`; after route change, preloads will typically be numbered semantic chunks only (unless another path injects tags).
- **ReAct advisor:** `AgentAdvisorModule` / `MockAgentAdvisorModule` and `dspy.ReAct` wiring (`agent_advisor.py` 106–135, 138–184).
- **Offline eval:** `backend/evals/rewrite_cv/` exercises rewriter directly; **should remain valid** if signature extension keeps mock deterministic (per your context).

### New Capabilities Required

- **New DSPy signature + modules:** e.g. `ClassifyIntentSignature` with `task_kind`, `target_doc`, `emphasis`, `prior_feedback`; `OpenAIIntentClassifier` + `MockIntentClassifier` (single LLM call; mock: keyword heuristics covering `rewrite_cv`, `qa`, `other`).
- **New ReAct tool:** `classify_intent` returning structured JSON (or equivalent) for the agent to parse, wrapping the classifier.
- **Prompt/rules engineering:** `AgentAdvisorSignature` rules enforcing call order and `rewrite_cv` when `task_kind == "rewrite_cv"`.
- **Optional guard:** truncate or cap `prior_feedback` before rewriter input (PM/spec) to control prompt size.

## Dependencies

- **Internal:** `dspy`, existing `build_agent_tools` / `AgentAdvisorModule` / `pipeline` / `chat` preload path; `UploadedFileRepository`; no new repositories required for intent if the classifier only needs `user_message` + `conversation_history` (already built in `pipeline.py` lines 267–308).
- **External:** OpenAI (or configured DSPy LM) for the classifier in non-mock mode — extra ~300 ms/turn is acceptable per clarification 5a.
- **Unchanged by this feature (per request):** DB schema, Alembic, frontend, chunker, `UploadedFileRepository` contract, `evals/rewrite_cv` harness shape (if rewriter API extended compatibly).

## Risks & Constraints

- **(a) Chattiness / iteration budget** — The design requires the agent to call `classify_intent` on **every** turn, so even trivial Q&A incurs at least one tool step (and one LLM call for the classifier in production). That increases ReAct steps and may push against `max_iters=6` (`agent_advisor.py` lines 115–127); `max_iters` and latency need explicit verification in implementation/QA.
- **(b) Mock-mode parity** — `MockAgentAdvisorModule` must register the same **five** tools as `AgentAdvisorModule` (`agent_advisor.py` 175–184 mirrors `build_agent_tools` order; prior feature **RC-001** was four-tool parity — `06-code-review.md` Round 2). `MockIntentClassifier` must be **deterministic** and cover all `task_kind` values for tests without network.
- **(c) No regex fast-path** — Rejected per 3a: any suggestion to keep `classify_rewrite_intent` for preload or “cheap” routing conflicts with the fixed architecture; `intent.py` and its tests are removed, not feature-flagged.
- **(d) `prior_feedback` length** — Unbounded feedback could dominate the rewriter prompt and displace `cv_text`; **length-capping** (and possibly prioritization) should be specified so `RewriteCVSignature` inputs stay within practical token limits.
- **(e) Non-English input** — Success criteria in `feature-request.md` include non-English phrasings routing to `rewrite_cv`; the classifier prompt and `task_kind` taxonomy must be robust to mixed/multilingual `user_message` and `conversation_history` without over-fitting to English keywords in mocks only (mocks can stay simple; production behavior is LLM-driven).

- **Test suite churn** — `test_rag_chat_preload.py` and `test_rag_tool_selection.py` are tightly coupled to the **removed** route behavior; expect broad test updates, not a narrow diff.

- **Preload no longer “free” for rewrites** — Without full-doc preload on the route, a mistaken skip of `get_full_document` on `rewrite_cv` could regress excerpt-only rewrites; mitigated by hard rules + strong integration coverage.

## Recommended Next Step
Hand off to the Product Manager to author `02-product-spec.md` using this analysis and the fixed decisions in `feature-request.md` (including explicit `classify_intent` I/O, `max_iters`, and `prior_feedback` limits).

## Output Artifacts
- `01-ba-analysis.md` ✅
