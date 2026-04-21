---
description: "Write development tasks for a feature. Usage: /feature-tasks <feature-id>"
allowed-tools: Task, Read, Write
---

# Feature Task List

Parse the arguments:
- First word = FEATURE_ID (optional — if omitted, read it from `.claude/features/.active`)

If no FEATURE_ID and `.claude/features/.active` does not exist:
```
Usage: /feature-tasks <feature-id>
```

Invoke the `task-writer` subagent with:
```
FEATURE_ID: {FEATURE_ID}
```

The agent will read `02-product-spec.md` and `03-qa-plan.md` and write `04-tasks.md`.
