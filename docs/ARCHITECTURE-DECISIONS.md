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
  · single-instance multi-tenancy · Facebook DM · autonomous multi-step agent · loyalty/reviews.
- **IN SCOPE (config-gated):** Instagram = config-gated optional channel (architecture-ready; per-client
  connection, default OFF). Deviates from the MASTER-BRIEF NOT-build snapshot — recorded in the decision log below.
- **IN SCOPE (v1 core, 2026-07-04 — deviates from MASTER-BRIEF NOT-build; see Final Feature Log):**
  cancel · reschedule · reminders.
- **Integrations + auth:** Zernio (WhatsApp) `✅ verified 2026-07-04 — official WhatsApp Business API BSP` ·
  Instagram DM (Meta Graph, optional) `⚠ verify` ·
  Google Calendar (OAuth per client) · Airtable · LLM (Claude/OpenAI) · n8n webhooks · Vercel.
  See MASTER-BRIEF §13 for unverified assumptions.
- **Verify at build time (additions to §13):** does Zernio support Instagram DM? · Meta IG API constraints
  (app-review lead time, business-account requirement, 24h messaging window) · Zernio/WhatsApp app-coexistence —
  with the bot API active, can the barber still message from their own app on the same number (needed for handoff)?
- **Mock plan + one-swap-to-real:** config-driven mock (services/prices/hours); demo via test WhatsApp/widget →
  live = client's real Zernio number + Google Calendar + Airtable base, no code change.

## 3. Stack
| Layer | Choice | Why | Alternative / exit |
|---|---|---|---|
| Engine | n8n (on RS) | deterministic-before-AI, visual, ownable | Make/Zapier |
| Channel | Zernio (WhatsApp) `✅ verified 2026-07-04` | per brief; official WhatsApp Business API BSP | WhatsApp Cloud API / 360dialog / Twilio |
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
| 2026-07-01 | `sender_key = "{channel}:{id}"` namespacing with the FULL channel name (matches the config channels enum), e.g. `whatsapp:+43…`, `instagram:12345` | prevents cross-channel ID collisions and state bleed in `conversations` | raw provider id as key; or channel-name shorthand (`wa:`/`ig:`) that drifts from the enum |
| 2026-07-01 | **Reply-to-origin-channel:** the `channel` field set at NORMALIZE travels the whole flow; the reply ALWAYS returns to the channel the message came from | a customer must never be answered on a different channel | single "default reply channel" |
| 2026-07-01 | **Instagram = IN SCOPE** as config-gated optional channel, default OFF; live IG connection is per-client (verify at build time: Meta app review, business account, 24h window). Facebook DM stays OUT. MASTER-BRIEF stays locked; this row records the deviation | architecture-ready now; connection cost deferred to per-client onboarding | rebuild-later (touches the brain twice) |
| 2026-07-02 | **Handoff mechanics (built in Phase 5):** the owner notification carries `sender + intent + filled slots + last N messages` → a `messages` log table is designed for this (with an explicit PII + TTL decision). While `stage: handoff`, the bot sends **no auto-reply** to that same sender (prevents human↔bot collision); the human joins the channel from their own WhatsApp Business / IG app | the owner needs full context to take over, and two responders on one thread confuse the customer | notify with a bare "someone needs help" ping; or let the bot keep replying alongside the human |
| 2026-07-02 | **Returning-customer touch (built in Phase 2):** the "load state" step also looks up the `customers` table; a known phone is greeted by name | cheap, deterministic personalization with data we already hold — no LLM needed | treat every inbound as a first-time stranger |
| 2026-07-02 | **Demo brand locale = EN/EUR** (target market is English-first); single source of truth: every mockup/demo value mirrors `config/client.config.example.json` (services EN + `priceEUR`, EN message templates) | one canonical place for demo copy/prices — no drift between config, schema and mockups | TR/₺ demo, or per-surface hardcoded values |
| 2026-07-02 | **Demo identity = English UI · EUR · Europe/Vienna** — one consistent single market (Yigitcan's location + the Beauty precedent) | a coherent demo reads as a real product; scattered locale/tz/currency looks unfinished | mixed identity (en-IE locale + Istanbul tz + € prices) |
| 2026-07-02 | **i18n (DE/EN) = OUT OF SCOPE (for now).** Architecture does not block it: UI copy comes from `config`/`messageTemplates`, so future DE/EN is a copy/i18n layer, not a code change — the `locale` field is already in place | ship one clean market now; the config-driven copy keeps the door open at zero rebuild cost | build a DE/EN toggle now (scope creep, no demand yet) |
| 2026-07-04 | **Cancel + reschedule + reminders = IN SCOPE (v1 core)** — bot-automated; deviates from the MASTER-BRIEF NOT-build snapshot (same pattern as the Instagram row: brief stays locked, deviation recorded here). Full detail in the Final Feature Log (§6) | booking lifecycle is core product value; handoff-only cancel breaks "zero owner effort" | keep them handoff-only |

## 6. Final Feature Log (locked 2026-07-04)

All items below are **IN SCOPE for v1** with a locked decision (no stubs). Schema/config changes
listed here are **DECISIONS ONLY** — implemented in their owning phase, not now.

### Booking lifecycle
- Cancel = **automated** in bot channels: phone-identity + explicit confirm + config
  `cancellationCutoffHours` (inside cutoff → no cancel, handoff/"call us") + idempotency
  + Google Calendar event delete + free the slot + confirm to customer. Zero owner effort. [Phase 3]
- Phone-call cancel = owner **one-click manual** from the dashboard (same automated chain). [Phase 3/6]
- Reschedule = **compose**: book the new slot first (verify availability) → then cancel the old;
  not a separate flow, same booking guardrails. [Phase 3]
- Reminder = **automated**, config `reminderHoursBefore` before the appointment. [Phase 3]
- **DECISION: Google Calendar = the SINGLE source of truth for availability** (owner blocks live in
  GCal too). Airtable = CRM/state mirror. Write order: **GCal FIRST, then Airtable**. [Phase 3]
- Owner calendar block: owner adds a "busy" event in GCal; availability = working hours − GCal busy. [Phase 3]
- **GCal-fail-visible:** if GCal OAuth drops/unreachable, the bot NEVER silently books →
  error branch + visible owner notification. [Phase 5]

### Security (director additions)
- **Dashboard authentication:** the dashboard holds PII + a destructive "Cancel" → owner-only,
  authenticated; never public without auth. [Phase 6]
- **Widget-cancel identity (IDOR prevention):** WhatsApp number = verified identity (safe);
  the widget has no number auth → widget-cancel requires a booking-ref/code. [Phase 3]

### Bot capabilities
- Config-driven FAQ/info (address · location · parking · walk-in · common questions) → bot answers. [Phase 2]
- One `client.config.json` → channel-agnostic n8n brain → ALL answers (FAQ included) identical on all
  ENABLED channels (web/WhatsApp/IG); the reply returns to the origin channel. IG default OFF. [Phase 2]

### Handoff
- On handoff the bot goes **SILENT** in that conversation (`conversations.stage=handoff`);
  the human continues in the **SAME thread**.

### WhatsApp transport (Zernio — VERIFIED, official WhatsApp Business API BSP)
- **Inbound:** Zernio pushes inbound messages to a webhook → received by a **generic n8n Webhook node**.
- **Outbound:** n8n **HTTP Request node** → Zernio REST messaging endpoint (free-form inside the 24h
  window; outside it, a Meta-approved template).
- **Handoff mechanics:** Zernio Inbox (WhatsApp DMs) — the owner replies from the Zernio dashboard,
  same number/thread. [Phase 4/5]
- **DECISION: the official `n8n-nodes-zernio` node is NOT used** (social-posting only; no WhatsApp).
  The WhatsApp channel = generic Webhook + HTTP Request against REST → **provider-agnostic**; a BSP swap
  (Twilio / 360dialog / Meta Cloud fallback) = URL/mapping change in the same 2 nodes.
- Reminders are business-initiated, mostly outside the 24h window → **Meta-approved TEMPLATE message**
  (paid, needs Meta approval). Write this into the reminder design.
- The client connects their own WABA (redirect/headless/dashboard); no Meta developer app needed,
  but WABA + number + template approval remain Meta rules.
- Endpoint paths are pulled in Phase 4 from the Zernio OpenAPI (docs.zernio.com/api/openapi) /
  llms-full.txt — routine lookup, not a risk gate. [Phase 4]

### Frontend
- Dark/light theme: landing + widget + dashboard. [Phase 6]

### Technical decisions (schemas updated in Phase 2/3 — DECISION ONLY now)
- `intent` enum additions: `cancel`, `reschedule`; slot addition: `appointmentRef`.
- `client.config` additions: `bot.cancellationCutoffHours`, `bot.reminderHoursBefore`,
  faq/info block, theme, widget bookingRef policy.

### Future (post-v1, NOT a phase)
- i18n (DE/EN) · voice agent (via Zernio Calling).

### Conscious v1 boundary (stated honestly in the Phase 7 README/case-study)
single chair / single calendar (no multi-staff) · no payments/deposits · no group bookings ·
no automated marketing.

## 7. Critical-Review Targets — additions (2026-07-04)

Rows 1–7 live in MASTER-BRIEF §9 (locked snapshot). These rows **extend** that table; the same
Codex gate applies (audited by the second tool before the owning phase is "done").

| # | What | Why critical (criterion) | Auditor | Status | Phase |
|---|---|---|---|---|---|
| 8 | Booking mutation via bot (cancel/reschedule = delete-write on real appointments) | 1 + 4 — irreversible + shared state | Codex | [ ] | Phase 3 |
| 9 | Dashboard auth (PII + destructive surface) | 3 — data leak / unauthorized destructive action | Codex | [ ] | Phase 6/7 |

<TODO: append decisions as phases progress>
