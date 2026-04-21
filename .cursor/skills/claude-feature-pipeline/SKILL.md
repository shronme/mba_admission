---
name: claude-feature-pipeline
description: Runs the repository’s Claude-style feature pipeline (BA → PM → QA → Tasks → Dev → Review → Test) and writes artifacts under .claude/features/<feature-id>/. Use when the user asks to start/resume a feature, generate BA/spec/QA/tasks artifacts, or to follow the repo’s /feature-* workflow.
---

# Claude Feature Pipeline (Project Skill)

This project keeps feature work in `.claude/features/<feature-id>/` and uses a staged pipeline with human checkpoints. Use the repo’s existing guidance as the source of truth and produce artifacts with the exact file names and section structures it specifies.

## Quick start

1. Pick a `FEATURE_ID` slug (kebab-case).
2. Ensure `.claude/features/<FEATURE_ID>/` exists.
3. Write the active feature id to `.claude/features/.active` (just the id, no extra text).
4. Execute the next stage in order (or resume based on current artifacts).

For the authoritative stage definitions and output templates, read:
- `.claude/commands/feature.md`
- `.claude/commands/feature-resume.md`
- `.claude/agents/*.md` (role playbooks)

## Pipeline stages (authoritative artifacts)

Follow these stages and write the corresponding files:

- **BA** → `.claude/features/<FEATURE_ID>/01-ba-analysis.md`
- **PM** → `.claude/features/<FEATURE_ID>/02-product-spec.md` (then pause for human checkpoint #1)
- **QA** → `.claude/features/<FEATURE_ID>/03-qa-plan.md` (then pause for human checkpoint #2)
- **Tasks** → `.claude/features/<FEATURE_ID>/04-tasks.md`
- **Dev** → `.claude/features/<FEATURE_ID>/05-dev-log.md` (iterate task-by-task; stop after each task unless explicitly asked)
- **Write Tests** → (code changes only; update `.claude/features/<FEATURE_ID>/05-dev-log.md`)
- **Review** → `.claude/features/<FEATURE_ID>/06-code-review.md` (Dev/Review loop until approved)
- **Test** → `.claude/features/<FEATURE_ID>/07-test-report.md` (then pause for human checkpoint #3)

## How to run each stage

### If the user says “start a feature”

Do the **Step 1/Step 2** flow described in `.claude/commands/feature.md`:
- Ask 3–5 clarifying questions and stop.
- After answers, run BA and create the feature folder + `.active`.

### If the user says “resume”

Use the decision table in `.claude/commands/feature-resume.md`:
- Inspect existing artifacts’ `Status` fields.
- Re-present any pending checkpoint instructions verbatim-ish (approved/change/stop).
- Otherwise, invoke the next stage and continue until the next checkpoint.

### If the user asks for a specific artifact (e.g., “write the QA plan”)

1. Verify prerequisites exist and have `Status: COMPLETE` per the corresponding agent playbook.
2. Produce the file with the exact structure required.
3. Print the stage completion footer text specified by that playbook (including which command is next / which checkpoint applies).

## Guardrails

- **Do not invent templates**: use the exact structures in `.claude/agents/*.md`.
- **Preserve status semantics**: only mark `Status` as `COMPLETE` when the artifact is done.
- **Checkpoints are hard stops**: after PM/QA/Test, stop and wait for user approval.
- **Repository conventions win**: follow `CLAUDE.md` architecture notes for where code should live when implementing tasks.

## Additional resources

- See `reference.md` for the exact repo files this skill builds on.
