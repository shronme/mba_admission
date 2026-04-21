---
description: "Run code review for a feature. Usage: /feature-review <feature-id>"
allowed-tools: Task, Read, Grep, Glob, LS, Write
---

# Feature Code Review

Parse the arguments:
- First word = FEATURE_ID (optional — if omitted, read it from `.claude/features/.active`)

If no FEATURE_ID and `.claude/features/.active` does not exist:
```
Usage: /feature-review <feature-id>
```

Invoke the `code-reviewer` subagent with:
```
FEATURE_ID: {FEATURE_ID}
```

The agent will review all changed files against the spec and task list, then write `06-code-review.md`.

After the review completes:
- Read `.claude/features/{FEATURE_ID}/06-code-review.md` and check `## Status`.
- If Status is `CHANGES_REQUESTED`, immediately invoke the `developer` subagent with:
  ```
  FEATURE_ID: {FEATURE_ID}
  ```
  And instruct it to fix **all** items under `## Required Changes (must fix before approval)` in `06-code-review.md`, updating code/tests as needed.
- When the developer finishes, run the `code-reviewer` subagent again (same FEATURE_ID) to re-check and update `06-code-review.md`.
- Repeat until the review status becomes `APPROVED`.
