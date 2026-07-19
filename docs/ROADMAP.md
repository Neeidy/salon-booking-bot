# Roadmap — salon-booking-bot (live phase tracking)

> **Role of this file:** the SINGLE live source of phase status. Roadmap content lives ONLY here —
> [../MASTER-BRIEF.md](../MASTER-BRIEF.md) = the current architecture (versioned); live phase status lives here;
> [ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md) links here rather than duplicating.
> Update the checkboxes as phases complete. Order discipline: **works first (2–5), then shines (6).**

| ✓ | Phase | Work | Done criteria |
|---|---|---|---|
| ✅ | **0. Scaffold** | repo skeleton · `.claude/` governance · schemas · config example · docs | Skeleton + schemas in place — **done + pushed (`a74625d`)** |
| ✅ | **1. Visual blueprint** | landing + widget + dashboard **mockup** + flow diagram *(CC builds → commits; Cowork reviews from git)* | Visual demo **approved** — Cream & Ink locked, EN/EUR/Europe/Vienna, config-driven; 3 mockups on `main` |
| ▶ | **2. Core bot** | n8n: webhook → load state (+ customer lookup/greeting) → LLM intent → routing → slot-filling → reply (test via widget first) | Happy path + 2–3 intents, JSON valid, multi-turn slot-fill completes |
| ☐ | **3. Booking + data** | availability → write → re-verify → Google Calendar + Airtable · **cancel · reschedule · reminders (bot-automated)** · **GCal = availability source-of-truth (write GCal→Airtable)** · **widget-cancel booking-ref (IDOR)** · idempotency · timezone-UTC | Booking works; duplicate ≠ double-book; concurrent same-slot → one + handoff; cancel/reschedule mutate exactly one appointment safely |
| ☐ | **4. WhatsApp** | Zernio channel `✅ verified 2026-07-04` — generic Webhook + HTTP Request (`n8n-nodes-zernio` not used) · `⚠ Zernio IG DM support still open` · IG activation = per-client onboarding via docs/runbook (Meta requirements) — the config switch alone is not enough | Real WhatsApp message → booking + reply |
| ☐ | **5. Safety** | handoff (context + bot-silence + `messages` log) · cost cap · kill-switch · dry-run · max-iteration · injection · error branch — **note: kill-switch + max-turns partially landed early in CP3 (decision log 2026-07-18); Phase 5 completes the full suite** | Low conf → handoff; kill-switch works; errors visible; jailbreak caught |
| ☐ | **6. Vitrin frontend** | build Next.js landing + widget + dashboard → live data → Vercel · **design gaps: [PHASE-6-BACKLOG.md](PHASE-6-BACKLOG.md)** | Deployed, branded, reads live data |
| ☐ | **7. Test + Codex + DoD** | golden set · edge · jailbreak · critical-targets audit · sanitize · README/case-study | Full DoD checklist passes |
| ☐ | **8. Template-ize** | config-only swap → a second mock client | Config swap → working 2nd instance |

**Legend:** ▶ in progress · ☐ not started · ✅ done.

## Phase 2 — checkpoint progress (core bot, built in n8n)
Built as a checkpoint (CP) sequence in n8n (workflow `Salon Booking Bot — Main`); sanitized flow committed at
[../n8n/workflow.sanitized.json](../n8n/workflow.sanitized.json). Each CP is built → tested (verified via the n8n
execution API) → understood, one small step at a time. No production publish until safety brakes are in (LLM lands CP3).

- ✅ **CP0 — Echo skeleton:** Webhook → Normalize (adapter boundary; `sender_key = {channel}:{id}`) → Build Reply → Respond. Transport + reply-to-origin proven for both widget (`sessionId`) and whatsapp (`from`) shapes.
- ✅ **CP1 — Front gate:** + Load Config (MOCK client config) + Validate Payload (channel enabled in config · text present · length ≤ 1000) → invalid = **400** reject. 5-scenario test passed (valid ×2 → echo; disabled-channel / empty / oversized → reject).
- ✅ **CP2 — Conversation state (Airtable `conversations`):** Load State (search by `sender_key`) → Merge State (found/new; Airtable nests fields under `fields`) → Save State (upsert, `last_updated` in **UTC**). Multi-turn persistence + per-sender isolation proven (2 distinct rows). Airtable-failure branch → **503** wired + config-verified; live error-drill deferred to Phase 5.
- ▶ **CP3 — LLM intent (in progress):**
  - ✅ **3a Guards (built 2026-07-19):** `Check Bot Guards` runs BEFORE any LLM call — kill-switch (`bot.killSwitch`) + max-turns (`conversations.turn_count` < `bot.maxTurnsPerConversation`) → `Handoff Reply` (200), **0 cost**; else `Save State` (`turn_count +1`) → normal flow. Verified via execution API: counter 0→1→2 (one row per sender), 3 scenarios (pass · kill-switch trip · max-turns trip). Deviation logged (guards pulled Phase 5 → CP3, decision log 2026-07-18).
  - ☐ **3b–3c LLM intent (next):** free-text → Anthropic structured output → **ajv-validate vs committed `schemas/intent.schema.json`** → confidence <0.7 / cancel / reschedule / handoff / unknown → handoff. ⚠ LLM = real cost → **draft-only, no public publish** until Phase-5 brakes.

Not yet in the flow (scope guard): booking / Google Calendar (Phase 3) · WhatsApp / Zernio transport (Phase 4) ·
full handoff · kill-switch · injection hardening (Phase 5). Known robustness follow-ups (Phase 5): Code-node
error handling, `$json` in "Run Once for All Items" mode (safe while 1 item/exec).

## Critical-Review Targets (Codex gate — from MASTER-BRIEF §9)
1a idempotency · 1b concurrency/no-double-book · 2 Google Calendar write · 3 webhook verification ·
4 secret+PII handling · 5 handoff threshold · 6 error visibility · 7 n8n control-plane exposure ·
**8 booking mutation (cancel/reschedule)** · **9 dashboard auth** — see [ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md) §7 (added 2026-07-04).
