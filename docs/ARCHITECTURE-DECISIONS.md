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
| 2026-07-02 | **Returning-customer touch (Phase 2)** — ~~load state also looks up a `customers` table; a known phone is greeted by name~~ **SUPERSEDED 2026-08-10 (see the CP6 row below):** no `customers` table; the returning signal is `conversations.found` (already computed in `Merge State`), and there is no name to greet by until Phase 3 booking / lead-capture writes one | cheap, deterministic personalization with data we already hold — no LLM needed | treat every inbound as a first-time stranger |
| 2026-07-02 | **Demo brand locale = EN/EUR** (target market is English-first); single source of truth: every mockup/demo value mirrors `config/client.config.example.json` (services EN + `priceEUR`, EN message templates) | one canonical place for demo copy/prices — no drift between config, schema and mockups | TR/₺ demo, or per-surface hardcoded values |
| 2026-07-02 | **Demo identity = English UI · EUR · Europe/Vienna** — one consistent single market (Yigitcan's location + the Beauty precedent) | a coherent demo reads as a real product; scattered locale/tz/currency looks unfinished | mixed identity (en-IE locale + Istanbul tz + € prices) |
| 2026-07-02 | **i18n (DE/EN) = OUT OF SCOPE (for now).** Architecture does not block it: UI copy comes from `config`/`messageTemplates`, so future DE/EN is a copy/i18n layer, not a code change — the `locale` field is already in place | ship one clean market now; the config-driven copy keeps the door open at zero rebuild cost | build a DE/EN toggle now (scope creep, no demand yet) |
| 2026-07-04 | **Cancel + reschedule + reminders = IN SCOPE (v1 core)** — bot-automated; deviates from the MASTER-BRIEF NOT-build snapshot (same pattern as the Instagram row: brief stays locked, deviation recorded here). Full detail in the Final Feature Log (§6) | booking lifecycle is core product value; handoff-only cancel breaks "zero owner effort" | keep them handoff-only |
| 2026-07-18 | **kill-switch + max-turns enforcement + `conversations.turn_count` pulled from Phase 5 into CP3** | a paid LLM must not be wired to inbound traffic with no brakes (MASTER-BRIEF §7 spend brakes); the guards run BEFORE the LLM call → 0 cost when tripped. The approved Phase-2 plan had placed these in Phase 5 — conscious deviation, recorded here (same pattern as the Instagram/cancel rows) | leave it brakeless until Phase 5 |
| 2026-07-27 | **CP5 deterministic FAQ = ONE `Answer FAQ` Code node** (config lookups keyed by `faqTopic`), NOT a 7-way Switch+Set fan-out | the roadmap phrased it "IF/Switch (deterministic)"; a Code node is equally deterministic (no LLM) and is unit-testable, whereas a 7-branch Switch each feeding its own Set node = ~14 nodes that bury the logic and break "the canvas teaches" ([n8n-conventions.md](../.claude/rules/n8n-conventions.md)). Spirit (deterministic-before-AI) honored; letter (Switch) not | 7-way Switch → 7 Set nodes |
| 2026-07-27 | **CP5 `computed_reply` (FAQ/lead pre-computed reply text) is carried to `Build Reply Payload` via a guarded node reference** (`$('Answer FAQ')` / `$('Build Lead State')` read only inside the always-run `intent` guard, so the branch-only node is never touched on other paths), NOT persisted as an Airtable column | `conversations` is the multi-turn STATE store; a per-turn transient reply is not state — a column would pollute the data model and add a needless write every turn | add a `computed_reply` column to `conversations` |
| 2026-08-09 | **CP5b: a lead-write failure gets its OWN `Lead Unavailable Reply` (503, `error:"lead_unavailable"`), not the shared `Send Error Response` (`state_unavailable`).** `Capture Lead`'s error output routes to a dedicated 503 node so the machine side distinguishes a leads-table write failure from a conversations-state write failure — a Phase-5 owner-alert can hook the right node. Deviates from the CP5 plan (which said reuse `Send Error Response`); the deviation is the improvement [n8n-conventions](../.claude/rules/n8n-conventions.md) asks for ("a distinct response from its own node"). Verified by a live drill: bogus table id → forced write failure → `503 lead_unavailable` + Save State skipped (no conversations row = no false success), then reverted. | reuse `Send Error Response` (mislabels a lead failure as `state_unavailable`, owner-alert can't tell them apart) |
| 2026-07-27 | **`Route Intent` fallback → `Mark Handoff` (fail-safe), NOT `Save State`.** The fallback's job is to put an UNRECOGNISED / not-yet-handled intent somewhere SAFE. Wired to `Save State` the customer got a `[demo] classified as …` placeholder and nobody was alerted (`stage=handoff` never written); wired to `Mark Handoff` the customer gets an honest handoff reply, `stage=handoff` is written, and the CP6 silent-lock + Phase-5 owner-alert hook onto the right place. Aligns with [handoff.md](../.claude/rules/handoff.md) "abstain over guess". (Interim until CP5b gives `capture_lead` its own route; after that fallback only catches truly-unexpected intents.) | fallback → `Save State` (visible but wrong reply, zero owner awareness) |
| 2026-07-27 | **SECURITY FINDING → close the live LLM webhook until Phase-5 brakes.** `/webhook/barber-inbound` (the CP3/CP4 published workflow) is **publicly reachable through the Cloudflare tunnel with NO auth and NO spend brakes** — verified 2026-07-27 by an anonymous external `POST` (no n8n API key) returning the flow's `400 invalid_payload`; a *valid* payload would invoke Anthropic + Airtable writes with no cost-cap / rate-limit / bot-protection. This is exactly the cost-and-abuse surface [spend-safety.md](../.claude/rules/spend-safety.md) forbids, and the Phase-1/CP1 roadmap note already warned it must be closed once the LLM landed (CP3). **Decision:** take the production webhook OFFLINE (unpublish / deactivate / close the tunnel path) until the Phase-5 brakes (cost-cap · rate-limit · bot-protection · kill-switch) are in; CP5 draft testing continues via the canvas Test URL, which needs no public endpoint. Tracked as a **Phase-5 OPEN ITEM**. Secondary: editor root `/` returns 200 (n8n login SPA is public, not behind Cloudflare Access) — re-check under Critical-Review Target 7 (control-plane lockdown). | leave it live "because it's only a mock" — a frensiz public LLM endpoint is a real fatura+abuse liability regardless of mock data |
| 2026-08-10 | **CP6: drop the `customers` table; returning-customer greeting uses `conversations.found` + a session-gap** (`now − last_updated_prev > bot.sessionGapMinutes`, both compared in **UTC**). Supersedes the 2026-07-02 "greet by name / customers table" row above | `conversations.found` (computed in `Merge State`) already answers "seen this sender before?" deterministically; we hold **no** customer name/profile until Phase 3 booking or lead-capture writes one, so a `customers` table would store nothing new — building it now violates "no new table before a real trigger" (master-architecture). The trigger arrives in Phase 3. `found` alone would spam "Welcome back" every turn, so the session-gap gates it to a genuinely new session | build the `customers` table now (speculative, empty); or greet on bare `found` (spams every turn) |
| 2026-08-10 | **CP6: handoff silent-lock = a dedicated `Check Handoff Lock` IF (after `Merge State`) → `Handoff Lock Reply` (200, no LLM, no `Save State`).** A thread already at `stage='handoff'` short-circuits BEFORE the LLM call: zero LLM cost, no `turn_count` increment, no state overwrite, and the bot never talks over the human. Only intent-handoff (`Mark Handoff` → `Save State`) writes `stage='handoff'`; a transient guard-trip writes no state, so it never locks. **Release is manual** for the mock: the owner clears `stage` in Airtable (automated release is Phase 5+). **Phase 5:** the owner-alert (Telegram) also hooks `Handoff Lock Reply` (a new message on a locked thread → owner pinged) so a locked customer is not left in silence | keep the bot replying alongside the human; or spend an LLM call per locked message; or auto-release the lock now (no signal for it yet) |

| 2026-08-15 | **Google Calendar = service account + calendar-share, via HTTP Request (NOT the built-in Google Calendar node, NOT per-client OAuth).** The n8n Google Calendar node is OAuth2-only; and per-client OAuth carries consent-screen + unverified-app + sensitive-scope verification + 100-test-user friction on every client. Service account: the client shares their calendar with the SA email ("Make changes to events") — no consent/verification/limit. n8n: HTTP Request node + generic "Google Service Account" (`googleApi`) credential; n8n's engine mints the JWT (the Code-node `require()` ban doesn't apply). Availability via `freeBusy.query` (lightweight, only busy intervals — no event-detail leakage). **Proven live on this instance** (freeBusy → 200, exec 62). Same provider-agnostic HTTP pattern as Zernio/Anthropic. **Gotcha:** never send `attendees` in `events.insert` (SA can't invite without domain-wide delegation); customer notice goes via the channel. MASTER-BRIEF §13 GCal item → RESOLVED. | built-in Google Calendar node (OAuth2-only, unusable here); per-client OAuth (onboarding friction) |

| 2026-08-15 | **CP2 dual-write failure policy — GCal = source of truth, Airtable = mirror.** If the **GCal write succeeds the booking is REAL** → always tell the customer "booked", EVEN IF the Airtable `appointments` mirror write then fails. On mirror-fail: send the customer NO error (a customer-facing error → they retry → **double-booking**); instead raise a visible owner-alert (`appointment_mirror_failed`) AND persist the `gcal_event_id` into `conversations` state so the mirror can be repaired later. A `503 appointment_unavailable` is returned **only** when the GCal write ITSELF fails (no real booking exists). | tell the customer an error on mirror-fail (retry → double-book) |
| 2026-08-15 | **CP2 write-then-verify deletes ALWAYS our own just-created event** (the `gcal_event_id` returned by `events.insert`), NEVER a pre-existing one. Positional logic ("delete the first overlapping") is FORBIDDEN — deleting the wrong event destroys another customer's real, irreversible booking. On >1 overlap after our write: delete OUR event → the pre-existing booking survives → tell the customer "that slot was just taken" + alternatives / handoff. | delete "the first" / positional (can destroy someone else's real booking) |
| 2026-08-16 | **CP2b verify-read failure returns 200, NOT the infra-class 503.** The post-write `Verify Slot` read can fail (calendar down) *after* the event is already written. We do NOT delete on a read-failure (could cancel a legit sole booking) and we do NOT 503: a 503 makes the channel provider RETRY → a second `events.insert` → double-book. Instead: keep the event, `stage=handoff` + `verify_unavailable` flag + persist `gcal_event_id`, 200. A conscious exception to `handoff.md`'s infra-class=5xx (justified: state was already written, so it is not a transient no-op). Proven live (exec 78). | 503 (would trigger provider retry → double-book) |
| 2026-08-16 | **CP2b implements the line-81 mirror-fail VISIBILITY now (was to be CP2c).** `Write Appointment` error output routes to a distinct **`Build Mirror-Failed State`** (`mirror_failed` flag, keeps `gcal_event_id`, still confirms "booked" since GCal is authoritative) instead of silently sharing the success node — closing a `flow-reviewer`+`qa-tester` FAIL (repo's "failures are VISIBLE" hard rule). A `conversations.gcal_event_id` column was created and mapped in `Save State` (pulled forward from CP2c) so the orphan / verify-unavailable / mirror-fail states persist the stray/authoritative event id for owner repair. Owner-alert that consumes these flags is still Phase 5. Proven live (orphan exec 79, mirror-fail branch verified-by-construction). | leave mirror-fail silent until CP2c (silent double-write failure, forbidden) |
| 2026-08-16 | **CP2b concurrency guard is best-effort, NOT an atomic lock — accepted limitation (honest).** Write-then-verify over GCal+Airtable (no cross-store transaction) NARROWS the TOCTOU window but cannot close it: (a) two NEW simultaneous writers both yield → slot ends empty (safe = no double-book, but not "exactly one"); (b) it assumes GCal `events.list` read-your-writes — if both verifies miss each other's insert, a real double-book slips through. A deterministic min-id tie-breaker was REJECTED (unsafe vs a manually-added event that never runs verify → could keep both). Mitigations taken: always yield on any other overlap (over-yield = safe); `Insert→Verify` is a direct edge (no LLM/extra read) to keep the read-after-write window tight. **Real fix = a DB `UNIQUE(date,time)` constraint** (the DB rejects the concurrent 2nd insert); deliberately NOT taken — adding Postgres is a T1→T2 tier bump. Concurrency path is correct-by-construction but could not be live-tested (one-shot test webhook). Idempotency (`processed_messages`) = CP2c. | pretend the guard is airtight; add a min-id tie-breaker (unsafe); add Postgres now (tier creep) |
| 2026-08-16 | **Codex L3 audit of Critical-Review-Target 1b (concurrency/no-double-book) — 5 findings, all addressed.** **#1 (BUG, live):** `Write Appointment.gcal_event_id` read `$json.id`, but post-CP2b its input is `Check Race`, which emits `gcal_event_id` (not `id`) → the mirror row's id wrote EMPTY (CP3 cancel / CP4 reschedule could not find the event — silent) → fixed to `$json.gcal_event_id`, re-tested (appointments row `recpFCMELzE60xEqs` now filled). **#2 (CRITICAL):** all post-write outcome branches hit `Save State`, whose error returned the pre-write `503 state_unavailable` → a provider retry re-books (and a mirror-failure — itself an Airtable fault — makes Save State likely fail too, so the guard broke itself) → added a `_post_write` flag on all 5 outcome builders + a `Classify State-Write Failure` IF routing post-write Save-State failures to a **200 `Booking State-Unsaved Reply`** (booking is real via GCal; `gcal_event_id` stays visible); pre-write branches still return 503. **#3** (ambiguous insert / timeout reconcile) → folded into **CP2c-ii** (deterministic event-id + GET reconcile before any 503). **#4:** `Verify Slot` ignored `nextPageToken` → `maxResults` raised to 250 + `Check Race` fails safe (yield) on any `nextPageToken`. **#5:** all-day events parsed at UTC midnight → `Check Race` now parses `start.date` at shop-tz. **HELD (Codex confirmed):** delete-our-only invariant; the documented symmetric-race + read-your-writes limits (no invented lock/DB fix). Re-audit scheduled after push. | leave #1 (silent unbookable) / #2 (retry → double-book) unfixed |
| 2026-08-16 | **Codex L3 re-audit round 2 (target 1b) — method correction + 2 MEDIUM/LOW, all addressed; EXIT CRITERION set.** **#2 came back:** the re-audit proved the flag approach failed — the Airtable error item carries ONLY `{message, error}`, NOT the input fields (confirmed empirically, exec 84), so `Classify State-Write Failure` read `$json._post_write` = undefined → 503. **Method change:** a SEPARATE `Save State (Post-Write)` node whose error output routes to the 200 `Booking State-Unsaved Reply` by **TOPOLOGY**, not by reading the error item; the recovery reply is rebuilt via **node refs** (`$('Build Booked State')…`). **Drill-proven** (exec 84: broke the node → HTTP 200 `{reply, state_unsaved, gcal_event_id}`, never 503). **Lesson:** error-path behaviour is verified EMPIRICALLY (a live error-drill), never "by-construction". **#3 (all-day, MEDIUM):** `Check Race` reads the calendar's own `timeZone` and fails safe (yield + `verify_incomplete`) when it != shop tz; demo calendar confirmed `Europe/Vienna`. **#4 (verify-incomplete, LOW):** an incomplete verify (pagination or tz-mismatch) yields with a NEUTRAL `verifyIncomplete` message ("couldn't finish confirming"), not the misleading "just taken"; delete behaviour unchanged. **EXIT CRITERION for CRT #1b:** CLOSED when all CRITICAL+HIGH are closed AND remaining MEDIUM/LOW are fixed or accepted-with-rationale; then ONE re-audit — if the bar holds the target is CLOSED and we move on; NO third round unless a NEW CRITICAL appears. | keep the disproven flag-on-error-item approach |
| 2026-08-16 | **Codex L3 audit of CRT #1b — AUDIT LOOP CLOSED (3 rounds).** Round 1: 5 findings (one live bug — `gcal_event_id` written empty). Round 2: the post-write classifier method was wrong (a flag does not survive the Airtable error item) → switched to a TOPOLOGICAL split (`Save State (Post-Write)`), proven by a live drill (exec 84). Round 3: 6/6 write-then-verify invariants HOLD, no new defect, no MEDIUM/LOW outstanding. The only CRITICAL left open (#1 ambiguous insert) is the already-planned CP2c-ii work — Codex confirmed it is not a new finding from `082e027`. **The audit loop is closed; the target closes on CP2c-ii landing** (verified by a targeted #1-only check, not a full re-audit). **Accepted design limits (not findings):** in a symmetric race both writers may withdraw (slot ends empty — safe, not "exactly one"); write-then-verify relies on seeing the other writer's insert (GCal read-your-writes) — the real fix is a DB unique constraint, deliberately not taken at T1 tier. | reopen a full re-audit after every change / treat the accepted tier limits as blocking findings |
| 2026-08-16 | **Codex targeted #1 re-check on CP2c-ii — 3 real defects in the deterministic event-id, all fixed.** **(HIGH) Encoder collision:** `Array.from(bkey).map(c => c.charCodeAt(0)…)` takes the first UTF-16 unit of each code point, so astral chars (😀/😁) truncate to the SAME byte → SAME event id (Cowork reproduced: both → `…d83d…`). Security impact: `sender_key` is client-supplied, so a crafted sessionId could produce a colliding id and reconcile onto ANOTHER customer's event (falsely "booked") or, in a race, have Cancel Our Event delete the victim's event. **Fix:** UTF-8 byte encoding `Array.from(new TextEncoder().encode(bkey)).map(b => b.toString(16).padStart(2,'0'))` — injective, no dependency. **`require('crypto')`/SHA-256 was NOT used — this instance blocks require (see [[n8n-code-node-no-require]]);** TextEncoder is a global. Proven: isolation (charCodeAt collides, UTF-8 distinct `f09f9880`≠`f09f9881`) + live (TextEncoder runs in the Code node, event id == expected UTF-8 hex). **(front gate) Input guard:** a 500-char sessionId made a 1064-char id (>1024, invalid for Google). Added a `Validate Payload` senderId guard `^[A-Za-z0-9:+._-]{3,80}$` (kills the astral class AND the length overflow at the root; proven live — emoji sender → 400) + a pre-insert `Event ID Valid?` (`^[0-9a-v]{5,1024}$`) → handoff if malformed. **(reconcile) 5xx-while-unresolved:** the reconcile GET's failure output returned a blanket 503. Now `Classify Reconcile Failure` splits a DEFINITE 404 (event never created → 503, retry-safe) from UNRESOLVED (timeout/transport/5xx → 200 handoff with the id visible, no retry loop; the deterministic id already prevents a double-book). Reconcile-handoff states now route through `Save State (Post-Write)` so a state-write failure never falls to the pre-write 503 (by-construction, Codex-accepted). | SHA-256 via require (blocked here); leave the surrogate-truncating encoder; blanket-503 on any reconcile failure |
| 2026-08-16 | **Codex root-cause behind the event-id collision: `serviceId` was never validated against the config allow-list.** The encoder collision (row above) was a SYMPTOM. Root defect: `Merge Slots` only carried serviceId, `Slot Gate` only checked presence (`!!serviceId`), and `Build Event Request` **silently fell back** (`dur = svc ? svc.durationMin : 30; svcName = svc ? svc.name : slots.serviceId`) — so an LLM-invented `serviceId:"coloring"` would write a non-existent 30-min service to the calendar and say "booked", silently. (In the approved CP4 plan, unimplemented.) **Fix — close the cause:** `Merge Slots` drops any serviceId not in `config.services`; `Slot Gate` enforces the allow-list (`hasService = present && in-config`) → invalid → re-ask `askService`, never the booking path; `Build Event Request` drops the silent fallback → **throws fail-loud** if the service is missing, and asserts the booking key is ASCII (defense-in-depth). This also closes the Unicode collision at the root — only known ASCII config ids reach the event key. **A live test caught a second layer:** an Airtable upsert skips a null field, so a dropped serviceId lingered in `conversations.slot_service` and mis-drove the re-ask → `Save State` now writes `|| ''` to CLEAR nulled slots. Verified live: invalid `coloring` → askService (lists the real services), NOT booked; valid `haircut` → booked (regression). | fix only the encoder symptom and leave the missing allow-list; trust "by-construction" (the upsert-skips-null bug only surfaced under a live test) |

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
