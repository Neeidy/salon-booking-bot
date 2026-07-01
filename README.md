# salon-booking-bot

> **Role of this file:** the public front door — what this is, its status, and how to run it.
> Architecture: [MASTER-BRIEF.md](MASTER-BRIEF.md) · decisions: [docs/ARCHITECTURE-DECISIONS.md](docs/ARCHITECTURE-DECISIONS.md) · live phases: [docs/ROADMAP.md](docs/ROADMAP.md).

**Status: learning / demo build.**

A config-driven, reusable salon **booking + lead-capture chatbot template** — it turns an incoming
WhatsApp/website message into a **booked appointment**, or a **captured lead + human handoff**,
automatically and in the shop's voice. One isolated deployment per client (**Model 1**).

## Stack
n8n (engine, on RS) · Zernio (WhatsApp) · Google Calendar · Airtable (CRM) · LLM (Claude/OpenAI,
cheap-model-first) · **Next.js** frontend on **Vercel**.

## Repo map
| Path | What |
|---|---|
| [`n8n/`](n8n/) | the engine — sanitized workflow export only |
| [`web/`](web/) | Next.js frontend (landing · widget · dashboard) — see [web/README.md](web/README.md) |
| [`config/`](config/) | per-client `client.config.json` (mock example committed) |
| [`schemas/`](schemas/) | JSON Schemas (intent · client config) |
| [`prompts/`](prompts/) | versioned LLM prompts |
| [`tests/`](tests/) | golden-set intents · jailbreak/injection cases |
| [`design/`](design/) | Phase 1 mockup + flow diagram |
| [`docs/`](docs/) | architecture decisions · data model · roadmap |

## One-swap-to-real
Everything is demo-able from config + a test WhatsApp number / the website widget. Going live for a client
= their real Zernio number + Google Calendar + Airtable base — **no code change** (a new `client.config.json`
+ new secrets).

## Security
This repo is **PUBLIC**. No secrets and no customer PII in git — real values live in n8n Credentials / Vercel
env. See [.claude/rules/security-secrets.md](.claude/rules/security-secrets.md).
