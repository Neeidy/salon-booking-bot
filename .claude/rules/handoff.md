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
