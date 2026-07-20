# handoff

**Purpose:** when the bot isn't sure, a human takes over — quietly and quickly.

- **Threshold:** `confidence < 0.7` → **human handoff** (starting value, aligned across the flow; tune with
  real data). The number lives in config, not hard-coded in scattered nodes.
- **Below-threshold behavior = abstain / fallback → handoff.** The bot never *guesses* the action. It is
  better to hand off than to book the wrong slot.
- LLM self-reported confidence is poorly calibrated — prefer clear intent-classification with an explicit
  "unsure" path over trusting a raw self-score.
- **Handoff = notify the owner** (visible alert) with the conversation context, and tell the customer a human
  will follow up. Never leave the customer in silence.
- Jailbreak attempts, invalid intent JSON, and any error branch also route here.

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
| intent-handoff | low confidence / cancel / unknown | yes (`stage=handoff`, `last_intent`) | 200 |

Rationale: if an outage looks like a normal handoff, nobody ever learns the system is broken —
exactly the silent failure this repo forbids.
