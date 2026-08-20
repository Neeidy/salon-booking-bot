# plan-gate

**Purpose:** the binding definition of the per-phase plan gate named in `CLAUDE.md` → "Operating protocol".
No phase/CP/checkpoint build starts until this ritual is satisfied. This file — not the harness — is the authority.

## The gate
1. **Full plan, in chat, every time.** Before building any phase / CP / checkpoint, the plan is presented **in
   the conversation** in the COMPLETE `/plan-flow` format. All of these sections are mandatory — a missing
   section means the gate is not satisfied:
   - **goal** · **scope** · **NOT-build list** · **skeleton (node-level)** · **integrations** ·
     **mock-data plan** · **Critical-Review Targets** · **acceptance criteria** · **⚙ drill matrix** ·
     **automation-fit** (`/loop` / `/goal` / "neither").
   Plus any decisions the phase must pin down, stated explicitly for the approver to rule on.
2. **Build starts ONLY on Yigitcan's written "approved".** A typed "approved" (or an unmistakable written
   go-ahead) in the conversation is the sole trigger. Nothing else begins the build.
3. **ExitPlanMode / harness "approved" is NOT Yigitcan's approval.** The harness returning
   "User has approved your plan" from ExitPlanMode (or any tool/UI acknowledgement) does **not** stand in for
   the ritual above. Treating a harness/ExitPlanMode signal as approval — and proceeding to any build step,
   including "pre-flight" verification or editor/Airtable instructions — is a **violation** of this gate.
4. **On violation: stop → report → roll back.** The moment a gate breach is noticed: STOP, report exactly what
   was applied (nodes added/edited, Airtable fields, config/schema/file changes — or "nothing mutated" if so),
   and roll back or hold anything applied. Yigitcan decides how to proceed.

## Scope note
"Build" includes any step that moves toward implementation: creating/editing n8n nodes, changing config/schema/
repo files, instructing an Airtable schema change, or running a "pre-flight" that presumes the plan is going
ahead. Read-only verification used to *write* the plan (exploration) is part of planning, not build.

## Why
This gate exists because the approver (L5, `CLAUDE.md` "Defense-in-depth") owns the go/no-go, and a plan that
was never fully laid out cannot be judged. It was breached once (CP5, 2026-08-20): ExitPlanMode returned
"approved", and on that signal the build advanced to pre-flight `describe_table` + an Airtable-field
instruction **before** the plan was presented in chat — and that plan was itself missing the mock-data,
Critical-Review-Targets, and ⚙ drill-matrix sections. No node/field/file was mutated that time, but the step
toward build without a written "approved" is exactly what this rule forbids. See
[reporting.md](reporting.md) (honest status) and [governance-sync.md](governance-sync.md) (decisions land in the repo).
