---
description: Lock a phase's plan (goal · scope · NOT-build · skeleton · integrations) before building.
---

# /plan-flow

Run at the START of every phase. Do NOT write code/nodes until this is approved.

1. **Goal** — the one outcome this phase delivers (one sentence).
2. **Scope + NOT-build** — what's in, and what is explicitly out of this phase.
3. **Skeleton** — the files/nodes to be created or changed (name them).
4. **Integrations** — which external tools this phase touches (Zernio, Google Calendar, Airtable, LLM).
5. **Acceptance + test** — how we'll know it works (happy path + the key edge cases from `.claude/rules/testing.md`).
6. **Automation-fit** — state whether `/loop` or `/goal` fits this phase, or say **"neither"**.

Then enter plan mode → present → get an explicit **"approved"** → build. One small step at a time.
