# Reference: Claude pipeline files in this repo

These are the canonical sources this skill follows.

## Agent playbooks (roles)

- `.claude/agents/business-analyst.md`
- `.claude/agents/product-manager.md`
- `.claude/agents/qa-planner.md`
- `.claude/agents/task-writer.md`
- `.claude/agents/developer.md`
- `.claude/agents/test-writer.md`
- `.claude/agents/code-reviewer.md`
- `.claude/agents/tester.md`

## Pipeline commands (orchestration)

- `.claude/commands/feature.md`
- `.claude/commands/feature-ba.md`
- `.claude/commands/feature-pm.md`
- `.claude/commands/feature-qa.md`
- `.claude/commands/feature-tasks.md`
- `.claude/commands/feature-dev.md`
- `.claude/commands/feature-write-tests.md`
- `.claude/commands/feature-review.md`
- `.claude/commands/feature-test.md`
- `.claude/commands/feature-resume.md`

## Artifacts produced

All artifacts live under:

- `.claude/features/<feature-id>/`

With these standard files:

- `01-ba-analysis.md`
- `02-product-spec.md`
- `03-qa-plan.md`
- `04-tasks.md`
- `05-dev-log.md`
- `06-code-review.md`
- `07-test-report.md`
