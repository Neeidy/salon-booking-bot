# testing

**Purpose:** define Definition of Done and the edge cases that matter for THIS bot.

**Definition of Done (per phase):** built · tested (happy path + key edge cases) · cleaned ·
**sanitized (secrets AND PII)** · README/case-study · pushed.

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
