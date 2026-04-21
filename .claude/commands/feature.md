---
description: "Kick off the full feature pipeline (BA only). Usage: /feature <feature-id> <description>"
allowed-tools: Task, Read, Write, Grep, Glob, LS
---

# Feature Pipeline Kickoff

This command starts the feature development pipeline by running the BA analysis.
The full pipeline is:

```
/feature-ba   → BA Analysis
/feature-pm   → Product Spec       ← ⏸ Human Checkpoint #1
/feature-qa   → QA Test Plan       ← ⏸ Human Checkpoint #2
/feature-tasks → Dev Task List
/feature-dev  → Implementation     ← 🔁 Dev/Review loop
/feature-write-tests → Write Tests
/feature-review → Code Review
/feature-test → Run Tests          ← ⏸ Human Checkpoint #3
```

Parse the arguments:
- First word = FEATURE_ID
- Remainder = FEATURE_REQUEST

If no arguments provided, print:
```
Usage: /feature <feature-id> <description>
Example: /feature user-auth-sso Add single sign-on via Google OAuth

Pipeline overview:
  /feature-ba <id> <desc>   — BA analysis (start here, or use /feature)
  /feature-pm <id>           — Product spec
  /feature-qa <id>           — QA plan          ⏸ checkpoint after
  /feature-tasks <id>        — Dev tasks
  /feature-dev <id>          — Implement         🔁 loops with review
  /feature-write-tests <id>  — Write tests from QA plan
  /feature-review <id>       — Code review
  /feature-test <id>         — Run tests         ⏸ final checkpoint
```

If arguments are provided, follow the same two-step flow as `/feature-ba`:

**Step 1 — Clarify requirements (do this first, stop here)**

Ask the user 3–5 targeted clarifying questions based on the FEATURE_REQUEST. The goal is to surface ambiguities that would otherwise force the BA agent to make assumptions.

Good questions address:
- Who is the primary user and what triggers the flow?
- Edge cases or constraints not mentioned (e.g. "what happens if X?")
- Success criteria — how will we know this feature works?
- Scope boundaries — what is explicitly out of scope?
- Any known technical constraints or preferences?

Ask the questions as a numbered list, then **stop and wait for the user's answers**. Do not proceed to Step 2 in the same turn.

**Step 2 — Run the BA agent (only after user has answered)**

Once the user has answered:
1. Create `.claude/features/{FEATURE_ID}/` directory
2. Write FEATURE_ID (just the ID, nothing else) to `.claude/features/.active`
3. Invoke the `business-analyst` subagent with FEATURE_ID, FEATURE_REQUEST, and the user's CLARIFICATIONS
4. The agent will write `01-ba-analysis.md` and prompt to continue with `/feature-pm`
