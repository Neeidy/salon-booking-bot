# Architecture Decisions — salon-booking-bot

> **Role of this file:** the **authoritative working record** of this project's architecture decisions —
> the living source of truth. The frozen snapshot is [../MASTER-BRIEF.md](../MASTER-BRIEF.md); live phase
> status is [ROADMAP.md](ROADMAP.md) (roadmap content lives there, not here).

## 1. Snapshot
- **Type:** automation-n8n + chatbot + web-app (config-driven template)
- **Complexity:** single-tenant-per-deployment (Model 1 = copy-per-client). **NOT** multi-tenant.
- **Tier:** T1 (Chatbot on the n8n substrate)
- **Who uses it:** end customer triggers (messages); shop owner consumes (calendar bookings + CRM leads)
- **Date:** 2026-06-30

## 2. The plan (locked)
- **Problem:** the barber loses leads / gets interrupted because WhatsApp/site messages aren't answered or booked instantly.
- **The ONE job:** turn an inbound message into a booked appointment — or a captured lead + human handoff — in the shop's voice.
- **Success metric:** % of inbound messages → booking or captured lead, with zero owner effort and **zero double-bookings**.
- **NOT-build (OUT OF SCOPE — permanent):** payments/prepay · POS/inventory · multi-staff rota · marketing blasts
  · single-instance multi-tenancy · Facebook DM · autonomous multi-step agent · loyalty/reviews ·
  reschedule/cancel (→ handoff) · time-based reminders.
- **IN SCOPE (config-gated):** Instagram = config-gated optional channel (architecture-ready; per-client
  connection, default OFF). Deviates from the MASTER-BRIEF NOT-build snapshot — recorded in the decision log below.
- **Integrations + auth:** Zernio (WhatsApp) `⚠ verify` · Instagram DM (Meta Graph, optional) `⚠ verify` ·
  Google Calendar (OAuth per client) · Airtable · LLM (Claude/OpenAI) · n8n webhooks · Vercel.
  See MASTER-BRIEF §13 for unverified assumptions.
- **Verify at build time (additions to §13):** does Zernio support Instagram DM? · Meta IG API constraints
  (app-review lead time, business-account requirement, 24h messaging window).
- **Mock plan + one-swap-to-real:** config-driven mock (services/prices/hours); demo via test WhatsApp/widget →
  live = client's real Zernio number + Google Calendar + Airtable base, no code change.

## 3. Stack
| Layer | Choice | Why | Alternative / exit |
|---|---|---|---|
| Engine | n8n (on RS) | deterministic-before-AI, visual, ownable | Make/Zapier |
| Channel | Zernio (WhatsApp) `⚠ verify` | per brief | WhatsApp Cloud API / 360dialog / Twilio |
| Calendar | Google Calendar | lands on owner's phone | — |
| Data/CRM | Airtable | fast, no SQL ops | Supabase (would raise tier) |
| LLM | Claude/OpenAI, cheap-first | intent extraction only | — |
| Frontend | Next.js on Vercel | one app, push-to-deploy | — |

## 4. Non-negotiables applied
- [x] Secrets in `.env`/Credentials; only `.env.example` committed (repo PUBLIC → PII also excluded)
- [x] Failures VISIBLE (n8n error branch)
- [x] LLM spend brakes: cost cap · max-iteration · timeout · dry-run · kill-switch (`spend-safety.md`)
- [x] Bot holds no prod write creds outside gated actions; action allow-list (book/capture-lead/answer-FAQ)
- [ ] (multi-tenant) — N/A: Model 1 is single-tenant-per-deployment by design

## 5. Decision log
| Date | Decision | Why | Rejected alternative |
|---|---|---|---|
| 2026-06-30 | Build from scratch, own template | resellable + portfolio | reuse "Beauty" |
| 2026-06-30 | Model 1 (copy-per-client) | isolated, avoids T3 multi-tenant risk | single-instance multi-tenant |
| 2026-06-30 | `n8n/` (not `builds/_TEMPLATE`) | one product, one engine | portfolio multi-build layout |
| 2026-06-30 | Split idempotency vs concurrency (write-then-verify) | no atomic lock across Airtable+GCal (TOCTOU) | assume a lock exists |
| 2026-06-30 | Scaffold before mockup | scaffold feeds from brief, needs no mockup | mockup-first |
| 2026-07-01 | **Config-gated optional channels:** every channel → NORMALIZE `{channel, sender_key, text}` → one shared brain; channels toggle in config and several may run at once (e.g. WhatsApp + Instagram) — the brain is channel-count-agnostic | one engine to maintain; adding a channel = one adapter + config, zero brain change | per-channel forked flows |
| 2026-07-01 | `sender_key = "{channel}:{id}"` namespacing (e.g. `wa:+90555…`, `ig:12345`) | prevents cross-channel ID collisions and state bleed in `conversations` | raw provider id as key |
| 2026-07-01 | **Reply-to-origin-channel:** the `channel` field set at NORMALIZE travels the whole flow; the reply ALWAYS returns to the channel the message came from | a customer must never be answered on a different channel | single "default reply channel" |
| 2026-07-01 | **Instagram = IN SCOPE** as config-gated optional channel, default OFF; live IG connection is per-client (verify at build time: Meta app review, business account, 24h window). Facebook DM stays OUT. MASTER-BRIEF stays locked; this row records the deviation | architecture-ready now; connection cost deferred to per-client onboarding | rebuild-later (touches the brain twice) |

<TODO: append decisions as phases progress>
