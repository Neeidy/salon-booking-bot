# salon-booking-bot

**A config-driven salon booking chatbot — one message in, a booked appointment or a captured lead out.**

![status](https://img.shields.io/badge/status-learning%20%2F%20demo%20build-orange)
![phase](https://img.shields.io/badge/phase-2%20of%208%20(core%20bot)-blue)
![engine](https://img.shields.io/badge/engine-n8n%20self--hosted-EA4B71)
![llm](https://img.shields.io/badge/LLM-Claude%20Haiku%204.5-8A63D2)
![license](https://img.shields.io/badge/license-MIT-green)

> **Honest status:** this is a **demo / learning build**, not a system serving paying customers.
> Phases 0–1 are done, Phase 2 (the core bot) is nearly complete, Phases 3–8 are not built yet.
> Everything below marked ✅ has been built **and verified from execution logs**; everything marked
> 🔜 is designed and locked but **not shipped**. No invented metrics, no fake traffic.

---

## The one job

A barbershop loses bookings because messages arrive while the owner is cutting hair. This bot answers
instantly, in the shop's voice, and turns each message into one of two outcomes:

**a booked appointment** — or — **a captured lead + a human handoff**

…with **zero owner effort** and **zero double-bookings**. It is a **template**: a new client means a new
config file and new credentials, *not* new code.

---

## How it works

```
                    ┌─────────────── config-gated channels ───────────────┐
   WhatsApp ────────┤                                                     │
   Web widget ──────┤   →  NORMALIZE  →  one channel-agnostic brain       │
   Instagram (off) ─┘      {channel, sender_key, text}                    │
                    └─────────────────────────────────────────────────────┘
                                          │
   ┌──────────────────────────────────────▼──────────────────────────────────────┐
   │  1  Validate payload            invalid → 400                               │
   │  2  Load conversation state     Airtable, keyed by "{channel}:{id}"         │
   │  3  Handoff lock  🔜             a human took over → bot stays quiet         │
   │  4  Guards                      kill-switch · max-turns  → 0 LLM cost       │
   │  5  LLM intent extraction       Claude, structured JSON output              │
   │  6  Validate against schema     ajv compiled from the committed contract    │
   │  7  Confidence & intent gate    < 0.7 or cancel/unknown → human             │
   │  8  Route (deterministic)       book · FAQ · lead · handoff                 │
   └──────────────────────────────────────┬──────────────────────────────────────┘
                                          │
        book → collect service/date/time (multi-turn, deterministic)
        FAQ  → answered from config — the LLM never writes the answer
        lead → written to Airtable
                                          │
                              reply returns to the origin channel
```

*Steps marked 🔜 are designed and in progress, not yet shipped.*

**The LLM has exactly one job: understanding.** It converts messy free text into a structured intent.
It never writes a customer-facing answer, never chooses an action, and holds no write permissions.
Prices, hours and services come from config; routing is `IF`/`Switch`. That is why the bot **cannot
quote a wrong price** — the answer path contains no model.

---

## What works today ✅

| Capability | Detail |
|---|---|
| **Multi-channel intake** | WhatsApp + widget shapes normalized to one internal format; channels toggle in config |
| **Conversation memory** | Per-sender state in Airtable (`stage`, slots, turn count) — survives restarts |
| **Intent understanding** | Claude Haiku 4.5, temperature 0, native structured outputs |
| **Contract validation** | Model output validated by an ajv validator **compiled from the committed schema** — no hand-written copy that can drift |
| **Multi-turn booking collect** | "I want a haircut" → "what day and time?" → merged into a complete request |
| **Deterministic FAQ** | Price / hours / services / address answered from config, never from the model |
| **Lead capture** | Non-booking interest written to Airtable with channel + message |
| **Human handoff, 3 distinct classes** | guard-trip (transient) · infrastructure down (503) · genuine handoff (writes state) — never merged |
| **Visible failures** | Four separate error responses: `invalid_payload` · `state_unavailable` · `llm_unavailable` · `lead_unavailable` |
| **Spend brakes before the LLM** | Kill-switch and max-turns run *before* any paid call — a tripped guard costs nothing |

## Designed, locked, not built yet 🔜

Calendar booking write + no-double-book · cancel / reschedule / reminders · live WhatsApp transport ·
full safety suite (cost cap, rate limiting, injection hardening) · the customer-facing frontend ·
config-only second client.

---

## Engineering decisions worth reading

**Deterministic before AI.** A model is used only where a rule genuinely cannot decide. Asking an LLM
"what does a haircut cost?" is slower, costlier and less reliable than reading one config field.

**The schema is the single source of truth.** The validator inside the flow is *generated* from
`schemas/intent.schema.json` by a script, with a drift check. Two hand-maintained copies of the same
contract always diverge; a generated one cannot.

**Never trust a 200.** Structured output is only guaranteed when the model stops normally, so
`stop_reason` is checked first, enum casing is normalized, and any unexpected shape becomes a handoff
instead of a crash.

**An outage must not look like a handoff.** If the LLM or the database is down the customer still gets a
polite message, but the machine-side response is distinct (`503` + an error flag) so the owner can be
alerted. An outage that looks normal is an outage nobody fixes.

**Availability has one source of truth.** Google Calendar owns free/busy; Airtable mirrors it. Writes go
to the calendar first. Two sources of truth mean double bookings.

**Config / code / secret are separate.** The engine is identical for every client. A new client is a new
`client.config.json` plus new credentials — the workflow does not change.

---

## Repo map

| Path | What |
|---|---|
| [`n8n/`](n8n/) | the engine — **sanitized** workflow export only |
| [`schemas/`](schemas/) | JSON Schemas — the intent contract and the client config contract |
| [`prompts/`](prompts/) | versioned LLM prompts (the canonical system prompt) |
| [`scripts/`](scripts/) | validator compiler + drift check · repo map generator |
| [`config/`](config/) | per-client `client.config.json` (mock example committed) |
| [`docs/`](docs/) | architecture decisions · data model · live roadmap · repo map |
| [`design/`](design/) | Phase-1 mockups + flow diagram |
| [`tests/`](tests/) | golden-set intents · jailbreak / injection cases |
| [`web/`](web/) | frontend surfaces (Phase 6) |
| [`.claude/`](.claude/) | the rules this repo is actually built under |

**Stack** — n8n (self-hosted) · Anthropic Claude Haiku 4.5 · Airtable · Google Calendar ·
Zernio (WhatsApp Business API) · Next.js on Vercel.

---

## Security

This repository is **public**, so it is built as if it were.

- No secrets, no customer PII in git — real values live in n8n Credentials. Only
  `n8n/workflow.sanitized.json` is committed; base, table and credential IDs are placeholders.
- Every push runs a secret/PII scan.
- The n8n editor is never exposed to the internet; only webhook endpoints are.
- The owner dashboard will be authenticated — it shows PII and a destructive cancel.
- **A finding from this build, recorded honestly:** the LLM webhook was discovered publicly reachable
  with no rate limit or spend cap. It was taken offline immediately and re-publishing is gated behind
  the Phase-5 brakes. Documented in [`docs/ARCHITECTURE-DECISIONS.md`](docs/ARCHITECTURE-DECISIONS.md).

---

## From demo to real

Everything runs today on mock config and a test endpoint. Going live for a client means their real
WhatsApp number, their calendar and their Airtable base — **no code change**, a new config file and new
credentials.

---

## Documentation

**[MASTER-BRIEF.md](MASTER-BRIEF.md)** — the current architecture ·
**[docs/ROADMAP.md](docs/ROADMAP.md)** — live phase status ·
**[docs/ARCHITECTURE-DECISIONS.md](docs/ARCHITECTURE-DECISIONS.md)** — every decision and why it changed ·
**[docs/DATA-MODEL.md](docs/DATA-MODEL.md)** — the data model.

MIT licensed. Built by [Neeidy](https://github.com/Neeidy) as a portfolio project in AI automation.
