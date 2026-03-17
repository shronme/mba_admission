# AI Admissions OS Validation Spec → Development Plan

## Planning Principles
- Build vertical slices that can be demoed and validated at the end of each epic.
- Keep AI behavior observable (reasoning summaries, logs, confidence/risk signals).
- Treat privacy, multilingual support, and low latency as first-class constraints from setup onward.

---

## Phase 0 — Initial Setup: Tech Stack & Deployment Infrastructure

### Objective
Establish a production-ready engineering foundation for secure, scalable delivery of an AI-native admissions platform.

### Proposed Tech Stack
- **Frontend:** Next.js (TypeScript), Tailwind CSS, component library (shadcn/ui or similar).
- **Backend/API:** Python FastAPI service (orchestrator + domain services), OpenAPI contracts.
- **AI/LLM Layer:** Provider abstraction supporting OpenAI/Anthropic, with prompt/version registry.
- **Data Layer:** PostgreSQL (structured data), Redis (cache/queues), object storage (S3-compatible) for documents.
- **Search/Retrieval:** pgvector or dedicated vector store for memory + retrieval.
- **Async Processing:** Celery/RQ workers with Redis broker for ingestion, extraction, essay diffing, research jobs.
- **Auth & Access:** OAuth/email auth with RBAC (candidate, consultant, admin).
- **Observability:** OpenTelemetry, centralized logs, metrics (Prometheus/Grafana), error tracking (Sentry).
- **Infra:** Docker + Terraform, Kubernetes (or ECS) deployment, managed DB/storage, CDN for frontend.
- **CI/CD:** GitHub Actions for lint/test/build/security scans + staged deploys.

### Deployment Recommendation (including Railway)
- **Short answer:** Yes—Railway can be a strong fit for an MVP and early beta of this product.
- **Use Railway for:**
  - Fast setup of API + worker + Postgres + Redis with low DevOps overhead.
  - Early-stage staging/production where speed of iteration matters more than deep infra customization.
  - Small teams validating product-market fit before scaling complexity.
- **Watchouts for Railway at scale:**
  - Less control over advanced networking/compliance patterns than self-managed Kubernetes.
  - Potential constraints for strict enterprise security controls and complex multi-region topologies.
  - Costs may become less predictable as workload and background jobs grow.
- **Recommended path:**
  1. Start with Railway through Epics 0–4.
  2. Reassess at Epic 5/6 using production metrics (latency, queue depth, uptime, cost per active candidate).
  3. Migrate selectively to Kubernetes/ECS only if scale/compliance requirements justify the operational overhead.

### Core Infrastructure Workstreams
1. Monorepo/project scaffolding (frontend, backend, workers, infra).
2. Environments: local, staging, production with secrets management.
3. Baseline data schema and migration pipeline.
4. Document storage pipeline and signed URL upload flow.
5. API gateway/routing, auth bootstrap, and role model.
6. Logging/tracing/monitoring dashboards and alerting.
7. Security baseline (encryption at rest/in transit, audit logs, PII redaction).
8. Deployment platform decision record (Railway-first vs Kubernetes/ECS) with exit criteria.

### User Stories
- **US0.1** As an engineer, I can run the full stack locally with one command so onboarding takes under 30 minutes.
- **US0.2** As a DevOps owner, I can deploy backend/frontend to staging from main branch automatically.
- **US0.3** As a security officer, I can verify encryption, access control, and audit logging are enabled.
- **US0.4** As a product manager, I can access staging and run a smoke journey (login → upload → chat).
- **US0.5** As an engineering lead, I can review a documented Railway viability decision with measurable migration triggers.

### Testable Deliverable
- **Deliverable:** “Platform Foundation Demo” in staging.
- **Validation checklist:**
  - A reviewer can open the app, authenticate, upload a file, send a chat message, and see persisted logs.
  - CI pipeline passes and deploys a tagged build to staging.
  - Monitoring dashboard shows request latency/error rate for backend endpoints.
  - Deployment ADR documents why Railway is or is not selected, with explicit scale/compliance exit criteria.

---

## Epic 1 — Candidate Intake & Profile Structuring

### Objective
Transform unstructured candidate input (files + free text) into a normalized, gap-aware candidate profile.

### Scope
- Intake UI for CV/transcript/essay uploads and free-text goals.
- Multi-language input handling and normalization.
- Structured extraction for academics, experience, activities, strengths/weaknesses.
- Gap detection (missing metrics, incomplete timeline, unclear goals).
- Candidate profile persistence and editable profile view.

### User Stories
- **US1.1** As a candidate, I can upload key documents and provide goals in chat or forms.
- **US1.2** As a candidate, I receive a structured profile summary generated from my inputs.
- **US1.3** As a candidate, I can see what information is missing and what to add next.
- **US1.4** As a consultant, I can review and correct extracted profile fields.

### Testable Deliverable
- **Deliverable:** “Structured Profile v1”.
- **Validation checklist:**
  - Uploading sample CV + transcript generates structured JSON/profile view.
  - System flags at least 3 categories of missing/low-confidence data.
  - Reviewer can edit fields and confirm changes are persisted and auditable.

---

## Epic 2 — Strategy Engine (Upgrade/Pivot/Hybrid + School Fit)

### Objective
Provide explicit strategy recommendations with transparent rationale and risk signals.

### Scope
- Strategy classification (Upgrade/Pivot/Hybrid).
- School-fit recommendation set with competitiveness tiers.
- Reasoning summary: strengths, risks, assumptions.
- Risk level scoring and strategy confidence.
- “What changed” recalculation when profile updates.

### User Stories
- **US2.1** As a candidate, I receive a clear strategy type and explanation.
- **US2.2** As a candidate, I can see target schools grouped by reach/match/safe tiers.
- **US2.3** As a consultant, I can inspect factors that drove the strategy output.
- **US2.4** As a candidate, when I update profile data, I can see strategy changes and why.

### Testable Deliverable
- **Deliverable:** “Strategy Recommendation Report”.
- **Validation checklist:**
  - Given a seeded candidate profile, engine returns strategy type + rationale + risk score.
  - School list includes fit reasoning per school.
  - Strategy output updates after profile edits with a visible diff.

---

## Epic 3 — Task Engine & Execution Planner

### Objective
Convert strategy into prioritized, trackable execution plans for applications.

### Scope
- Auto-generated task plan by candidate type (Grad/UG).
- Prioritization logic by deadlines, impact, dependencies.
- Progress tracking, reminders, and status transitions.
- Calendar/deadline views and milestone summaries.
- Consultant override/comment support.

### User Stories
- **US3.1** As a candidate, I get a prioritized list of next actions tied to my strategy.
- **US3.2** As a candidate, I can mark tasks complete and view remaining critical path.
- **US3.3** As a candidate, I receive deadline reminders for upcoming submissions.
- **US3.4** As a consultant, I can adjust task priority and add guidance notes.

### Testable Deliverable
- **Deliverable:** “Execution Board v1”.
- **Validation checklist:**
  - Reviewer sees auto-generated tasks with priority and due dates.
  - Completing tasks updates completion metrics and next recommended actions.
  - Reminder triggers fire for due-soon tasks in test accounts.

---

## Epic 4 — Essay Review Engine & Version Intelligence

### Objective
Deliver iterative essay feedback and revision tracking without full essay ghostwriting.

### Scope
- Essay upload/editor with draft versions.
- AI feedback on clarity, structure, impact, and alignment with narrative.
- Version comparison (diff, improvement highlights).
- Guardrails to avoid full end-to-end essay generation.
- Feedback history and actionable revisions.

### User Stories
- **US4.1** As a candidate, I can submit a draft and receive structured feedback.
- **US4.2** As a candidate, I can compare draft versions and see what improved.
- **US4.3** As a consultant, I can review AI feedback and add final comments.
- **US4.4** As a compliance owner, I can verify the system avoids full essay authorship.

### Testable Deliverable
- **Deliverable:** “Essay Review Workspace”.
- **Validation checklist:**
  - Two uploaded drafts produce a version diff + quality deltas.
  - Feedback categories appear with actionable recommendations.
  - Guardrail tests confirm blocked behavior for “write full essay for me” prompts.

---

## Epic 5 — Research Engine (Program Insights & Recommendations)

### Objective
Provide candidate-specific school/program research with comparison views.

### Scope
- Program database ingestion and normalization.
- Candidate-query research assistant (fit, culture, career outcomes, deadlines).
- Side-by-side school comparison.
- Personalization using profile strategy and constraints.
- Citation/source snippets for answer traceability.

### User Stories
- **US5.1** As a candidate, I can ask research questions and get tailored answers.
- **US5.2** As a candidate, I can compare shortlisted schools side by side.
- **US5.3** As a consultant, I can validate evidence sources behind recommendations.
- **US5.4** As a candidate, I can save schools to a target list from research results.

### Testable Deliverable
- **Deliverable:** “School Research Hub”.
- **Validation checklist:**
  - Reviewer can run a query and receive personalized school insights.
  - Comparison table renders at least 3 schools with differentiating criteria.
  - Responses include source/citation metadata for traceability.

---

## Epic 6 — Persistent Memory, Logs, and Consultant Collaboration

### Objective
Maintain complete candidate context across sessions and enable AI-human shared workflows.

### Scope
- Persistent chat history and context recall.
- Decision/revision/event log system.
- Consultant mode with shared profile/task/essay context.
- Activity audit trail and timeline playback.
- Memory summarization for long-running UG journeys.

### User Stories
- **US6.1** As a candidate, I can return weeks later and the assistant remembers my context.
- **US6.2** As a consultant, I can see AI decisions and prior interactions in one place.
- **US6.3** As a candidate, I can review a timeline of major decisions and revisions.
- **US6.4** As an admin, I can audit who changed what and when.

### Testable Deliverable
- **Deliverable:** “Shared Context Timeline”.
- **Validation checklist:**
  - Session memory recall works across at least 3 separate sessions.
  - Consultant can inspect logs, edits, and decision history by candidate.
  - Audit events include actor, timestamp, entity, and change summary.

---

## Epic 7 — Quality, Compliance, and Launch Readiness

### Objective
Validate non-functional requirements and prepare for controlled rollout.

### Scope
- Latency/load testing and availability targets.
- PII/privacy validation and retention policies.
- Multilingual QA for intake/chat/feedback pathways.
- Pricing/plan enforcement (Grad AI, Grad Consultant, UG AI, UG Consultant).
- Analytics dashboards for conversion, retention, task completion, essay improvement.
- Beta launch controls: feature flags, cohort rollout, incident runbooks.

### User Stories
- **US7.1** As an operator, I can monitor SLOs and receive alerts before user impact escalates.
- **US7.2** As a compliance owner, I can prove PII handling and policy enforcement.
- **US7.3** As a growth lead, I can track funnel and engagement metrics by plan.
- **US7.4** As a beta user manager, I can gradually roll out features to selected cohorts.

### Testable Deliverable
- **Deliverable:** “Launch Readiness Review Pack”.
- **Validation checklist:**
  - Load test report confirms target latency/availability under expected traffic.
  - Privacy/security checklist passed with remediation log closed.
  - KPI dashboards display baseline metrics for pilot users.

---

## Recommended Delivery Sequence & Milestones
1. **Phase 0 Setup** (2–4 weeks)
2. **Epic 1 + Epic 2** (4–6 weeks) → first strategic value demo
3. **Epic 3 + Epic 4** (4–6 weeks) → execution and essay iteration demo
4. **Epic 5 + Epic 6** (4–6 weeks) → research + persistent intelligence demo
5. **Epic 7** (2–3 weeks) → launch readiness gate

## Definition of Done (Across All Epics)
- User stories meet acceptance criteria.
- Epic testable deliverable is demoed in staging with checklist evidence.
- Observability, security checks, and regression tests pass for changed services.
- Product + engineering sign-off recorded with known risks and follow-up actions.
