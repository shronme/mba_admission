# BA Analysis: School Selection Advisor

## Status
COMPLETE

## Feature Request Summary

After the automated admission evaluation (research and scoring) completes, allow the candidate to review their per-program results and explicitly select which schools they intend to pursue. Upon confirming that selection, open a dedicated chat interface (a new page or view) backed by an AI advisor that proactively suggests ways to improve their admission chances for the chosen schools — for example, strengthening their CV, reviewing an essay draft, improving their test score strategy, or addressing specific profile gaps the evaluation surfaced.

---

## Codebase Findings

### Current User Journey (State Before This Feature)

1. Candidate completes the 4-step intake form (school/program pairs selected as part of intake step 1, stored in `profile.attributes.school_program_selections`).
2. On the post-intake dashboard (`CandidateDashboard`), `AdmissionEvaluationPanel` auto-triggers `POST /candidates/me/admission-evaluation/start`.
3. A background job (`admission_evaluation_job`) researches each selected school via Perplexity and scores fit via OpenAI, writing results into `profile.attributes.admission_evaluation_result` (status: `complete | failed`).
4. The UI polls for completion and renders `EvaluationResultsView` — per-program cards showing strengths, weaknesses, admission band, narrative strategy, and priority actions.
5. The footer of `EvaluationResultsView` renders two **disabled** buttons: "Export full report" and "Proceed to positioning". There is no active CTA after results are shown.

The candidate stage is set to `CandidateStage.PROGRAM_RESEARCH` (value: `"program_research"`) after the evaluation job succeeds. The pipeline defines further stages: `STRATEGY`, `NARRATIVE`, `SCHOOL_LIST`, `APPLICATION_WORK` — none of which have UI yet.

The chat infrastructure is fully built (`ChatThread`, `ChatMessage`, streaming endpoint, `ChatRepository`) but is currently used only for the intake interview thread (`extra: {"stage": "intake"}`). The `ChatThread` model has an `extra: JSONB` field that can carry arbitrary metadata including a stage discriminator.

---

### Files Likely Requiring Changes

**Backend**

- `backend/app/api/routes/chat.py` — needs a new thread-creation path (or an extension to the existing `POST /chat/threads`) that tags a thread as `"stage": "advisor"` and injects school-selection context into the initial greeting; also needs the streaming handler to route advisor-stage threads to the new DSPy advisor module instead of the intake interviewer.
- `backend/app/dspy/pipeline.py` — the `generate_assistant_response` routing block currently branches only on `profile_complete`. A third branch (or a separate function `generate_advisor_response`) is needed for the school-selection advisor persona.
- `backend/app/api/routes/admission_evaluation.py` — optionally: add a `POST /candidates/me/admission-evaluation/school-selection` endpoint (or reuse the profile-attributes mechanism) to persist the candidate's finalized school selection to `profile.attributes.selected_schools`.
- `backend/app/db/enums.py` — `CandidateStage` already has `SCHOOL_LIST` and `STRATEGY` values. The appropriate stage (`STRATEGY` or `SCHOOL_LIST`) should be set when the candidate confirms their selection.
- `backend/app/workers/tasks/admission_evaluation_task.py` — no changes required initially, though it could later be extended to trigger a "school selection" strategy job.
- `backend/app/repositories/candidate_repo.py` — may need a method to store confirmed selected schools (separate from intake selections).

**Frontend**

- `apps/web/src/components/AdmissionEvaluationPanel.tsx` — the `EvaluationResultsView` footer's "Proceed to positioning" button needs to become active and launch the school-selection step. A school-selection overlay or inline selection UI will be embedded here or triggered from here.
- `apps/web/src/components/CandidateDashboard.tsx` — needs to support a new `activeTab` value (e.g. `"advisor"`) or a page navigation to the advisor chat view.
- `apps/web/src/components/CandidateStitchShell.tsx` — the phase index passed in (`activePhaseIndex={1}`) will need to advance to phase 2 or 3 when the candidate confirms selection and enters the advisor.
- `apps/web/src/lib/api.ts` — new API call functions: `confirmSchoolSelection(sessionToken, selectedSchools)` and `createAdvisorThread(sessionToken)`.
- **New file**: `apps/web/src/components/SchoolSelectionConfirm.tsx` — multi-select UI overlaid on or replacing the evaluation results footer; lets the candidate check/uncheck programs from the evaluated list before confirming.
- **New file**: `apps/web/src/components/AdvisorChatPage.tsx` (or `apps/web/src/app/advisor/page.tsx`) — the chat interface for the school-selection advisor, reusing the streaming infrastructure from the intake chat.

---

### Existing Capabilities Relevant to This Feature

- **Streaming chat infrastructure** — `POST /chat/threads/{id}/messages/stream` in `chat.py` already handles full streaming, profile injection, RAG doc snippets, recent-message context, and persistence. The advisor chat can reuse this endpoint with a different system-prompt path.
- **ChatThread.extra JSONB** — the `extra` column on `ChatThread` already stores `{"stage": "intake"}`. Setting `{"stage": "advisor", "selected_schools": [...]}` is a zero-migration extension.
- **Admission evaluation result** — the complete per-program result (`strengths`, `weaknesses`, `priority_actions`, `narrative_strategy`, `admission_band`) is already available in `profile.attributes.admission_evaluation_result`. The advisor DSPy module can consume this directly as structured context, giving it a head-start on what to recommend.
- **CandidateProfile.attributes JSONB** — free-form JSON store; `selected_schools` can be persisted here with zero schema migration, consistent with how `school_program_selections`, `admission_evaluation_result`, and `intake_test_scores` are currently stored.
- **DSPy module pattern** — `research_agent.py` (ResearchAgent) demonstrates the pattern of a one-shot "handover" message. The advisor module will follow the same pattern but for conversational turns (similar to `intake_interviewer.py`).
- **EssayDraft / EssayReview models** — the essay infrastructure exists in `essay.py` (school_name, prompt_text, body, AI reviews). The advisor chat could reference or create essay drafts in later iterations.
- **StrategyDecision model** — `strategy_decisions` table exists with `StrategyType.SCHOOL_SELECTION`. A `StrategyDecision` row with this type and the confirmed school list as `payload` is the semantically correct place to persist the finalized selection.

---

### New Capabilities Required

1. **School selection confirmation API endpoint** — `POST /candidates/me/school-selection/confirm` accepting a list of `{school, program_slug}` objects. Persists the selection to `profile.attributes.selected_schools` (and optionally creates a `StrategyDecision` row with `strategy_type = SCHOOL_SELECTION`). Advances `candidate.stage` to `CandidateStage.STRATEGY`.

2. **Advisor DSPy module** (`backend/app/dspy/school_advisor.py`) — A conversational DSPy module that, given:
   - candidate profile attributes (background, goals, test scores)
   - selected school + program combinations
   - per-program evaluation results (strengths, weaknesses, priority_actions)
   - conversation history
   produces prioritized, actionable advice (CV gaps, essay angles, test score improvements, outreach steps, timeline). This is the core new LLM capability.

3. **Advisor chat thread creation** — `POST /chat/threads` needs to support (or a new endpoint needs to create) a thread tagged with `stage = "advisor"`. On creation it should send an opening assistant message that orients the candidate around their selected schools and top priority actions, synthesized from the evaluation result.

4. **Routing update in `generate_assistant_response`** — the pipeline must detect when the active thread's stage is `"advisor"` and dispatch to the new `AdvisorModule` rather than the `IntakeInterviewer` or `ResearchAgent`.

5. **School selection UI** (`SchoolSelectionConfirm` component) — presented after evaluation results are rendered. Shows a checklist of the evaluated programs (pre-selected by default). The candidate deselects any they do not want to pursue, then clicks "Confirm & get advice." Calls the new confirmation API, then navigates to the advisor chat.

6. **Advisor chat UI** — a chat page/view showing:
   - A header summarizing the confirmed school list (school names + programs).
   - The streaming chat bubble interface (re-use the intake chat pattern, adapted for the advisor context).
   - Quick-action prompts (e.g., "Review my CV", "Help with HBS essay", "Improve my GMAT score") as tappable chips that pre-fill the input.

---

## Dependencies

**Internal**

- `profile.attributes.admission_evaluation_result` — must be `status: complete` before school selection is meaningful; the UI must gate accordingly.
- `profile.attributes.school_program_selections` (from intake) — the initial school list comes from here, but the candidate may now select a subset.
- `ChatThread` / `ChatMessage` — the advisor uses the same persistence layer.
- `CandidateRepository.merge_profile_attributes` — used to write `selected_schools` without a schema change.
- `StrategyDecision` model — optional but semantically appropriate for persisting the confirmed list.

**External**

- OpenAI (OPENAI_API_KEY) — the advisor module will use the same OpenAI LM used for evaluation and intake.
- No new external services required. Perplexity is not needed for the advisor phase (it already ran during evaluation).

**Libraries / Tooling**

- No new npm packages needed for the frontend (the streaming + chat pattern already exists in the intake flow, though currently in `CandidateIntakeForm` rather than an extracted hook/component).
- No new Python packages needed.

---

## Risks & Constraints

1. **No isolated chat component exists yet.** The intake chat is embedded inside `CandidateIntakeForm.tsx` (a 900+ line file) rather than being an extracted reusable component. The advisor chat will need either to duplicate the streaming pattern or trigger a refactor to extract a `ChatBubbleList` / `StreamingChatInput` component. Doing a partial duplicate first is faster but creates tech debt.

2. **Thread stage routing happens inside the pipeline, not on the thread.** Currently `generate_assistant_response` has no knowledge of which thread it is answering; the chat route (`chat.py`) passes no thread metadata to the pipeline. Adding a `thread_stage` parameter to `generate_assistant_response` (and passing `thread.extra.get("stage")` from the route) is a low-risk but required change.

3. **`profile.attributes` is an untyped JSONB blob.** All evaluation results, job progress, and profile data are merged into a single flat attributes dict. Adding `selected_schools` here is consistent with the existing pattern but increases the blob size. Long-term, a dedicated `school_selections` table would be cleaner; for now the JSONB approach is consistent.

4. **Idempotency of the advisor thread.** The intake thread is reused if one exists (`get_latest_active_thread`). The advisor must have a clear stage discriminator so a second visit does not spawn duplicate advisor threads or, worse, conflate the advisor thread with the intake thread.

5. **The evaluation job is currently triggered automatically** on dashboard mount, before the candidate has a chance to opt in. If the evaluation fails or takes a very long time, the candidate may never reach the school-selection step. The school selection gate must handle `result.status === "failed"` gracefully (offer a retry path, not a dead end).

6. **Candidate may return after a session break.** If the candidate confirmed their school selection in a prior session, the advisor thread and `selected_schools` attribute should already exist; the UI must detect this and navigate directly to the existing advisor thread rather than showing the selection UI again.

7. **Extra program recommendations** (the `result.extra` array) are agent-suggested schools the candidate did not select during intake. The selection UI must decide whether to include these as selectable options or treat them as informational only. Including them as opt-in selections is the more useful UX but slightly increases scope.

---

## Open Questions / Assumptions

- **Does "new page" mean a distinct Next.js route** (e.g., `/advisor`) or a view switch within the existing dashboard layout? A route (`/advisor`) is cleaner for deep-linking and browser back-button, but the current app has minimal routing (documents is a tab, not a route). Assumption: implement as a new route for the advisor page.
- **Should the advisor thread be a single persistent thread per candidate**, or can there be multiple (one per session / selection event)? Assumption: one active advisor thread per candidate; re-open if it already exists.
- **Scope of quick-action prompts**: are CV review, essay review, and test strategy all in scope for the first version? Assumption: the advisor DSPy module should handle all three conversationally; hard-coded quick-action chips are UI sugar that pre-fills the text input.
- **Should confirming school selection trigger a new background job?** (e.g., generating a personalized study plan or fetching essay prompts.) This is out of scope for the initial version; the advisor answers questions on demand.

---

## Recommended Next Step

Hand off to Product Manager with this analysis for spec writing.

## Output Artifacts

- `01-ba-analysis.md` ✅
