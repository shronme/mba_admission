# Product Specification: Agent intent classification and rewrite-CV routing

## Status
COMPLETE

## Overview

This feature replaces the brittle regex-based rewrite intent and route-level full-document RAG preload with an **LLM-based intent classifier** exposed as a **fifth ReAct tool** (`classify_intent`). On each user turn, the advisor is guided (and in part enforced) to call `classify_intent` first, receive a **JSON string** with `task_kind`, `target_doc`, `emphasis`, and `prior_feedback`, then act accordingly. When `task_kind == "rewrite_cv"`, the system **must** produce CV drafts only via `rewrite_cv` (using `RewriteCVSignature` and thus preserving source content) and **must not** bypass that path with inline CV in `response` or ad-hoc `save_artifact` for `cv_draft`. The `rewrite_cv` tool and rewriter gain `prior_feedback` so curated advisor guidance is applied without dropping CV facts. The chat route’s `_retrieve_doc_snippets` no longer preloads full documents on “rewrite” regex matches; **semantic RAG (top-k) only** in that path, matching pre–regex behavior, with the agent using `get_full_document` / `rewrite_cv` when the classifier says so. ReAct’s iteration budget increases to **8** to account for the extra tool step; an additional **~300 ms** per turn is expected in production for the classifier LLM call. **No database or schema changes.**

## User stories

1. **As a** candidate who asks to update my CV in natural language (including “apply what we discussed”, pronouns, or non-English), **I want** the system to treat that as a CV rewrite **so that** the full rewriter pipeline runs and I do not get excerpt-only or inline ad-hoc CVs.

2. **As a** candidate who has received advisor tips in recent turns, **I want** those tips reflected in the rewritten CV **so that** the draft matches our conversation, not just the last user sentence.

3. **As a** user asking normal Q&A or chit-chat, **I want** the advisor to still respond helpfully without being forced into rewrite tooling **so that** simple turns remain smooth (with classifier defaulting to `qa` on errors).

4. **As an** operator / developer, **I want** `DSPY_MODE=mock` to use deterministic `MockIntentClassifier` heuristics **so that** CI and offline tests stay stable without network calls.

5. **As a** product owner, **I want** unsafe bypass of `rewrite_cv` for `cv_draft` blocked at `save_artifact` when the trajectory did not run `rewrite_cv` under `task_kind == rewrite_cv` **so that** policy is enforced even if the model drifts from prompt rules.

## Goals & success metrics

- **Goal:** CV rewrites always go through `classify_intent` → (when `rewrite_cv`) `rewrite_cv` with `prior_feedback`, preserving source coverage and incorporating recent guidance.
- **Metric:** Meets prior ≥95% structural coverage in eval harness for full-CV rewrites; manual/QA spot-checks that `prior_feedback` themes appear in drafts when present in last 10 messages.
- **Metric:** No reliance on `classify_rewrite_intent` or route-level full-doc preload; tests and observability reflect semantic-only snippet retrieval in `chat` + agent-owned full document access.

## Functional Requirements

### FR-1: Remove regex intent and route-level full-doc preload
- **Description:** Delete `app/dspy/intent.py` (`classify_rewrite_intent`, regex). Remove the `_retrieve_doc_snippets` branch in `chat.py` that preloads full tagged CV (or other full text) when regex matched. `_retrieve_doc_snippets` uses **only** semantic top-k RAG (plus existing no-API-key or other documented fallbacks), i.e. **semantic RAG only in `_retrieve_doc_snippets`**, not regex-driven full text.
- **Acceptance criteria:**
  - [ ] No import or call site of `classify_rewrite_intent` remains.
  - [ ] RAG path tests no longer expect full-text preload from the route for “rewrite” phrasing; they assert semantic snippet behavior.
  - [ ] Obsolete tests tied solely to regex preload are removed or rewritten per PM/QA.

### FR-2: `classify_intent` ReAct tool
- **Description:** New async tool in `build_agent_tools` returning a **JSON string** (see API contract) from `OpenAIIntentClassifier` (production) or `MockIntentClassifier` (mock). Inputs: at minimum `user_message` and **conversation context limited to the last 10 messages** (see FR-3). The tool does **not** receive `thread.stage`, `profile_json`, or other extended context in v1.
- **Acceptance criteria:**
  - [ ] Tool is registered as the **fifth** tool; `build_agent_tools` and pipeline unpack a **5-tuple**.
  - [ ] Return value is a string parseable as JSON with the schema in “API contract.”
  - [ ] `AgentAdvisorSignature` / RULES state that the **first** tool call on a turn should be `classify_intent`.

### FR-3: Classifier input — last 10 messages only
- **Description:** The classifier (and the `classify_intent` tool) uses **only** the last **10** messages of conversation (role/content as available) plus the current user message as appropriate. No `thread.stage`, no `profile_json`.
- **Acceptance criteria:**
  - [ ] Unit/integration tests can assert the window (e.g. 10) without leaking other context into the classifier.

### FR-4: `classify_intent` JSON output schema
- **Description:** The JSON string **must** conform to the schema defined under “API contract” (`task_kind`, `target_doc`, `emphasis`, `prior_feedback`).

### FR-5: Routing and rewriter — `task_kind == rewrite_cv`
- **Description:** When parsed `task_kind` is `rewrite_cv`, the advisor **must** call `rewrite_cv` with `target_school` (or equivalent existing parameters), `emphasis`, and `prior_feedback`, and **must not** place CV body in free-text `response` for that turn’s delivery path. **Enforcement** combines (a) **prompt RULES** in `AgentAdvisorSignature` and (b) a **`save_artifact` guard** that **rejects** persisting `cv_draft` unless a **`rewrite_cv` ran in-trajectory** for this user turn’s classification outcome (i.e. when the intended artifact is a CV draft from a rewrite, the trajectory must have executed `rewrite_cv` under the policy for this turn). Exact guard condition should match engineering: e.g. block `save_artifact` with `kind=cv_draft` if no in-trajectory `rewrite_cv` when `classify_intent` had `task_kind=rewrite_cv`, or a single agreed predicate — **reject `cv_draft` unless `rewrite_cv` ran in-trajectory** (per user answer 4b).
- **Acceptance criteria:**
  - [ ] Documented `save_artifact` behavior when guard triggers (see FR-6).
  - [ ] Integration tests: rewrite path uses `rewrite_cv` + artifact save; no successful `cv_draft` **save** without in-trajectory `rewrite_cv` when policy applies.

### FR-6: `save_artifact` guard — reject and retry behavior
- **Description:** If the model attempts `save_artifact` for **`cv_draft`** (or the canonical CV draft artifact type used by the product) **without** an in-trajectory **`rewrite_cv`** call, the **guard rejects** the operation (error or structured failure returned to the ReAct layer per existing patterns). **Retry behavior:** the agent should receive a clear signal to **call `rewrite_cv` first**, then `save_artifact` with the rewriter output (not ad-hoc body). ReAct **must** remain able to continue within the **iteration budget (8)** to recover.
- **Acceptance criteria:**
  - [ ] Test or spec trace: guard fires → model can still complete turn via `rewrite_cv` → `save_artifact` within `max_iters=8` in happy path.
  - [ ] No silent persistence of bypass CV drafts for `cv_draft`.

### FR-7: `RewriteCVSignature` and `rewrite_cv` — `prior_feedback`
- **Description:** Add `prior_feedback: str` (default `""`) to the rewrite signature and tool; `OpenAIRewriteCVModule` / `MockRewriteCVModule` accept and use it. **No hard character/token cap** on `prior_feedback` in code; size control is **prompt-instruction only** (e.g. “summarize concisely in classifier output; rewriter prioritizes `cv_text` for facts”).
- **Acceptance criteria:**
  - [ ] `prior_feedback` forwarded end-to-end in tests.
  - [ ] Docstring instructs: incorporate feedback **without** dropping source content.

### FR-8: `prior_feedback` — generation and rewriter obligations
- **Description:** **Generation:** The **intent classifier** (single LLM call in live mode) produces `prior_feedback` as a **curated bullet list** (string) of **applicable** advisor/candidate guidance extracted from the **classifier’s input window** (last 10 messages), focused on what should change tone, emphasis, or structure in the next CV — **empty** if nothing applies. **Rewriter:** `RewriteCVSignature` + module must **apply** those bullets in the rewrite (emphasis, ordering, phrasing) while **preserving** all material facts and structure required by the existing preservation rules.

### FR-9: `task_kind` taxonomy
- **Description:** `task_kind` is one of: `rewrite_cv` | `qa` | `smalltalk` | `other`. (v1 product routing for CV artifacts still only **requires** the hard `rewrite_cv` path for CV drafts; `target_doc` remains enumerated for future use.)

### FR-10: `target_doc` enumeration
- **Description:** `target_doc` remains **enumerated** with allowed values: `cv` | `life_story` | `essay` | `other` (v1 only routes/implements **CV** rewrite; other values are forward-compatible, not new rewriters in this feature).

### FR-11: Classifier failure / timeout — operational behavior
- **Description:** On classifier **error**, **timeout**, or **invalid JSON** from the tool: **log** the failure, **return** a safe default with **`task_kind=qa`** (and sensible empty/minimal other fields) so the user still gets a normal answer path. (Matches user answer 6b: fallback to QA.)
- **Acceptance criteria:**
  - [ ] Tests or docs for fallback path; logs include enough context to debug without leaking PII inappropriately (follow existing logging norms).

### FR-12: `MockIntentClassifier` (mock mode)
- **Description:** In `DSPY_MODE=mock`, use **deterministic keyword heuristics** that cover **all four** `task_kind` values (`rewrite_cv`, `qa`, `smalltalk`, `other`) so tests are offline and stable. Mocks for agent and rewriter **maintain tool parity** (five tools) with production wiring.
- **Acceptance criteria:**
  - [ ] No network in mock tests for classifier; deterministic mapping documented briefly in code or tests.
  - [ ] At least one test path per `task_kind` for mock classifier (or table-driven).

### FR-13: ReAct iteration budget
- **Description:** Set ReAct `max_iters` to **8** (from 6) to absorb `classify_intent` and occasional guard/retry. Expected **extra latency** ~**300 ms** per turn in production due to the classifier LLM (on top of existing chat latency).

## Non-Functional Requirements

- **Performance:** Add ~one LLM call per user turn for classification in non-mock mode; **~300 ms** median budget acceptable. `max_iters=8` upper bound on tool loops; monitor p95 ReAct step counts after rollout.
- **Reliability:** Classifier failures degrade to **QA** mode with logging, not user-visible hard failure (unless the platform already surfaces a generic error — align with existing chat error handling).
- **Security / privacy:** Classifier only sees the same conversation slice as provided (10 messages); no new PII in logs beyond existing practices.
- **Testability / mock:** Deterministic mock classifiers; five-tool parity in `MockAgentAdvisorModule` vs `AgentAdvisorModule`.
- **Scope:** **Backend only**; no DB migrations; no frontend changes in this spec.

## UX flows (user-visible, backend-shaping)

### Flow 1: User requests CV rewrite
1. User sends a message (any phrasing, including follow-up to prior advice).
2. Advisor ReAct calls **`classify_intent`** first → JSON with `task_kind: "rewrite_cv"`, `target_doc: "cv"`, `emphasis`, `prior_feedback` (bulleted).
3. Agent calls **`rewrite_cv`** (and **`get_full_document`** / other tools as per existing rules if needed for full CV).
4. User sees the assistant’s narrative **without** a pasted full CV in the main reply if policy forbids it; the **artifact** is produced via `save_artifact` from rewriter output. If the model tries to skip `rewrite_cv` and `save_artifact` `cv_draft`, **guard blocks** and the agent retries within the loop.
5. User downloads or views CV draft as today (downstream unchanged).

### Flow 2: Q&A or smalltalk
1. `classify_intent` returns `qa`, `smalltalk`, or `other` as appropriate.
2. No forced `rewrite_cv`; normal answering. No `save_artifact` guard issue for `cv_draft` unless the model incorrectly attempts a CV save.

### Flow 3: Classifier hiccup
1. Classifier times out or returns bad JSON.
2. System logs, defaults to **QA**-style behavior so the user still gets a coherent reply.

## API contract

### `classify_intent` tool
- **Inputs:** `user_message` (string), `conversation_history` (structured per existing agent conventions), implementing **only the last 10 messages** in the **history** passed for classification.
- **Output:** **JSON string** with the following object (parseable with standard JSON; field names exact):

| Field | Type | Allowed values / notes |
|-------|------|-------------------------|
| `task_kind` | string | `rewrite_cv` \| `qa` \| `smalltalk` \| `other` |
| `target_doc` | string | `cv` \| `life_story` \| `essay` \| `other` (v1 behavior only for `cv` rewrite routing) |
| `emphasis` | string | Short free text; one-sentence style hint from latest user + recent turns. |
| `prior_feedback` | string | Curated **bullet** lines (e.g. `- item`) of applicable guidance from the window, or `""` if none. **No** hard max length in code; prompt instructs concision. |

**Example (illustrative):**

```json
{
  "task_kind": "rewrite_cv",
  "target_doc": "cv",
  "emphasis": "Lead with cross-border M&A and quantify deal outcomes.",
  "prior_feedback": "- Emphasize cross-border transactions\n- Quantify venture outcomes where possible\n- Build narrative around operator-founder arc"
}
```

### `rewrite_cv` tool
- **Additional parameter:** `prior_feedback: str = \"\"` forwarded into `RewriteCVSignature` / modules.

### `save_artifact` (behavior change)
- **Guard:** Reject `cv_draft` (or product’s CV draft type) when **no in-trajectory `rewrite_cv`** in the current ReAct run’s policy; return an error/structured result that allows the model to call `rewrite_cv` then retry `save_artifact` within `max_iters=8`.

### HTTP routes
- **No** new public REST endpoints required for v1. **`/chat/.../stream`** behavior change is internal: `_retrieve_doc_snippets` = semantic RAG only, no regex full-doc branch.

## Data model changes
**None** (no new tables, columns, or migrations). State in ReAct/trajectory is **ephemeral**; no durable `task_kind` store required for v1.

## Out of scope
- Essay / life-story / SOP / recommendation rewriters; implementing rewrite flows for `target_doc` other than `cv` beyond **enumeration** in JSON.
- Reintroducing **any** regex fast-path for intent or preload.
- PDF/DOCX renderer, chunker, `UploadedFileRepository` contract, or DB schema changes.
- Frontend or Alembic migrations.
- Hard **code-level** cap on `prior_feedback` length (prompt-only).
- `thread.stage` / `profile_json` in classifier v1.

## Open questions
- **Minimal:** Exact error surface for `save_artifact` guard (string format vs. structured) — align with existing `save_artifact` and ReAct error handling in code review.
- **Policy nuance:** Whether `get_full_document` is **mandated** in RULES for every `rewrite_cv` or only when snippets insufficient — can be **implementation** detail as long as coverage and user stories hold.

## Dependencies (from BA)
- Internal: `dspy`, `build_agent_tools`, `AgentAdvisorModule`, `pipeline`, `chat._retrieve_doc_snippets`, `UploadedFileRepository` (unchanged), full-doc and `rewrite_cv` from prior RAG work.
- External: OpenAI (or configured DSPy LM) for `OpenAIIntentClassifier` in non-mock mode.

## Output Artifacts
- `01-ba-analysis.md` ✅
- `02-product-spec.md` ✅

> Human checkpoint: review `02-product-spec.md`, then run `/feature-qa` to continue.

