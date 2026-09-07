# handoff

**Purpose:** when the bot isn't sure, a human takes over — quietly and quickly.

- **Threshold:** `confidence < 0.7` (config, not hard-coded in scattered nodes) marks a turn **UNCERTAIN**.
  Uncertain is not the same as "the customer wants a human" — since 2026-09-07 the two are handled separately:
  - **A confirmation is pending** (`cancel_confirming` / `reschedule_confirming`) → **handoff immediately**
    (`Confirm Pending & Uncertain?` → `Mark Handoff`, owner alert). Never act on a classification we distrust
    while a booking hangs on it.
  - **Otherwise** → the FIRST uncertain turn gets a clarifying question (`messageTemplates.askIntent`) and
    writes no new `stage`, so no lock forms; a SECOND uncertain turn in a row hands off.
  - `intent = 'handoff'` (explicit request, jailbreak) and invalid intent JSON still hand off on the FIRST turn.
- **Below-threshold behavior = abstain, never guess.** The bot does not act on an intent it distrusts. Asking one
  clarifying question is abstaining; booking, cancelling or dropping a pending confirmation is guessing.
- LLM self-reported confidence is poorly calibrated — prefer clear intent-classification with an explicit
  "unsure" path over trusting a raw self-score.
- **Handoff = notify the owner** (visible alert) with the conversation context, and tell the customer a human
  will follow up. Never leave the customer in silence.
- Jailbreak attempts and invalid intent JSON route here. **Error branches are NOT automatically a
  conversational handoff** — see 'Infrastructure failure ≠ conversational handoff' below for the
  three classes and which one applies.

**Why:** a wrong booking erodes trust more than an honest "let me get a person" — the handoff is a feature.

## Infrastructure failure ≠ conversational handoff
A failure of an external system (LLM, calendar, CRM, channel provider) must NEVER be presented as a
normal conversational handoff. The customer may receive the same polite message, but the machine side
must be distinguishable: a distinct response (status code and/or `error: "<system>_unavailable"` flag)
AND a distinct node/branch that the owner-alert hooks onto.

Three handoff classes — never merged:

| Class | Cause | Writes state? | Response |
|---|---|---|---|
| guard-trip | kill-switch / max-turns | no (transient) | 200 |
| infra-unavailable | external system down | no (transient) | 5xx + `error` flag |
| intent-handoff | explicit handoff · invalid intent · uncertain turn **while a confirmation is pending** · SECOND consecutive uncertain turn | yes (`stage=handoff`, `last_intent`) | 200 |
| clarify | FIRST uncertain turn (no confirmation pending) | `last_intent='clarify'` only — **no `stage` change, so no lock** | 200 |

Rationale: if an outage looks like a normal handoff, nobody ever learns the system is broken —
exactly the silent failure this repo forbids.
