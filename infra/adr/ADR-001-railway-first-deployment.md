# ADR-001: Railway-first deployment for Phase 0

- Status: Accepted
- Date: 2026-03-17

## Context
Phase 0 requires rapid MVP deployment for API + worker + Postgres + Redis while keeping an exit path to a more customizable platform if scale/compliance constraints appear.

## Decision
Use Railway as the primary deployment platform through Epics 0–4 for:
- API service deployment
- Worker deployment
- Managed Postgres and Redis
- Staging and production environments

## Rationale
- Fast environment bootstrap with low DevOps overhead.
- Good fit for early-stage product validation and small engineering team velocity.
- Supports required services for current architecture.

## Exit criteria (trigger reassessment)
Reassess platform choice in Epic 5/6 if one or more are true for 2+ consecutive weeks:
1. API p95 latency > 800ms for core endpoints under expected load.
2. Queue depth sustained > 5,000 jobs with processing lag > 15 minutes.
3. Uptime drops below 99.5% monthly.
4. Infrastructure cost per active candidate rises above target budget by > 25%.
5. Compliance/security needs require controls unavailable in Railway (advanced networking, strict data residency, enterprise controls).

## Consequences
- Positive: faster delivery of first user-facing milestones.
- Negative: possible migration effort to Kubernetes/ECS when scale/compliance increases.
- Mitigation: keep Docker-based workloads and infrastructure-as-code assets portable from day one.
