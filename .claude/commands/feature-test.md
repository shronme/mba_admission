---
description: "Run tests for a feature. Usage: /feature-test <feature-id>"
allowed-tools: Task, Read, Write, Bash
---

# Feature Test Run

Parse the arguments:
- First word = FEATURE_ID (optional — if omitted, read it from `.claude/features/.active`)

If no FEATURE_ID and `.claude/features/.active` does not exist:
```
Usage: /feature-test <feature-id>
```

Invoke the `tester` subagent with:
```
FEATURE_ID: {FEATURE_ID}
```

The agent will run the test suite, compare results against the QA plan, and write `07-test-report.md`.

After the test run completes:
- Read `.claude/features/{FEATURE_ID}/07-test-report.md` and check `## Status`.
- If Status is `PASS`, stop (human checkpoint remains).
- If Status is `FAIL` or `PARTIAL`, run this loop until the status becomes `PASS`:
  - Invoke the `developer` subagent with:
    ```
    FEATURE_ID: {FEATURE_ID}
    ```
    And instruct it to fix **all** failures described under `## Failures Detail` in `07-test-report.md` (update code and/or tests as needed).
  - Invoke the `code-reviewer` subagent with:
    ```
    FEATURE_ID: {FEATURE_ID}
    ```
    If the code review status becomes `CHANGES_REQUESTED`, invoke the `developer` again to fix all `## Required Changes`, then re-run the `code-reviewer` until it becomes `APPROVED`.
  - Invoke the `tester` subagent again (same FEATURE_ID) to regenerate `07-test-report.md`.
