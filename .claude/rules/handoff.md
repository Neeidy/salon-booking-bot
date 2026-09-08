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

Five classes — never merged (the header said "three" while listing four; corrected 2026-09-09f):

| Class | Cause | Writes state? | Response |
|---|---|---|---|
| guard-trip | kill-switch / max-turns | no (transient) | 200 |
| infra-unavailable | external system down | no (transient) | 5xx + `error` flag |
| intent-handoff | explicit handoff · **model did not answer at all** (bad `stop_reason`, unparseable JSON, non-object) · uncertain turn **while a confirmation is pending** · SECOND consecutive uncertain turn | yes (`stage=handoff`, `last_intent`) | 200 |
| clarify | FIRST uncertain turn (no confirmation pending) | `last_intent='clarify'` only — **no `stage` change, so no lock** | 200 |
| **extraction-transient** | the model ANSWERED but the JSON failed the committed schema (e.g. the required `dateExpr` key absent) — AND the intent is not `handoff` — AND **no cancel/reschedule confirmation is pending** — AND it is the FIRST one in a row | `last_intent='invalid'` only — **no `stage` change, so no lock**; `extraction_invalid` flag → owner alert | 200 |

**Two bounds on that row are load-bearing, not fine print — both were missing in the first cut and both were
found by the L2 reviewers, not by the build (2026-09-09f):**
1. **A pending cancel/reschedule confirmation wins.** The new gate sits in FRONT of `Invalid or Handoff Gate`,
   so without this carve-out a schema failure during `cancel_confirming`/`reschedule_confirming` never reached
   `Confirm Pending & Uncertain?` — the row three lines above. The pending confirm survived in state but
   `turn_count` advanced, the `confirm_turn` TTL went stale, and the customer's next "yes" was answered with
   *"your booking stands"*: the confirmation dropped on a classification we do not trust, which is exactly what
   this file forbids. The stage list in `Extraction Transient?` is COPIED from `Confirm Pending & Uncertain?`
   and a unit test compares the two so they cannot drift. (Plain booking `confirming` is deliberately NOT in
   the list — shown, not assumed: `Confirm Router` → `Reschedule Router` → `Build Event Request` has no
   freshness check, so an extra turn cannot stale it.)
2. **The second one in a row escalates.** `Repeat Extraction Failure?` reads `last_intent='invalid'` carried in
   by `Merge State` and routes to `Mark Handoff`. Without it a systematic contract failure gave the customer up
   to `bot.maxTurnsPerConversation` (12) identical re-asks while the owner saw ONE alert (throttle is 30
   minutes on `class:sender`). Same two-strike shape as `clarify` — a non-locking class still needs a ladder,
   or "no lock" quietly means "no exit".

⚠ **"invalid intent" used to sit in the intent-handoff row and it was too coarse.** A model that does not answer
and a model that breaks our schema are different faults. The second is OUR contract defect, and locking the
conversation for it silenced a customer who only asked a price (Codex MED-6, 2026-09-09f): the required
`dateExpr` key was simply ABSENT from an otherwise perfect payload. The split is `Extraction Transient?` →
`Build Extraction-Retry State`. It is **not** the clarify class: it must not spend the customer's single
clarify credit for a bug of ours, so it keeps `last_intent='invalid'` and always alerts the owner.

Rationale: if an outage looks like a normal handoff, nobody ever learns the system is broken —
exactly the silent failure this repo forbids.
