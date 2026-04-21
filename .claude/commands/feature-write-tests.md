---
description: "Write tests for a feature from the QA plan. Usage: /feature-write-tests <feature-id>"
allowed-tools: Task, Read, Write, Bash, Grep, Glob, LS
---

# Feature Test Writing

Parse the arguments:
- First word = FEATURE_ID (optional — if omitted, read it from `.claude/features/.active`)

If no FEATURE_ID and `.claude/features/.active` does not exist:
```
Usage: /feature-write-tests <feature-id>
```

Invoke the `test-writer` subagent with:
```
FEATURE_ID: {FEATURE_ID}
```

The agent will implement/adjust automated tests to satisfy `.claude/features/{FEATURE_ID}/03-qa-plan.md`, and will update `.claude/features/{FEATURE_ID}/05-dev-log.md` with what was covered.
