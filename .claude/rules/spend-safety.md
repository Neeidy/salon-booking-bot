# spend-safety

**Purpose:** hard brakes so the bot can never run away on cost or loop forever.

- **Budget cap:** a hard LLM spend cap per period (`LLM_COST_CAP_USD`). Over cap → stop calling the LLM,
  fall back to deterministic replies + handoff.
- **Max-iteration:** a per-conversation turn cap (`LLM_MAX_TURNS`). No infinite back-and-forth.
- **Timeout:** every external call (LLM, Zernio, Google Calendar, Airtable) has a timeout → error branch on expiry.
- **Dry-run default:** new/changed flows run in dry-run (no real writes) until explicitly switched to live.
- **Global kill-switch:** `BOT_KILL_SWITCH=true` puts the bot into **handoff-only** mode instantly — every
  message goes to a human, no LLM, no writes. This is the emergency stop.

The website widget is a public endpoint → also rate-limit + bot-protection so it can't be spammed into cost.

**Why:** an LLM behind a public webhook is a cost-and-abuse surface; these brakes make the worst case bounded.
