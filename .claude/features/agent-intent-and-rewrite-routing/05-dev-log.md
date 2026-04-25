# Dev Log: Agent intent classification and rewrite-CV routing

## Status
COMPLETE

## Progress

| Task | Status | Notes |
|------|--------|-------|
| TASK-001 | DONE | Removed regex-driven route preload; semantic-only `_retrieve_doc_snippets`; deleted unused import. |
| TASK-002 | DONE | Added strict schema + normalizer in `backend/app/schemas/agent_advisor_intent.py`. |
| TASK-003 | DONE | Implemented `OpenAIIntentClassifier` (`IntentClassifierSignature`) returning JSON string. |
| TASK-004 | DONE | Implemented deterministic `MockIntentClassifier` covering all 4 `task_kind` values. |
| TASK-005 | DONE | Added `classify_intent` as 5th tool; uses last 10 messages; returns JSON string; QA fallback on failure. |
| TASK-006 | DONE | Added per-trajectory `rewrite_cv_ran` state + `save_artifact` guard for `cv_draft`; internal rewrite save allowed. |
| TASK-007 | DONE | Threaded `prior_feedback` through `rewrite_cv` tool and `RewriteCVSignature` + modules (no code-level cap). |
| TASK-008 | DONE | Updated `AgentAdvisorSignature` tool docs + rules: classify first; semantic snippets; no full CV paste on rewrite. |
| TASK-009 | DONE | Wired 5 tools into `dspy.ReAct` with `max_iters=8`. |
| TASK-010 | DONE | Updated `MockAgentAdvisorModule` for five-tool parity. |
| TASK-011 | DONE | Updated `pipeline.py` to unpack 5-tuple + pass classifier; refreshed semantic-only snippet comments. |
| TASK-012 | DONE | Deleted obsolete regex intent tests (`test_rag_rewrite_intent_regex.py`). |
| TASK-013 | DONE | Rewrote `test_rag_tool_selection.py` to assert semantic-only preload path (no full-doc preload). |
| TASK-014 | DONE | Updated `test_rag_chat_preload.py` for semantic-only route behavior. |
| TASK-015 | DONE | Updated `test_rag_tool_wiring.py` for 5 tools + `max_iters=8` + grep regression guard. |
| TASK-016 | DONE | Updated `test_agent_advisor_unit.py` wiring/unpacks to 5 tools and `max_iters=8`. |
| TASK-017 | DONE | Updated rewrite/get-full-document tests for 5-tuple and `prior_feedback` propagation. |
| TASK-018 | DONE | Added `backend/tests/test_intent_classifier.py` (matrix + 10-message window + invalid JSON/exception → QA fallback). |
| TASK-019 | DONE | Added save-artifact guard tests (unit + integration-level persistence checks). |
| TASK-020 | DONE | Updated advisor integration expectations to tolerate semantic-only preloads + classifier tool presence. |
| RC-001 | DONE | Fixed RULES contradiction: `classify_intent` is always first; “no tools” only applies after classification. |
| RC-002 | DONE | Added recovery-sequence integration test covering guard → rewrite_cv → save_artifact within `max_iters=8`. |

## Blockers
- None

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅
- `03-qa-plan.md` ✅
- `04-tasks.md` ✅
- `05-dev-log.md` ✅

