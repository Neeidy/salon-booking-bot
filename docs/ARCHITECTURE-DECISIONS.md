# Architecture Decisions — salon-booking-bot

> **Role of this file:** the decision **log / rationale + history** for this project's architecture.
> [../MASTER-BRIEF.md](../MASTER-BRIEF.md) = the **current architecture (versioned)**; this file records
> *why/when* each decision changed — the two never disagree. Live phase status is
> [ROADMAP.md](ROADMAP.md) (roadmap content lives there, not here).

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
| 2026-07-18 | **kill-switch + max-turns enforcement + `conversations.turn_count` pulled from Phase 5 into CP3** | a paid LLM must not be wired to inbound traffic with no brakes (MASTER-BRIEF §7 spend brakes); the guards run BEFORE the LLM call → 0 cost when tripped. The approved Phase-2 plan had placed these in Phase 5 — conscious deviation, recorded here (same pattern as the Instagram/cancel rows) | leave it brakeless until Phase 5 |
| 2026-07-27 | **CP5 deterministic FAQ = ONE `Answer FAQ` Code node** (config lookups keyed by `faqTopic`), NOT a 7-way Switch+Set fan-out | the roadmap phrased it "IF/Switch (deterministic)"; a Code node is equally deterministic (no LLM) and is unit-testable, whereas a 7-branch Switch each feeding its own Set node = ~14 nodes that bury the logic and break "the canvas teaches" ([n8n-conventions.md](../.claude/rules/n8n-conventions.md)). Spirit (deterministic-before-AI) honored; letter (Switch) not | 7-way Switch → 7 Set nodes |
| 2026-07-27 | **CP5 `computed_reply` (FAQ/lead pre-computed reply text) is carried to `Build Reply Payload` via a guarded node reference** (`$('Answer FAQ')` / `$('Build Lead State')` read only inside the always-run `intent` guard, so the branch-only node is never touched on other paths), NOT persisted as an Airtable column | `conversations` is the multi-turn STATE store; a per-turn transient reply is not state — a column would pollute the data model and add a needless write every turn | add a `computed_reply` column to `conversations` |
| 2026-07-27 | **`Route Intent` fallback → `Mark Handoff` (fail-safe), NOT `Save State`.** The fallback's job is to put an UNRECOGNISED / not-yet-handled intent somewhere SAFE. Wired to `Save State` the customer got a `[demo] classified as …` placeholder and nobody was alerted (`stage=handoff` never written); wired to `Mark Handoff` the customer gets an honest handoff reply, `stage=handoff` is written, and the CP6 silent-lock + Phase-5 owner-alert hook onto the right place. Aligns with [handoff.md](../.claude/rules/handoff.md) "abstain over guess". (Interim until CP5b gives `capture_lead` its own route; after that fallback only catches truly-unexpected intents.) | fallback → `Save State` (visible but wrong reply, zero owner awareness) |
| 2026-07-27 | **SECURITY FINDING → close the live LLM webhook until Phase-5 brakes.** `/webhook/barber-inbound` (the CP3/CP4 published workflow) is **publicly reachable through the Cloudflare tunnel with NO auth and NO spend brakes** — verified 2026-07-27 by an anonymous external `POST` (no n8n API key) returning the flow's `400 invalid_payload`; a *valid* payload would invoke Anthropic + Airtable writes with no cost-cap / rate-limit / bot-protection. This is exactly the cost-and-abuse surface [spend-safety.md](../.claude/rules/spend-safety.md) forbids, and the Phase-1/CP1 roadmap note already warned it must be closed once the LLM landed (CP3). **Decision:** take the production webhook OFFLINE (unpublish / deactivate / close the tunnel path) until the Phase-5 brakes (cost-cap · rate-limit · bot-protection · kill-switch) are in; CP5 draft testing continues via the canvas Test URL, which needs no public endpoint. Tracked as a **Phase-5 OPEN ITEM**. Secondary: editor root `/` returns 200 (n8n login SPA is public, not behind Cloudflare Access) — re-check under Critical-Review Target 7 (control-plane lockdown). | leave it live "because it's only a mock" — a frensiz public LLM endpoint is a real fatura+abuse liability regardless of mock data |

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

Rows 1–7 live in MASTER-BRIEF §9 (current architecture). These rows **extend** that table; the same
Codex gate applies (audited by the second tool before the owning phase is "done").

| # | What | Why critical (criterion) | Auditor | Status | Phase |
|---|---|---|---|---|---|
| 8 | Booking mutation via bot (cancel/reschedule = delete-write on real appointments) | 1 + 4 — irreversible + shared state | Codex | [ ] | Phase 3 |
| 9 | Dashboard auth (PII + destructive surface) | 3 — data leak / unauthorized destructive action | Codex | [ ] | Phase 6/7 |

<TODO: append decisions as phases progress>
