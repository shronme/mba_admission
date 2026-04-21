---
description: "Write product spec for a feature. Usage: /feature-pm <feature-id>"
allowed-tools: Task, Read, Write
---

# Feature Product Spec

Parse the arguments:
- First word = FEATURE_ID (optional — if omitted, read it from `.claude/features/.active`)

If no FEATURE_ID and `.claude/features/.active` does not exist:
```
Usage: /feature-pm <feature-id>
```

## Step 1 — Read the BA analysis and ask clarifying questions (do this first, stop here)

Read `.claude/features/{FEATURE_ID}/01-ba-analysis.md`.

The BA analysis will likely contain open questions, assumptions, and ambiguities. Before writing the spec, ask the user targeted questions to resolve every open question so the spec can be written without assumptions.

Focus questions on:
- Any open questions listed explicitly in the BA analysis — ask about each one
- UX decisions that aren't pinned down (e.g. modal vs. page, tab vs. route)
- Edge case behaviors that affect implementation (e.g. what happens when a user re-does an action?)
- Priority or scope trade-offs (e.g. must-have vs. nice-to-have for v1)
- Any data model decisions that have multiple viable approaches

Ask **one question at a time**. After each answer, ask the next question. Keep going until all ambiguities are resolved. Only proceed to Step 2 once every question has been answered.

## Step 2 — Invoke the product-manager agent (only after user has answered)

Once the user has answered, invoke the `product-manager` subagent passing:
- FEATURE_ID
- The BA analysis path
- The user's answers to the clarifying questions

Instruct the agent to write a spec with **no open questions** — all decisions must be resolved using the user's answers. The spec should include:
1. Overview
2. User stories
3. Functional requirements (numbered, testable)
4. Non-functional requirements
5. UX flows
6. API contract
7. Data model changes
8. Out of scope

Output: `.claude/features/{FEATURE_ID}/02-product-spec.md`

End the file with:
> Human checkpoint: review `02-product-spec.md`, then run `/feature-qa` to continue.
