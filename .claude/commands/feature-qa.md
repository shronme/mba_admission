---
description: "Write QA test plan for a feature. Usage: /feature-qa <feature-id>"
allowed-tools: Task, Read, Write
---

# Feature QA Plan

Parse the arguments:
- First word = FEATURE_ID (optional — if omitted, read it from `.claude/features/.active`)

If no FEATURE_ID and `.claude/features/.active` does not exist:
```
Usage: /feature-qa <feature-id>
```

Invoke the `qa-planner` subagent with:
```
FEATURE_ID: {FEATURE_ID}
```

The agent will read `02-product-spec.md` and write `03-qa-plan.md`, then prompt for human review.
