# Product Specification: School Selection Advisor

## Status
COMPLETE

## Overview

After the automated admission evaluation completes, candidates are currently left at a dead end — two disabled buttons and no clear next step. The School Selection Advisor closes that gap by letting the candidate confirm which evaluated programs they intend to pursue (including AI-suggested extras as opt-in choices), then immediately connecting them to a persistent AI advisor chat at `/advisor` that knows their profile, their confirmed schools, and the specific strengths, weaknesses, and priority actions surfaced by the evaluation. The advisor responds conversationally to whatever the candidate needs next — strengthening their CV, workshopping an essay angle, adjusting their test score strategy, or understanding a specific gap — turning the evaluation output into an ongoing, actionable coaching relationship rather than a static report. This feature also establishes a reusable `StreamingChat` component that replaces the legacy inline streaming logic in `CandidateIntakeForm.tsx`.

---

## Goals & Success Metrics

- Goal: Convert the evaluation dead-end into a clear next step that drives candidates into the strategy phase.
  - Metric: >= 60% of candidates who see a completed evaluation result click "Confirm & get advice" within the same session.

- Goal: Provide high-quality, context-aware admission advice grounded in the candidate's actual evaluation results.
  - Metric: >= 5 candidate turns per advisor session on average (proxy for engagement quality).

- Goal: Advance the candidate pipeline stage from `program_research` to `strategy`.
  - Metric: `candidate.stage` transitions to `STRATEGY` for every candidate who confirms their school selection.

- Goal: Eliminate streaming logic duplication between intake and advisor surfaces.
  - Metric: Zero direct `fetch` / `ReadableStream` calls in `CandidateIntakeForm.tsx` or the advisor page after the refactor.

---

## User Stories

- As a candidate who has just received my evaluation results, I want to select which programs I actually intend to apply to, so that the platform can focus its guidance on the schools that matter to me.

- As a candidate reviewing per-program evaluation cards, I want my evaluated programs pre-checked with AI-suggested extras available as opt-in, so that I can confirm quickly or expand my list with minimal effort.

- As a candidate entering the advisor chat, I want to see an opening message that immediately calls out my biggest priorities across my chosen schools, so that I know where to start.

- As a candidate mid-conversation, I want to ask follow-up questions without losing the context of my profile or previous messages, so that I get coherent, personalised answers throughout a session.

- As a candidate returning after a break, I want to re-enter my existing advisor conversation or start a fresh one, so that I can either continue where I left off or get a clean slate.

- As a candidate who finds the advisor useful, I want quick-action chips to jump into common tasks, so that I don't have to figure out how to phrase my request.

---

## Functional Requirements

### FR-1: Chat Component Refactor

**Description:** The streaming chat logic currently embedded in `CandidateIntakeForm.tsx` must be extracted into a standalone, reusable `StreamingChat` component before any new chat surface is built. This is a hard prerequisite — no duplicate streaming logic is permitted.

**Acceptance Criteria:**
- [ ] `apps/web/src/components/StreamingChat.tsx` exists with the public API defined in the Chat Component Refactor Scope section.
- [ ] `CandidateIntakeForm.tsx` is updated to use `StreamingChat` and contains no direct `fetch` / `ReadableStream` / token-accumulation logic.
- [ ] The advisor page uses `StreamingChat` (not its own streaming implementation).
- [ ] No regression in the intake chat flow (thread creation, streaming, message persistence, profile update callbacks).

---

### FR-2: School Selection Checklist

**Description:** When `admission_evaluation_result.status === "complete"`, the disabled "Proceed to positioning" button in the `EvaluationResultsView` footer is replaced by an active `SchoolSelectionConfirm` panel. The panel shows a checklist of all evaluated programs. `result.primary` programs are pre-checked. `result.extra` programs appear as unchecked opt-in rows under a clearly labelled "Additional recommendations" section. At least one program must be checked before the candidate can confirm.

**Acceptance Criteria:**
- [ ] Every program in `result.primary` renders as a pre-checked row with school name and program display name.
- [ ] Every program in `result.extra` renders as an unchecked, opt-in row under "Additional recommendations" with school name and program display name.
- [ ] "Confirm & get advice" is disabled when zero programs are checked.
- [ ] Clicking "Confirm & get advice" calls `POST /candidates/me/school-selection/confirm` with the checked list.
- [ ] On API success, the frontend calls `POST /chat/advisor-threads` and navigates to `/advisor`.
- [ ] If `profile.attributes.selected_schools` is already set on page load (returning session), the selection panel is skipped and a "Continue with your advisor" CTA navigates directly to `/advisor`.
- [ ] If the API call fails, an inline error is shown; checklist state is preserved.

---

### FR-3: Evaluation Failure Retry

**Description:** When `admission_evaluation_result.status === "failed"` and no job is currently running, the evaluation panel displays an error summary and a visible, primary-styled "Retry evaluation" button. School selection is inaccessible until evaluation succeeds.

**Acceptance Criteria:**
- [ ] The failed state renders a human-readable error message (from `result.error`) and a "Retry evaluation" button styled as the primary action (not ghost/secondary).
- [ ] Clicking "Retry evaluation" calls `POST /candidates/me/admission-evaluation/start` and restarts the polling loop.
- [ ] The existing retry wiring in `AdmissionEvaluationPanel` (`retryStart` callback) is confirmed to implement this behaviour; it must not be removed or downgraded.

---

### FR-4: School Selection Confirmation API

**Description:** A new endpoint persists the confirmed school list, creates a `StrategyDecision` record, and advances the candidate's stage to `STRATEGY`.

**Acceptance Criteria:**
- [ ] `POST /candidates/me/school-selection/confirm` accepts the request body defined in the API Contract section.
- [ ] `profile.attributes.selected_schools` is written via `CandidateRepository.merge_profile_attributes` (no migration).
- [ ] A `StrategyDecision` row is upserted: `strategy_type = StrategyType.SCHOOL_SELECTION`, `payload = selected_schools`. One row per candidate; a second call overwrites, not appends.
- [ ] `candidate.stage` is set to `CandidateStage.STRATEGY`.
- [ ] Returns `400` if `selected_schools` is empty or missing.
- [ ] Returns `409` if `admission_evaluation_result.status` is not `"complete"`.
- [ ] Returns `401` if the session token is invalid.

---

### FR-5: Advisor Thread Endpoint

**Description:** A dedicated endpoint creates or retrieves the candidate's advisor thread, tagged `stage: "advisor"` in `ChatThread.extra`. On new thread creation it persists an opening assistant message personalised to the confirmed school list and evaluation findings.

**Acceptance Criteria:**
- [ ] `POST /chat/advisor-threads` checks for an existing active `ChatThread` where `extra->>'stage' = 'advisor'` for this candidate.
- [ ] With `?new=false` (default): if a thread exists, return it; if not, create one.
- [ ] With `?new=true`: close (`status = CLOSED`) any existing advisor thread and create a new one.
- [ ] On new thread creation, generate and persist an initial assistant message that names the confirmed schools, references the top priority actions from the evaluation result, and invites the candidate to choose a focus area.
- [ ] The `ChatThread.extra` payload for advisor threads is `{"stage": "advisor", "selected_schools": [...]}`.
- [ ] Response: `{"thread_id": "<uuid>", "is_new": <bool>}`.
- [ ] Returns `409` if `profile.attributes.selected_schools` is absent (confirmation step was skipped).

---

### FR-6: Pipeline Routing for Advisor Stage

**Description:** The streaming chat endpoint must detect advisor-stage threads and dispatch to the new `AdvisorModule` instead of `IntakeInterviewer` or `ResearchAgent`.

**Acceptance Criteria:**
- [ ] `POST /chat/threads/{id}/messages/stream` reads `thread.extra.get("stage")` from the database before dispatching.
- [ ] When `stage == "advisor"`, the request is routed to `AdvisorModule` with the candidate profile, selected schools, evaluation result, and conversation history.
- [ ] When `stage == "intake"` (or absent), existing behaviour is unchanged.
- [ ] The `generate_assistant_response` function accepts a `thread_stage: str | None` parameter (or a peer function `generate_advisor_response` is added).

---

### FR-7: Advisor DSPy Module

**Description:** A new `AdvisorModule` in `backend/app/dspy/school_advisor.py` handles all conversational turns for advisor-stage threads.

**Acceptance Criteria:**
- [ ] The module accepts: candidate profile attributes, selected schools list, per-program evaluation results (`strengths`, `weaknesses`, `priority_actions`, `narrative_strategy`), and recent conversation history.
- [ ] Responses are specific to the candidate's profile and selected schools, not generic MBA advice.
- [ ] The module handles at minimum: CV/resume gap questions, essay angle questions, test-score strategy questions, and open-ended "what should I focus on" questions.
- [ ] A `MockAdvisorModule` exists for use with `DSPY_MODE=mock` (deterministic, no API calls).
- [ ] The module follows the same DSPy module pattern as `intake_interviewer.py` (class inheriting from `dspy.Module`, `forward` method).

---

### FR-8: Advisor Page at /advisor

**Description:** A dedicated Next.js App Router page at `/advisor` renders the school advisor chat.

**Acceptance Criteria:**
- [ ] The page exists at `apps/web/src/app/advisor/page.tsx`.
- [ ] On load, the page reads the candidate session. If unauthenticated, redirect to sign-in.
- [ ] If `profile.attributes.selected_schools` is absent, redirect to the dashboard with a toast/notice.
- [ ] If an active advisor thread exists (and `?new` is absent from the URL), load and display it.
- [ ] If no active advisor thread exists, call `POST /chat/advisor-threads` to create one, then load it.
- [ ] A header section shows the confirmed schools as compact pills (school name + program abbreviation).
- [ ] The `StreamingChat` component is rendered below the header.
- [ ] Three quick-action chips are shown above the input field: "Help with my CV gaps", "Plan my essay strategy", "Improve my GMAT/GRE score". Clicking a chip pre-fills the input; it does not auto-submit.
- [ ] A "Start new conversation" button calls `POST /chat/advisor-threads?new=true`, creates a new thread, and reloads the chat pane.
- [ ] The `CandidateStitchShell` phase indicator shows phase 3 (strategy) on this page.

---

### FR-9: Dashboard Navigation Update

**Description:** The dashboard must surface the school selection step and, after confirmation, provide a path back into the advisor.

**Acceptance Criteria:**
- [ ] When `admission_evaluation_result.status === "complete"` and `selected_schools` is absent, the "Proceed to positioning" button in the evaluation footer is active and opens the `SchoolSelectionConfirm` panel.
- [ ] When `candidate.stage === "strategy"` (or `selected_schools` is present) on dashboard load, a "Continue with your advisor" CTA is displayed and links to `/advisor`.
- [ ] The `CandidateStitchShell` phase indicator advances to phase 3 when `candidate.stage` is `"strategy"` or later.

---

## Non-Functional Requirements

### Performance
- `POST /candidates/me/school-selection/confirm` must respond within 500 ms (pure DB writes, no LLM call).
- `POST /chat/advisor-threads` must return the `thread_id` within 3 seconds. The opening message may be pre-generated synchronously as part of thread creation or streamed separately; either approach is acceptable as long as at least the thread ID is returned within the SLO.
- First streaming token from `POST /chat/threads/{id}/messages/stream` (advisor stage) must arrive within 3 seconds (same SLO as intake chat).
- `/advisor` page initial render (profile + thread + message list) must complete within 2 seconds on a standard broadband connection.

### Security
- All new endpoints require a valid bearer token via the existing `get_candidate_id_from_bearer_token` dependency.
- Candidates may only access their own threads and profile data. The `_ensure_thread_owned` guard must be applied to all advisor thread operations.
- `selected_schools` payload is validated: each entry must have a non-empty `school` string and a non-empty `program_slug` string; array maximum length 10.

### Accessibility
- The school selection checklist uses native `<input type="checkbox">` elements with associated `<label>` elements (not `div`-based click targets).
- "Confirm & get advice" uses `aria-disabled="true"` when disabled, in addition to the visual disabled style.
- Quick-action chips are `<button>` elements with descriptive `aria-label` attributes.
- The chat message list exposes an `aria-live="polite"` region so screen readers announce new assistant messages as they arrive during streaming.

### Error States
- Confirmation API failure: inline error above the confirm button; checklist state preserved.
- Advisor thread creation failure: inline error on the `/advisor` page with a "Try again" button; do not render a broken chat pane.
- Streaming failure mid-response: partially accumulated text is retained in the chat bubble; an inline "Something went wrong — please try again" notice is appended; the input field is re-enabled.
- Evaluation failure: a primary-styled "Retry evaluation" button is the sole CTA; the school selection panel is not reachable until evaluation succeeds.

---

## UX Flows

### Flow 1: First Visit After Evaluation Completes

1. Candidate is on the dashboard. The evaluation job completes and `EvaluationResultsView` renders per-program cards.
2. The footer area below the cards now shows `SchoolSelectionConfirm` in place of the disabled buttons.
3. The checklist shows all `result.primary` programs pre-checked and all `result.extra` programs unchecked under "Additional recommendations".
4. Candidate reviews, optionally checks one or more extra programs or unchecks a primary program.
5. Candidate clicks "Confirm & get advice" (enabled because at least one box is checked).
6. Frontend calls `POST /candidates/me/school-selection/confirm`. On success, calls `POST /chat/advisor-threads`.
7. Frontend navigates to `/advisor`.
8. The advisor page renders: school header pills, opening assistant message, quick-action chips, and an empty input field.
9. Candidate types a message or clicks a chip. Streaming response begins.

### Flow 2: School Selection + Confirm (detailed)

1. `SchoolSelectionConfirm` is mounted with `result.primary` and `result.extra`.
2. Each `primary` entry renders as a checked row: school name (bold) + program display name (muted).
3. A section break labelled "Additional recommendations" follows; each `extra` entry renders as an unchecked row.
4. Candidate unchecks "Yale SOM — MBA" (for example). One primary program and zero extras remain checked.
5. "Confirm & get advice" remains enabled (1 program selected).
6. Candidate clicks confirm. A spinner replaces the button text.
7. `POST /candidates/me/school-selection/confirm` succeeds. `POST /chat/advisor-threads` is called.
8. Navigation fires to `/advisor`.

### Flow 3: Advisor Chat Session

1. Candidate is on `/advisor`. The `StreamingChat` component renders the message history (at minimum the opening assistant message).
2. Candidate types "What are my biggest CV weaknesses for HBS?" and presses Enter.
3. `POST /chat/threads/{thread_id}/messages/stream` is called. The pipeline reads `thread.extra.stage = "advisor"` and dispatches to `AdvisorModule`.
4. The assistant response streams token-by-token into a chat bubble.
5. On completion, the full response is persisted as a `ChatMessage`.
6. Candidate clicks the "Plan my essay strategy" chip. The input field pre-fills with that text. Candidate edits it and submits.

### Flow 4: Returning Visit

1. Candidate re-authenticates and loads the dashboard.
2. Dashboard detects `candidate.stage === "strategy"` and `selected_schools` is present.
3. A "Continue with your advisor" button is shown in the dashboard.
4. Candidate clicks it, lands on `/advisor`.
5. The existing advisor thread and all prior messages render. The conversation continues.
6. If the candidate wants a fresh start, they click "Start new conversation". The current thread is closed, a new one is created, and the opening message renders.

### Flow 5: Evaluation Failure and Retry

1. Candidate is on the dashboard. The evaluation job has failed.
2. `AdmissionEvaluationPanel` renders: error message + "Retry evaluation" button (primary style).
3. The school selection panel is not accessible.
4. Candidate clicks "Retry evaluation". The endpoint is called, the polling loop restarts.
5. On success, the evaluation completes and the flow continues from Flow 1 step 1.

---

## API Contract

### POST /candidates/me/school-selection/confirm

Persists the confirmed school list, upserts a StrategyDecision row, and advances the candidate's stage.

**Request body**
```json
{
  "selected_schools": [
    { "school": "Harvard Business School", "program_slug": "mba" },
    { "school": "Stanford GSB", "program_slug": "mba" }
  ]
}
```

**Response 200**
```json
{
  "selected_schools": [
    { "school": "Harvard Business School", "program_slug": "mba" },
    { "school": "Stanford GSB", "program_slug": "mba" }
  ],
  "stage": "strategy"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400  | `selected_schools` is empty, missing, or contains invalid entries |
| 401  | Missing or invalid bearer token |
| 409  | `admission_evaluation_result.status` is not `"complete"` |
| 422  | Pydantic validation error (malformed body) |

---

### POST /chat/advisor-threads

Creates or retrieves the candidate's advisor thread.

**Query parameter:** `new` (boolean string, optional, default `false`). When `true`, closes any existing active advisor thread and creates a new one.

**Request body:** empty.

**Response 200**
```json
{
  "thread_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "is_new": true
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401  | Missing or invalid bearer token |
| 409  | `profile.attributes.selected_schools` is absent (must confirm selection first) |

---

### POST /chat/threads/{thread_id}/messages/stream

No structural change. The existing endpoint is reused. The pipeline internally dispatches to `AdvisorModule` when `thread.extra.get("stage") == "advisor"`. Response format (chunked `text/plain; charset=utf-8`) is unchanged.

---

### GET /chat/threads/{thread_id}/messages

No change. Used to load the advisor thread message history on page mount.

---

## Data Model Changes

All changes extend existing JSONB fields or add rows to existing tables. No new migrations are required.

### profile.attributes extensions (JSONB, zero migration)

New key written by `POST /candidates/me/school-selection/confirm`:

```json
{
  "selected_schools": [
    {
      "school": "Harvard Business School",
      "program_slug": "mba",
      "program_display_name": "MBA"
    }
  ]
}
```

Written via `CandidateRepository.merge_profile_attributes`, consistent with all other attribute writes.

---

### ChatThread.extra extensions (JSONB, zero migration)

Advisor threads use the following `extra` shape (extends the existing `{"stage": "intake"}` pattern):

```json
{
  "stage": "advisor",
  "selected_schools": [
    {
      "school": "Harvard Business School",
      "program_slug": "mba",
      "program_display_name": "MBA"
    }
  ]
}
```

The `selected_schools` snapshot is embedded in the thread's `extra` so the `AdvisorModule` can access it without a profile re-fetch in the streaming hot path.

---

### StrategyDecision row (existing table, new row)

On `POST /candidates/me/school-selection/confirm`:
- `strategy_type`: `StrategyType.SCHOOL_SELECTION`
- `payload`: the confirmed `selected_schools` array
- `candidate_id`: the confirming candidate

Upsert semantics: if a row with `(candidate_id, strategy_type=SCHOOL_SELECTION)` already exists, it is updated. No append-only history at this stage.

---

### CandidateStage transition (existing enum, existing column)

`CandidateStage.STRATEGY` (value `"strategy"`) is already defined in `backend/app/db/enums.py`. The confirmation endpoint sets `candidate.stage = CandidateStage.STRATEGY` using the existing `stage` column on `Candidate`. No migration required.

---

## Chat Component Refactor Scope

### What Gets Extracted

All of the following logic, currently inline in `CandidateIntakeForm.tsx` (approximately the final-questions/chat area), must move into `apps/web/src/components/StreamingChat.tsx`:

- `fetch` call to `POST /chat/threads/{id}/messages/stream` with `text/plain` streaming response consumption via `ReadableStream` / `getReader()`.
- Token accumulation state and incremental rendering into an "in-progress" assistant bubble.
- Submission of a text message and clearing of the input.
- Initial message history load via `GET /chat/threads/{id}/messages` on mount.
- Rendering of the message list: user bubbles (right-aligned) and assistant bubbles (left-aligned).
- Inline error display for stream failures.

### New Component Public API

```tsx
interface StreamingChatProps {
  /** Bearer token for API auth. */
  sessionToken: string;
  /** ID of the chat thread to load and stream into. */
  threadId: string;
  /** Optional placeholder text for the text input. */
  inputPlaceholder?: string;
  /**
   * Optional value to pre-fill the input field (e.g. from a quick-action chip).
   * The component will populate the input but will NOT auto-submit.
   */
  prefillValue?: string;
  /**
   * Called after the component has consumed prefillValue into its input state,
   * so the parent can clear its own state and avoid re-triggering.
   */
  onPrefillConsumed?: () => void;
  /** Optional className applied to the root container element. */
  className?: string;
}

export function StreamingChat(props: StreamingChatProps): JSX.Element;
```

The component owns its internal message list state and streaming state entirely. It does not accept messages as a prop. It does not expose an imperative ref handle.

### What Stays in CandidateIntakeForm

- Thread creation (`POST /chat/threads` for intake) remains in `CandidateIntakeForm` — it is intake-specific and happens before `StreamingChat` is mounted.
- Profile completeness callbacks and step-advancement logic remain in `CandidateIntakeForm`.
- `StreamingChat` receives the already-created `threadId` as a prop.

---

## Out of Scope

- Background jobs triggered by school selection confirmation (auto-generating a study plan, fetching essay prompts from school websites). The advisor is on-demand only.
- Essay draft creation or saving from within the advisor chat. The advisor discusses essay angles conversationally; it does not create `EssayDraft` records.
- Thumbs-up / thumbs-down feedback on individual advisor messages.
- Export or PDF generation of the advisor transcript.
- Push or email notifications when the evaluation completes or when a new advisor message arrives.
- Multi-select school comparison view.
- Perplexity-backed real-time school research during advisor turns (Perplexity ran during the evaluation phase; the advisor uses the cached evaluation result).
- Any changes to the intake flow, the evaluation job, or the existing `AdmissionEvaluationReadOnly` admin component.
- The "Export full report" button in the evaluation footer (remains disabled).
- Pagination or infinite scroll of the advisor message history (all messages loaded on mount for v1).

---

## Dependencies (from BA)

- `profile.attributes.admission_evaluation_result` must be `status: complete` before school selection is available.
- `profile.attributes.school_program_selections` (from intake) seeds the primary checklist; `result.extra` provides the opt-in additions.
- `ChatThread` / `ChatMessage` / streaming endpoint — reused without structural change.
- `CandidateRepository.merge_profile_attributes` — writes `selected_schools` without a schema change.
- `StrategyDecision` model and `StrategyType.SCHOOL_SELECTION` — used for semantic persistence of the confirmed list.
- OpenAI API (OPENAI_API_KEY) — powers the `AdvisorModule` via the same DSPy LM configuration used for intake and evaluation.
- No new external services, npm packages, or Python packages are required.

---

## Output Artifacts

- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅

---

> Human checkpoint: review `02-product-spec.md`, then run `/feature-qa school-selection-advisor` to continue.
