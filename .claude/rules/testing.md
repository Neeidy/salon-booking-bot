# testing

**Purpose:** define Definition of Done and the edge cases that matter for THIS bot.

**Definition of Done (per phase):** built · tested (happy path + key edge cases) · cleaned ·
**sanitized (secrets AND PII)** · README/case-study · pushed.

**Edge cases that must be tested (not optional for a booking bot):**
- **Double-booking:** two customers, same slot, ~same time → exactly one booking + handoff (see [booking-integrity.md](booking-integrity.md)).
- **Idempotency:** the same inbound message delivered twice → one booking, not two.
- **Prompt injection / jailbreak:** a message trying to change the bot's instructions → treated as data (see [prompt-injection.md](prompt-injection.md)).
- **Low confidence:** ambiguous message → human handoff, not a wrong guess (see [handoff.md](handoff.md)).
- **Invalid LLM output:** intent JSON fails `schemas/intent.schema.json` → error branch + handoff, not silent retry.
- **Timezone/DST:** a booking near a DST boundary lands at the correct wall-clock time.

Test artifacts live in [`tests/`](../../tests/): `golden-set.md` (happy) + `jailbreak-cases.md` (adversarial).

**Why:** a booking bot that double-books or leaks a jailbreak is worse than no bot — these cases are the product.
