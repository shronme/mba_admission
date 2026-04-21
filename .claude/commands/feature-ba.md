---
description: "Start BA analysis for a feature. Usage: /feature-ba <feature-id> <feature description>"
allowed-tools: Task, Read, Write, Grep, Glob, LS
---

# Feature BA Analysis

Parse the arguments:
- First word = FEATURE_ID (e.g. `user-auth-sso`)
- Remainder = FEATURE_REQUEST (the feature description)

If no FEATURE_ID or FEATURE_REQUEST provided, print usage and stop:
```
Usage: /feature-ba <feature-id> <feature description>
Example: /feature-ba user-auth-sso Add single sign-on via Google OAuth
```

## Step 1 — Clarify requirements (do this first, stop here)

Before running the BA analysis, ask the user 3–5 targeted clarifying questions based on the FEATURE_REQUEST. The goal is to surface ambiguities that would otherwise force the BA agent to make assumptions.

Good questions address:
- Who is the primary user and what triggers the flow?
- Edge cases or constraints not mentioned (e.g. "what happens if X?")
- Success criteria — how will we know this feature works?
- Scope boundaries — what is explicitly out of scope?
- Any known technical constraints or preferences?

Ask **one question at a time**. After each answer, ask the next question. Keep going until all ambiguities are resolved. Only proceed to Step 2 once every question has been answered.

## Step 2 — Run the BA agent (only after user has answered)

Once the user has answered the clarifying questions:

1. Create the feature folder if it doesn't exist:
   `.claude/features/{FEATURE_ID}/`

2. Write FEATURE_ID (just the ID, nothing else) to `.claude/features/.active` so subsequent pipeline commands know which feature is active

3. Invoke the `business-analyst` subagent, passing:
   - FEATURE_ID
   - FEATURE_REQUEST (original description)
   - CLARIFICATIONS (the user's answers from Step 1)

The agent will explore the codebase and write `.claude/features/{FEATURE_ID}/01-ba-analysis.md`.
