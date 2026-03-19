
# AI Admissions Platform — Detailed Engineering Backlog v2
## Python/FastAPI + Celery/Redis + DSPy

## Purpose

This document updates the implementation plan to use:

- **Backend:** Python + FastAPI
- **Async execution:** Celery + Redis
- **LLM orchestration:** DSPy instead of ad hoc prompt strings
- **Frontend:** Web app
- **Scope:** Graduate admissions first, AI-only
- **Architecture style:** agent-based, but implemented as explicit services/modules, not vague autonomous agents

This is meant to be actionable for engineering work.

---

# 1. Updated Technical Stack

## Frontend
- Next.js
- TypeScript
- Tailwind
- TanStack Query

## Backend
- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x or SQLModel
- Alembic
- PostgreSQL
- Redis
- Celery

## AI / LLM Layer
- DSPy
- OpenAI or Anthropic as model providers
- structured outputs validated with Pydantic
- evaluation harness for classifier / profile / strategy / essay quality

## Storage
- S3 / GCS compatible object storage for uploaded files

## Testing
- pytest
- pytest-asyncio
- httpx test client
- fixture-based eval tests
- optional snapshot tests for DSPy outputs

---

# 2. Updated Repository Structure

```text
ai_admissions/
  apps/
    web/
      src/
        app/
        components/
        features/
          chat/
          profile/
          strategy/
          tasks/
          essays/
  services/
    api/
      app/
        main.py
        core/
          config.py
          logging.py
          security.py
          celery_app.py
          redis.py
          db.py
        api/
          routes/
            chat.py
            candidates.py
            profile.py
            strategy.py
            tasks.py
            essays.py
            files.py
        models/
        schemas/
        repositories/
        services/
          orchestration/
          intent/
          profile/
          strategy/
          task_engine/
          essay_review/
          file_ingestion/
          audit/
        dspy_modules/
          intent/
          profile/
          strategy/
          tasks/
          essays/
        workers/
          tasks/
        tests/
  packages/
    shared_schemas/
    evals/
    docs/
      product/
      engineering/
```

---

# 3. Architecture Principles

1. **FastAPI handles synchronous API orchestration and short tasks.**
2. **Celery handles long-running or retryable workloads**, especially:
   - LLM calls
   - document parsing
   - profile extraction
   - strategy generation
   - essay review
3. **Redis is used for Celery broker/result backend and short-lived orchestration state.**
4. **DSPy modules replace free-form prompt files** for core intelligence paths.
5. **Pydantic schemas define all boundaries** between API, services, DSPy modules, and DB writebacks.
6. **Every AI action must persist an execution record** for auditability.

---

# 4. What Changes Because of DSPy

Instead of treating prompts as static text templates, the system should treat each AI capability as a **typed DSPy program**.

## Examples
- intent classification becomes a DSPy classifier module
- profile extraction becomes a DSPy extraction module
- strategy generation becomes a DSPy reasoning module
- task generation becomes a DSPy planning module
- essay review becomes a DSPy critique module

## Implications
- each module needs:
  - input schema
  - output schema
  - DSPy signature
  - examples / few-shots / training set
  - evaluation function
- prompts are no longer the main product artifact
- the main product artifact becomes:
  - DSPy signatures
  - module code
  - training examples
  - evaluation datasets
  - optimization scripts

---

# 5. Updated Build Order

## Phase A — Platform foundations
1. FastAPI service skeleton
2. PostgreSQL schema + Alembic
3. Redis + Celery wiring
4. Pydantic boundary schemas
5. audit/event logging
6. file upload pipeline

## Phase B — AI runtime foundations
7. DSPy runtime config
8. model adapter layer
9. execution wrapper for DSPy modules
10. module registry
11. eval harness

## Phase C — Core product intelligence
12. deterministic pre-router
13. DSPy intent classifier
14. hybrid arbitration
15. orchestration service
16. profile extraction module
17. profile update module
18. strategy module
19. task generation module
20. essay review module

## Phase D — Web app integration
21. chat UI
22. profile panel
23. strategy panel
24. task list
25. essay review experience

---

# 6. Celery Task Boundaries

Use Celery only where latency/retries/background execution are genuinely useful.

## Good Celery candidates
- parse uploaded CV / PDF / DOCX
- run profile extraction on uploaded data
- run strategy generation
- run essay review on long drafts
- run school comparison if it becomes retrieval-heavy
- run offline eval jobs

## Keep synchronous in FastAPI
- saving chat messages
- loading candidate state
- deterministic intent pre-routing
- returning existing profile/task data
- short orchestration decisions

## Rule of thumb
If it may take more than a few seconds, call an external LLM, or benefit from retries, put it behind Celery.

---

# 7. Updated Domain Model

## candidate
Primary applicant object.

## candidate_profile
Versioned normalized profile.

## chat_thread / chat_message
Conversation state.

## uploaded_file
Source documents with extracted text.

## strategy_decision
Versioned strategy outputs.

## task_item
Action plan items.

## essay_draft / essay_review
Essay workflow objects.

## ai_run
Execution record for DSPy/Celery/LLM runs.

## audit_event
Business-level state changes.

---

# 8. Updated Detailed Tasks

---

## TASK 001 — Create Python backend skeleton with FastAPI, Celery, Redis, and Postgres wiring

### Goal
Create the initial backend skeleton with clean separation between API routes, services, workers, schemas, and DSPy modules.

### Deliverables
- FastAPI app skeleton
- health endpoint
- config management
- Celery app wiring
- Redis config
- Postgres connection setup
- dev docker-compose for postgres + redis
- base logging

### Suggested structure
- `app/main.py`
- `app/core/config.py`
- `app/core/db.py`
- `app/core/celery_app.py`
- `app/api/routes/`
- `app/services/`
- `app/dspy_modules/`
- `app/workers/tasks/`

### Acceptance criteria
- FastAPI boots locally
- `/health` returns OK
- Celery worker starts successfully
- Redis broker is connected
- DB session can initialize
- docker-compose can start local dependencies

### Cursor prompt
```text
Create a production-oriented Python backend skeleton for an AI admissions platform.

Requirements:
1. Use FastAPI for the HTTP API.
2. Use Celery with Redis for background jobs.
3. Use PostgreSQL as the primary database.
4. Add docker-compose for local postgres and redis.
5. Add environment-based settings using pydantic-settings.
6. Create the following structure:
   - app/main.py
   - app/core/config.py
   - app/core/db.py
   - app/core/celery_app.py
   - app/api/routes/
   - app/services/
   - app/dspy_modules/
   - app/workers/tasks/
7. Add a /health endpoint.
8. Add basic structured logging.
9. Keep the codebase clean and modular.

Return:
- file tree
- contents of key files
- dependencies list
- run commands
```

---

## TASK 002 — Implement SQLAlchemy models, Alembic migrations, and repository foundations

### Goal
Define the persistence layer for candidates, profiles, chats, files, strategy, tasks, essays, AI runs, and audit events.

### Deliverables
- SQLAlchemy models
- Alembic initial migration
- repository base classes or focused repositories
- seed script

### Acceptance criteria
- migration runs cleanly
- seed script creates one realistic candidate
- relationships work for profile, tasks, files, messages

### Cursor prompt
```text
Implement the initial persistence layer for an AI admissions platform using:
- SQLAlchemy 2.x
- Alembic
- PostgreSQL

Entities needed:
- candidate
- candidate_profile
- chat_thread
- chat_message
- uploaded_file
- strategy_decision
- task_item
- essay_draft
- essay_review
- ai_run
- audit_event

Requirements:
1. Use JSONB where flexibility is useful.
2. Add created_at / updated_at as appropriate.
3. Add indexes on common lookup fields.
4. Add enums for statuses and strategy types.
5. Create an Alembic migration.
6. Add a seed script with one Grad candidate and related records.
7. Add repository classes or repository functions for common reads/writes.

Return:
- models
- migration
- seed code
- repository layer
```

---

## TASK 003 — Build Celery execution framework for AI jobs

### Goal
Create a reusable job framework for background AI work.

### Why this matters
LLM/DSPy operations should not be mixed directly into request/response code when they can run long, fail intermittently, or need retries.

### Deliverables
- Celery task base class
- retry policy
- typed task payloads
- job status model
- helper for creating `ai_run` records
- idempotency strategy

### Acceptance criteria
- Celery task can be queued from FastAPI
- task can update DB status
- retries work for transient failures
- task execution is logged

### Cursor prompt
```text
Implement a reusable Celery execution framework for AI jobs in a FastAPI backend.

Requirements:
1. Create a Celery base task with:
   - common logging
   - retry handling
   - correlation id support
2. Define a pattern for typed task payloads using Pydantic.
3. Add a helper that creates and updates ai_run records in Postgres.
4. Add a sample background task that sleeps and updates status.
5. Design for future tasks like:
   - profile extraction
   - strategy generation
   - essay review
6. Include notes on idempotency and safe retries.

Return:
- Celery code
- sample task
- DB integration helpers
- design explanation
```

---

## TASK 004 — Implement DSPy runtime configuration and model adapter layer

### Goal
Set up DSPy as the core AI programming framework.

### Deliverables
- DSPy initialization module
- provider config for OpenAI/Anthropic
- shared helper for invoking DSPy modules
- structured logging for model name, latency, token use if available

### Implementation notes
- keep provider setup centralized
- do not scatter model configuration across services
- allow different modules to use different models later

### Acceptance criteria
- one sample DSPy module runs successfully
- provider can be configured via env
- execution metadata is logged

### Cursor prompt
```text
Set up DSPy in a Python FastAPI backend as the main LLM programming layer.

Requirements:
1. Create a central DSPy runtime configuration module.
2. Support provider configuration via environment variables.
3. Make it possible to switch model/provider centrally.
4. Add an execution wrapper that logs:
   - module name
   - model
   - latency
   - success/failure
5. Include one minimal sample DSPy module and invocation example.

Return:
- DSPy runtime code
- config module
- sample module
- sample usage
```

---

## TASK 005 — Define Pydantic contracts for intent classification and routing

### Goal
Lock the routing contract before implementing modules.

### Required output shape
- primary_intent
- secondary_flags
- confidence
- reasoning
- recommended_agent
- requires_clarification

### Acceptance criteria
- schemas are strict
- enums are centralized
- contract is reusable across API, services, and tests

### Cursor prompt
```text
Define strict Pydantic schemas and enums for intent classification and routing.

Requirements:
1. Create enums for all top-level intents and secondary flags.
2. Create a Pydantic model for classifier output with fields:
   - primary_intent
   - secondary_flags
   - confidence
   - reasoning
   - recommended_agent
   - requires_clarification
3. Add docstrings or comments describing each intent.
4. Export this contract for use across services and tests.

Return:
- schema code
- enum code
- one example payload
```

---

## TASK 006 — Build deterministic pre-router in Python

### Goal
Handle obvious intent cases cheaply and consistently before DSPy classification.

### Required rules
- CV upload / intake
- essay review request
- school comparison request
- task request
- profile update request
- unsupported full-essay-writing request

### Acceptance criteria
- at least 15 rules
- rules are explicit objects/classes
- rules are unit-tested

### Cursor prompt
```text
Implement a deterministic intent pre-router in Python for an AI admissions platform.

Requirements:
1. Do not use a giant if/elif chain.
2. Implement explicit rule objects or strategy classes.
3. Each rule should support:
   - id
   - description
   - match(message, context)
   - output
4. Output can be:
   - hard route
   - soft hint
   - no match
5. Add at least 15 rules for common admissions-product actions.
6. Add pytest tests with realistic messages.

Return:
- rule engine
- rules
- tests
```

---

## TASK 007 — Implement DSPy intent classifier module

### Goal
Replace prompt-only classification with a typed DSPy module.

### Inputs
- latest user message
- recent thread summary
- candidate summary
- deterministic hints

### Outputs
- classifier result matching Pydantic contract

### Acceptance criteria
- output parses into Pydantic model
- invalid outputs are retried or rejected cleanly
- execution metadata is recorded

### Cursor prompt
```text
Implement the DSPy-based intent classifier module.

Requirements:
1. Use DSPy, not a raw prompt string in service code.
2. Inputs:
   - latest_user_message
   - recent_thread_summary
   - candidate_summary
   - deterministic_hints
3. Output must parse into the existing Pydantic classifier model.
4. Add an execution wrapper so the module run is logged to ai_run.
5. Add one success test and one low-confidence ambiguity test.
6. Keep the module narrow: it classifies only, it does not answer the user.

Return:
- DSPy signature/module
- service wrapper
- tests
```

---

## TASK 008 — Implement hybrid arbitration service

### Goal
Combine deterministic rules and DSPy classification safely.

### Decision policy
1. hard deterministic route wins
2. soft hints are passed into DSPy classifier
3. low confidence yields clarification
4. unsupported essay ghostwriting routes to safe editing path

### Acceptance criteria
- final routing decision is explicit
- raw classifier output is preserved
- arbitration is tested

### Cursor prompt
```text
Implement a hybrid arbitration service for routing user messages.

Inputs:
- deterministic pre-router result
- DSPy classifier result

Decision policy:
1. hard deterministic route wins
2. soft hints influence DSPy result
3. low-confidence DSPy result sets requires_clarification=true
4. unsupported essay ghostwriting routes to a safe path

Requirements:
- persist raw classifier output and final routing decision separately
- add tests for at least 6 scenarios
- keep the service easy to extend

Return:
- arbitration service
- tests
- short design explanation
```

---

## TASK 009 — Build FastAPI orchestration endpoint and service

### Goal
Create the main `/chat` flow that stores the message, routes it, and triggers the correct downstream action.

### Deliverables
- POST `/chat`
- orchestration service
- synchronous path for short operations
- Celery enqueue path for long operations
- response payload contract

### Important behavior
- save user message immediately
- return quickly if work is delegated to Celery
- expose job id / status for background tasks
- refresh structured state after completion

### Acceptance criteria
- chat endpoint works end-to-end
- can return immediate response or queued job
- orchestration is modular

### Cursor prompt
```text
Implement the FastAPI /chat endpoint and orchestration service.

Requirements:
1. Accept:
   - candidate_id
   - thread_id
   - message
   - optional file ids
2. Persist the message immediately.
3. Run deterministic routing + DSPy classification.
4. Decide whether the requested work should be:
   - executed inline
   - queued to Celery
5. Return a response payload that supports both:
   - immediate assistant response
   - queued background job with job_id/status
6. Keep orchestration logic in services, not route handlers.

Return:
- route code
- orchestration service
- response schemas
- one example request/response
```

---

## TASK 010 — Design normalized candidate profile schema with provenance

### Goal
Store candidate information in a way that separates facts, inferences, and unknowns.

### Required sections
- academics
- test scores
- work experience
- leadership/impact
- extracurriculars
- goals
- motivations
- risks
- contradictions
- unknowns
- evidence map

### Acceptance criteria
- Pydantic schema exists
- provenance is explicit
- example profile included

### Cursor prompt
```text
Design a strict normalized candidate profile schema for graduate admissions using Pydantic.

Requirements:
1. Separate:
   - extracted facts
   - inferred assessments
   - contradictions
   - unknowns
2. Include provenance/evidence metadata for important facts.
3. Support these sections:
   - academics
   - test scores
   - work experience
   - leadership/impact
   - extracurriculars
   - goals
   - motivations
   - risks
4. Include one realistic example profile payload.
5. Keep the schema suitable for both DB storage and API responses.

Return:
- Pydantic models
- example payload
- design notes
```

---

## TASK 011 — Build file ingestion + text extraction pipeline

### Goal
Ingest uploaded files and extract text for downstream DSPy modules.

### Supported types
- pdf
- docx
- txt

### Deliverables
- upload metadata model
- extracted text persistence
- file type classification heuristic
- Celery task for heavy parsing

### Acceptance criteria
- uploaded CV becomes stored file + extracted text
- extraction failures are recoverable
- file classification is available to orchestration

### Cursor prompt
```text
Implement the file ingestion pipeline for a FastAPI + Celery backend.

Requirements:
1. Support:
   - pdf
   - docx
   - txt
2. Store file metadata in Postgres.
3. Store file bytes in object storage or a storage abstraction.
4. Extract text and persist it.
5. Classify file type as:
   - cv
   - transcript
   - test_score
   - essay
   - other
6. Use Celery for heavy parsing/extraction.
7. Expose a normalized file object for downstream modules.

Return:
- ingestion service
- Celery extraction task
- storage abstraction
- example normalized output
```

---

## TASK 012 — Implement DSPy profile extraction module

### Goal
Produce the first normalized candidate profile from uploaded materials and chat context.

### Inputs
- CV text
- transcript/test score text if available
- user self-description
- existing profile if any

### Outputs
- normalized profile
- gaps
- contradictions
- follow-up questions
- confidence by section

### Execution mode
Run via Celery.

### Acceptance criteria
- output parses into profile schema
- job result is persisted
- user can later fetch updated profile

### Cursor prompt
```text
Implement the DSPy profile extraction module for graduate admissions.

Inputs:
- cv_text
- optional transcript_text
- optional test_score_text
- user_context
- existing_profile

Outputs:
- normalized_profile
- unknowns/gaps
- contradictions
- followup_questions
- confidence_by_section

Requirements:
1. Use DSPy, not raw inline prompt strings.
2. Output must parse into Pydantic models.
3. Execute this module through Celery because it may be slow.
4. Persist:
   - ai_run
   - candidate_profile version
   - audit event
5. Return a concise user-facing summary as part of the job result.

Return:
- DSPy module
- service wrapper
- Celery task
- tests
```

---

## TASK 013 — Implement profile patch/update module

### Goal
Support incremental profile updates from chat messages.

### Example updates
- new GRE score
- corrected work history
- changed goals
- added leadership evidence

### Acceptance criteria
- update produces patch, not full regeneration
- contradictions are preserved
- audit events are written

### Cursor prompt
```text
Implement a profile update module that generates minimal profile patches from new user messages.

Requirements:
1. Input:
   - latest user message
   - existing normalized profile
2. Output:
   - profile_patch
   - new_unknowns
   - contradictions
   - followup questions if needed
3. Do not regenerate the entire profile unnecessarily.
4. Preserve contradictions instead of silently overwriting.
5. Persist an audit trail.

Use DSPy for the intelligence step, but keep patch application deterministic in Python.

Return:
- DSPy module
- patch schema
- patch application service
- tests
```

---

## TASK 014 — Define strategy schema and reasoning rubric

### Goal
Specify the exact output contract for strategy decisions.

### Required fields
- strategy_type
- rationale
- supporting_evidence
- risks
- evidence_gaps
- alternatives_considered
- next_actions
- confidence_score
- school_band_implication

### Acceptance criteria
- Pydantic model exists
- rubric doc exists
- examples cover upgrade/pivot/hybrid

### Cursor prompt
```text
Define the strategy decision schema and rubric for graduate admissions.

Requirements:
1. Support strategy types:
   - upgrade
   - pivot
   - hybrid
   - undetermined
2. Fields must include:
   - rationale
   - supporting_evidence
   - risks
   - evidence_gaps
   - alternatives_considered
   - next_actions
   - confidence_score
   - school_band_implication
3. Add a rubric explaining how to distinguish strategy types credibly.
4. Include example outputs for:
   - strong upgrade
   - credible hybrid
   - weak pivot

Return:
- Pydantic models
- rubric markdown
- example payloads
```

---

## TASK 015 — Implement DSPy strategy module

### Goal
Generate candidate positioning strategy from profile evidence.

### Execution mode
Run via Celery.

### Acceptance criteria
- strategy output parses into schema
- weak evidence is called out explicitly
- chosen strategy is compared against alternatives

### Cursor prompt
```text
Implement the DSPy strategy module for a graduate admissions platform.

Inputs:
- normalized candidate profile
- recent goals/motivations
- recent chat summary
- optional school preferences

Outputs:
- structured strategy decision
- user-facing explanation

Requirements:
1. Use DSPy.
2. Make the reasoning candidate-specific, not generic.
3. Explicitly compare the chosen strategy to at least one alternative.
4. Identify evidence gaps and risks clearly.
5. Run this as a Celery task.
6. Persist ai_run, strategy_decision, and audit_event.

Return:
- DSPy module
- service wrapper
- Celery task
- tests for at least 2 profiles
```

---

## TASK 016 — Define task schema and actionability rules

### Goal
Prevent vague tasks and ensure the system generates usable action items.

### Task categories
- profile completion
- evidence gathering
- narrative clarification
- school research
- essay drafting
- recommender prep
- logistics

### Acceptance criteria
- every task begins with an action
- vague tasks are disallowed by policy/examples
- examples included

### Cursor prompt
```text
Define the task schema and generation policy for the admissions platform.

Requirements:
1. Task fields:
   - category
   - title
   - description
   - priority
   - reasoning
   - due suggestion
   - related_gap_or_risk
2. Add a policy that rejects vague tasks like:
   - improve profile
   - make story better
3. Include at least 12 example tasks.
4. Use Pydantic models.

Return:
- schema
- markdown policy
- example payloads
```

---

## TASK 017 — Implement DSPy task generation module

### Goal
Translate current profile + strategy + open tasks into a concrete plan.

### Acceptance criteria
- tasks are specific
- duplicates are avoided
- tasks map to real gaps/risks/milestones

### Cursor prompt
```text
Implement the DSPy task generation module.

Inputs:
- normalized profile
- current strategy decision
- open tasks
- latest user message

Outputs:
- tasks_to_create
- tasks_to_update
- tasks_to_archive
- rationale

Requirements:
1. Use DSPy for the planning step.
2. Add deterministic duplicate detection in Python.
3. Make every task specific and user-executable.
4. Tie tasks to real profile gaps, strategy risks, or milestones.
5. Persist changes to task_item records and audit events.

Return:
- DSPy module
- service wrapper
- duplicate detection logic
- tests
```

---

## TASK 018 — Define essay review schema, rubric, and boundary policy

### Goal
Set clear review behavior and safe limits.

### Review dimensions
- authenticity
- clarity
- specificity
- coherence
- credibility
- prompt fit
- distinctiveness

### Acceptance criteria
- schema exists
- rubric exists
- safe boundary policy exists

### Cursor prompt
```text
Define the essay review schema, rubric, and editing boundary policy.

Requirements:
1. Review dimensions:
   - authenticity
   - clarity
   - specificity
   - coherence
   - credibility
   - prompt_fit
   - distinctiveness
2. Output fields:
   - strengths
   - weaknesses
   - rubric_scores
   - revision_priorities
   - suggested_edits
   - revision_plan
3. Add a boundary policy:
   - default mode is reviewer/editor
   - full ghostwritten final essay is not the default
4. Include 2 example review payloads.

Return:
- Pydantic models
- rubric markdown
- policy markdown
- example payloads
```

---

## TASK 019 — Implement DSPy essay review module with Celery execution

### Goal
Review essays asynchronously and return structured feedback.

### Acceptance criteria
- review output parses cleanly
- limited rewrite suggestions are allowed
- unsupported full-writing requests route safely

### Cursor prompt
```text
Implement the DSPy essay review module.

Inputs:
- essay_draft
- optional school prompt
- profile summary
- current strategy decision

Outputs:
- structured essay review
- user-facing feedback
- optional limited rewrite suggestions

Requirements:
1. Use DSPy.
2. Execute through Celery.
3. Keep the default mode as reviewer/editor, not ghostwriter.
4. Return structured output validated by Pydantic.
5. Persist essay_review, ai_run, and audit_event.
6. Add one normal review test and one boundary/safe-path test.

Return:
- DSPy module
- service wrapper
- Celery task
- tests
```

---

## TASK 020 — Build evaluation harness for DSPy modules

### Goal
Make module quality measurable from the beginning.

### Initial eval targets
- intent classification accuracy
- profile extraction completeness / correctness
- strategy quality rubric
- task usefulness
- essay review quality

### Acceptance criteria
- eval dataset format defined
- at least one eval script exists
- DSPy modules can be run against fixtures

### Cursor prompt
```text
Build an evaluation harness for DSPy modules in the admissions platform.

Requirements:
1. Support evals for:
   - intent classifier
   - profile extraction
   - strategy module
   - task generation
   - essay review
2. Define a fixture format for test cases.
3. Add at least one runnable eval script.
4. Make the harness easy to extend as more labeled examples are added.
5. Include notes on how DSPy optimization/training could be layered on later.

Return:
- eval structure
- fixture format
- sample eval script
- usage notes
```

---

## TASK 021 — Build minimal web app flow against FastAPI backend

### Goal
Provide a usable internal alpha.

### Required UI
- chat
- CV upload
- profile panel
- strategy panel
- task list
- job status polling for Celery work

### Acceptance criteria
- user can upload CV
- background extraction job starts
- profile appears after completion
- strategy can be requested
- tasks appear
- UI polls job status cleanly

### Cursor prompt
```text
Build the initial web app flow for the AI admissions platform.

Requirements:
1. Use Next.js + TypeScript.
2. Integrate with the FastAPI backend.
3. Support:
   - sending chat messages
   - uploading CV files
   - polling Celery-backed job status
   - showing profile panel
   - showing strategy summary
   - showing tasks
4. Keep the UI clean and modular.
5. Design around asynchronous background jobs for AI work.

Return:
- component structure
- API integration layer
- polling approach
- implementation code
```

---

# 9. DSPy-Specific Engineering Notes

## 9.1 Do not store “prompts” as the main artifact
Instead store:
- DSPy module code
- signatures
- examples
- eval fixtures
- optimization scripts

## 9.2 Separate deterministic code from model reasoning
Use plain Python for:
- arbitration
- patch application
- deduplication
- business rules
- DB writebacks

Use DSPy for:
- classification
- extraction
- reasoning
- critique
- planning

## 9.3 Add module wrappers
Each DSPy module should have a wrapper service responsible for:
- schema validation
- ai_run logging
- exception handling
- DB writebacks
- Celery compatibility

---

# 10. Immediate Sprint Recommendation

## Sprint 1
- Task 001 backend skeleton
- Task 002 persistence
- Task 003 Celery framework
- Task 004 DSPy runtime
- Task 005 routing contracts
- Task 006 pre-router
- Task 007 DSPy intent classifier
- Task 008 arbitration
- Task 009 chat orchestration

## Sprint 2
- Task 010 profile schema
- Task 011 file ingestion
- Task 012 profile extraction
- Task 013 profile patching
- Task 014 strategy schema
- Task 015 strategy module

## Sprint 3
- Task 016 task schema
- Task 017 task generator
- Task 018 essay rubric
- Task 019 essay review
- Task 020 eval harness
- Task 021 frontend alpha

---

# 11. What to Build First This Week

Build this thin vertical slice:

1. FastAPI backend skeleton
2. Postgres + Alembic
3. Redis + Celery wiring
4. DSPy runtime wrapper
5. deterministic pre-router
6. DSPy intent classifier
7. hybrid arbitration
8. `/chat` orchestration
9. file upload + extraction job
10. profile extraction job
11. simple UI that shows job progress and resulting profile

That gets you a real working backbone aligned with your preferred architecture.

---
