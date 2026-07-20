# n8n-conventions

**Purpose:** how every n8n flow in this repo is built (the engine lives in n8n).

- **Node naming:** verb + object (`Extract Intent`, `Check Availability`, `Book Appointment`). No `HTTP Request1`.
- **Sticky notes are mandatory** on every branch — say what the section does and why. The canvas teaches.
- **Mandatory error branch — failures are VISIBLE.** Every external call (Zernio, Google Calendar, Airtable,
  LLM) has an error path that notifies the owner. Silent failure is forbidden.
- **Infra failure ≠ a normal handoff** — an external-system outage returns a *distinct* response (status
  code + `error:"<system>_unavailable"` flag) from its own node so an owner-alert can hook it; it is one of
  the three handoff classes in [handoff.md](handoff.md), never merged with a conversational handoff.
- **Deterministic before AI.** Menu / price / hours / slot lookups = IF/Switch nodes, not an LLM call.
  The LLM is only for genuine free-text intent extraction.
- **Idempotency + booking integrity:** see [booking-integrity.md](booking-integrity.md) — dedupe on
  message-ID, and write-then-verify on booking.
- **Control-plane lockdown:** via the Cloudflare tunnel expose **only the webhook endpoints**. The n8n
  editor/admin UI is **never** on the public internet (behind auth / Cloudflare Access).
- **Export discipline:** commit only `n8n/workflow.sanitized.json` (run `/sanitize`); raw exports are gitignored.

**Why:** the flow IS the product's engine — its readability, safety, and idempotency are what a client pays for.
