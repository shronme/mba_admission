# Code Review: Agent intent classification and rewrite-CV routing

## Status
APPROVED

## Review Round
Round 2

## Summary
Round 1 required aligning `AgentAdvisorSignature` RULES with “`classify_intent` first” (RC-001) and adding a test tying the save-artifact guard recovery path to the ReAct iteration budget (RC-002). Both are resolved: RULE 2 now explicitly applies **after** `classify_intent` and only allows skipping **additional** tools for Q&A/smalltalk when snippets suffice; and `test_guard_recovery_sequence_fits_within_react_iteration_budget` asserts `max_iters == 8` and demonstrates guard → `rewrite_cv` → successful `save_artifact` using the same `build_agent_tools` closures.

## Required Changes (must fix before approval)

_No outstanding required changes._

## Suggested Improvements (optional, not blocking)

### SI-001: Stale test name / comments in tool wiring tests
- **File**: `backend/tests/test_rag_tool_wiring.py`
- **Suggestion**: Rename `test_returns_four_callables_in_fixed_order` to reflect five callables; update the docstrings/comments to reflect `max_iters=8`.

### SI-002: `MockAgentAdvisorModule` vs real `save_artifact` guard
- **File**: `backend/app/dspy/agent_advisor.py`
- **Suggestion**: `MockAgentAdvisorModule.aforward` may attempt to persist `cv_draft` directly; if this conflicts with the guard, consider routing mock CV success through a stubbed `rewrite_cv`-style path consistent with the guard.

### SI-003: `classify_intent` returns raw LLM string after validation
- **File**: `backend/app/dspy/agent_tools.py`
- **Suggestion**: Consider returning canonical JSON from the parsed model for stable downstream parsing (not required by spec).

## Checklist
- [x] Correctness
- [x] Completeness — Core FRs implemented; **RC-001** and **RC-002** are the main gaps vs spec/tasks.
- [x] Code quality — Solid; a few stale comments in tests (**SI-001**).
- [x] Edge case handling — Classifier failures → QA + logging; enum validation → QA; guard blocks naked `cv_draft` saves.
- [x] Security — No new obvious injection; classifier window limited; logging uses existing patterns.
- [x] Tests present — Good unit/integration coverage; **RC-002** for TC-018-style loop.
- [x] No obvious regressions — `chat` preload path is consistent with semantic-only design.

## Output Artifacts
- `06-code-review.md` ✅

