# testing

**Purpose:** define Definition of Done and the edge cases that matter for THIS bot.

**Definition of Done (per phase):** built · tested (happy path + key edge cases) · cleaned ·
**sanitized (secrets AND PII)** · README/case-study · pushed ·
**□ resume-point memory WRITTEN and READ BACK to verify it names the phase that actually just closed.**
· *(Loom walkthrough, if relevant — carried here on 2026-09-11 from `MASTER-BRIEF.md`, which had been a third copy of this list and was the only surface holding this item.)*

⚠ **That last item is a GATE, not a courtesy: a phase does not close without it.** "I updated the memory"
is a claim like any other — read the file back and show that its content points at the right phase and the
right next step. Writing and verifying are two acts, and only the second one is evidence.

**Why it became a gate (2026-09-11):** the end-of-phase memory update was happening because Yigitcan asked
for it every single time. **Something that works because a human remembers to ask is not a rule — it is his
attention, borrowed.** The failure it prevents is already on the record: at CP4 the memory lagged a full
checkpoint behind, so the next session resumed from a state that no longer existed
(`reporting.md` → "Live-state sync is part of closing a phase").

**Edge cases that must be tested (not optional for a booking bot):**
- **Double-booking:** two customers, same slot, ~same time → exactly one booking + handoff (see [booking-integrity.md](booking-integrity.md)).
- **Idempotency:** the same inbound message delivered twice → one booking, not two.
- **Prompt injection / jailbreak:** a message trying to change the bot's instructions → treated as data (see [prompt-injection.md](prompt-injection.md)).
- **Uncertain turn (`unknown` or low confidence):** the FIRST one gets a clarifying question and writes no new
  `stage` (no lock); a SECOND in a row hands off; one that arrives **while a confirmation is pending** hands off
  immediately with an owner alert. Never a wrong guess (see [handoff.md](handoff.md)).
- **Invalid LLM output:** intent JSON fails `schemas/intent.schema.json` → visible, never a silent retry — but
  **which** failure decides which class (see [handoff.md](handoff.md)). A model that did not answer (bad
  `stop_reason`, unparseable JSON, non-object) hands off and locks. A model that answered and broke the SCHEMA is
  `extraction-transient`: owner-alerted, kept off every write path, **no `stage` write, no lock**.
- **A required key ABSENT is not the same test as that key being `null`.** The drill for the `dateExpr` contract
  used `dateExpr: null` — a present key, which validates — passed six ways, and missed the real defect entirely;
  Codex removed the key and an ordinary price question got a permanent handoff lock. When a schema makes a key
  required, the case that matters is the MISSING key (`tests/unit/validate-intent.test.cjs`).
- **Timezone/DST:** a booking near a DST boundary lands at the correct wall-clock time.

Test artifacts live in [`tests/`](../../tests/): `golden-set.md` (happy) + `jailbreak-cases.md` (adversarial).

**Why:** a booking bot that double-books or leaks a jailbreak is worse than no bot — these cases are the product.

## A script that makes live calls does nothing on import (ruling D4-7, 2026-10-23)
**Its body sits under `if __name__ == '__main__':`** — every activation, request, seed or wait. At the top level
it may only import, define, and set constants. **Why:** twice in the migration a live-probe script ran its body
when it was imported: the D3b race script, and the D3c drill script, imported to reuse one function, which ran a
second, unplanned drill pass inside a K-4 window (MIGRATION-PLAN §3r, D3c result). Both lived in the session
scratchpad, which no repo guard can see.
**Checked by** `scripts/check-import-safe.py`: in `check-all` over `scripts/` and `tests/`, and **before every live
window over the scripts that window will run** (pass their paths; a named script's own directory is read too, so a
drill script counts as live through the helper it imports). A line that must stay at the top level carries
`# import-safe: <reason>`. Python only; Node scripts are not covered.
