---
description: "Implement tasks for a feature. Usage: /feature-dev <feature-id> [resume|<task-id>]"
allowed-tools: Task, Read, Write, Edit, Bash, Grep, Glob, LS
---

# Feature Development

Parse the arguments:
- First word = FEATURE_ID (optional — if omitted, read it from `.claude/features/.active`)
- Next word (optional) = `resume` or a specific TASK_ID (e.g. `TASK-003`)

If no FEATURE_ID and `.claude/features/.active` does not exist:
```
Usage: /feature-dev <feature-id> [resume|TASK-001]
```

Invoke the `developer` subagent with:
```
FEATURE_ID: {FEATURE_ID}
MODE: {resume | TASK_ID | start}
```

The agent will read `04-tasks.md` and `05-dev-log.md` (if exists), implement the next task, and update the dev log.
