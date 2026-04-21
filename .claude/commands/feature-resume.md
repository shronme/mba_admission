---
description: "Resume an in-progress feature pipeline. Usage: /feature-resume <feature-id>"
allowed-tools: Read, Write, Task, Grep, Glob, LS
---

# Feature Pipeline Resume

## Argument Parsing

- First word = FEATURE_ID
- If no FEATURE_ID provided, scan `.claude/features/` for any in-progress features and list them:

```
Usage: /feature-resume <feature-id>

In-progress features:
  - user-auth-sso   (last stage: 03-qa-plan.md, awaiting checkpoint #2)
  - dark-mode-ui    (last stage: 05-dev-log.md, in development)
```

---

## Resume Logic

Read the feature folder at `.claude/features/{FEATURE_ID}/` and inspect each file in order.
Also read `checkpoint.md` if it exists.

Determine the current stage using this decision table:

| Condition | Action |
|-----------|--------|
| Folder doesn't exist | Print error: "Feature {FEATURE_ID} not found. Start it with: /feature {FEATURE_ID} <description>" |
| `07-test-report.md` Status = PASS, checkpoint 3 APPROVED | Print: "Feature is already complete ✅" |
| `07-test-report.md` Status = PASS, checkpoint 3 PENDING | Re-present Checkpoint #3 and wait for reply |
| `07-test-report.md` Status = FAIL | Inform user, invoke `developer` to fix, then `code-reviewer`, then `tester` |
| `06-code-review.md` Status = APPROVED, no test report | Invoke `test-writer` (optional), then invoke `tester` |
| `06-code-review.md` Status = CHANGES_REQUESTED | Inform user of outstanding review issues, invoke `developer` (resume), then `code-reviewer` |
| `05-dev-log.md` Status = COMPLETE, no review | Invoke `code-reviewer` |
| `05-dev-log.md` Status = IN_PROGRESS or BLOCKED | Invoke `developer` (resume) |
| `04-tasks.md` Status = COMPLETE, no dev log | Invoke `developer` (start) |
| `03-qa-plan.md` Status = COMPLETE, checkpoint 2 APPROVED | Invoke `task-writer` |
| `03-qa-plan.md` Status = COMPLETE, checkpoint 2 PENDING | Re-present Checkpoint #2 and wait for reply |
| `02-product-spec.md` Status = COMPLETE, checkpoint 1 APPROVED | Invoke `qa-planner` |
| `02-product-spec.md` Status = COMPLETE, checkpoint 1 PENDING | Re-present Checkpoint #1 and wait for reply |
| `01-ba-analysis.md` Status = COMPLETE | Invoke `product-manager` |
| Only `01-ba-analysis.md` exists, Status = IN_PROGRESS | Inform user BA is still running |

---

## Status Report

Before resuming, always print a status summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Feature: {FEATURE_ID}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  01-ba-analysis.md     ✅ COMPLETE
  02-product-spec.md    ✅ COMPLETE
  checkpoint #1         ✅ APPROVED
  03-qa-plan.md         ✅ COMPLETE
  checkpoint #2         ⏳ PENDING
  04-tasks.md           —
  05-dev-log.md         —
  06-code-review.md     —
  07-test-report.md     —

Resuming from: Checkpoint #2 — QA Plan Review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then continue the pipeline from that point, including all remaining stages and checkpoints, exactly as the main `feature.md` orchestrator would.

---

## Re-presenting Checkpoints

When re-presenting a checkpoint, include a reminder of what was produced:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏸  CHECKPOINT #2 — QA Plan Review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Please review: .claude/features/{FEATURE_ID}/03-qa-plan.md

Reply with:
  ✅ "approved" or "looks good" — continue to task writing + development
  ✏️  "change: <your feedback>" — revise the QA plan first
  ❌ "stop" — halt the pipeline
```

Handle replies the same way as in `feature.md`.