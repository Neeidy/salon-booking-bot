---
description: Lock a phase's plan (full format, in chat) before building. Gate = written "approved".
---

# /plan-flow

Run at the START of every phase/CP. Do NOT write code/nodes until Yigitcan's **written "approved"** —
the binding gate is [.claude/rules/plan-gate.md](../rules/plan-gate.md) (ExitPlanMode / harness "approved"
does **not** count). Present ALL of these sections in chat:

1. **Goal** — the one outcome this phase delivers (one sentence).
2. **Scope + NOT-build** — what's in, and what is explicitly out of this phase.
3. **Skeleton** — the files/nodes to be created or changed, **at node level** (name them).
4. **Integrations** — which external tools this phase touches (Zernio, Google Calendar, Airtable, LLM).
5. **Mock-data plan** — what test/mock data is used, marked as mock; cleanup after (`honesty-demos`, `security-secrets`).
6. **Critical-Review Targets** — which of MASTER-BRIEF §9's targets this phase touches (the Codex gate).
7. **Acceptance criteria** — how we'll know it works.
8. **⚙ Drill matrix** — the edge cases from `.claude/rules/testing.md`: scenario · setup · expected · MUST-RUN · MUST-NOT-RUN.
9. **Automation-fit** — state whether `/loop` or `/goal` fits this phase, or say **"neither"**.

Plus any decisions the phase must pin down, stated explicitly for the approver to rule on.
Then present → get Yigitcan's written **"approved"** → build, one small verifiable step at a time.
