# Barber Booking Bot — MASTER BRIEF
*(Cowork → Claude Code handoff · approved architecture + roadmap)*

> **What this is:** the **approved** master architecture for a config-driven, reusable salon
> lead-capture + booking chatbot **template** (Model 1 — one isolated deployment per client).
> Produced in Cowork (architecture/brain). Hand this to **Claude Code on the RS**; CC runs
> `/repo-scaffold` from it, then builds Phases 0→8. **Cowork stays the brain** (architecture,
> review, teaching); **CC is the builder**; **Yigitcan** does hands-on approvals + the n8n editor work.

---

## 1. Operating protocol for Claude Code (READ FIRST)

- **This master architecture is ALREADY APPROVED.** Do **not** relitigate tier / stack / scope. Execute it.
- **PLAN MODE GATE — per phase.** Before building each phase, enter CC **plan mode** → produce that
  phase's *implementation* plan (files/nodes, acceptance criteria, test) → get Yigitcan's explicit
  **"approved"** → only then build. (The architecture is the approved top plan; plan mode operates at the
  *phase* level, not to re-plan the whole system.)
- **Automation-fit declaration (per phase).** Every phase's plan-mode plan must state whether **`/loop` or
  `/goal`** fits that phase and how — or explicitly say **"neither"** (rationale in §11).
- **One small verifiable step at a time.** Build a piece → test it → confirm understanding → next. No big jumps.
- **Teach-while-build.** Explain WHAT / WHY / HOW; Yigitcan performs the hands-on actions (especially n8n
  nodes). No black boxes.
- **Secrets & PII — repo is PUBLIC.** `.env` gitignored; real keys live in **n8n Credentials / Vercel env**.
  Never commit or paste secrets. Only **sanitized** n8n exports are committed — sanitize strips **both
  secrets AND customer PII** (pinned/test data: real phone numbers, names) before any commit.
- **Critical-Review Targets (§9):** each must be **audited by a second tool (Codex)** before a phase is "done".
- **Failures must be VISIBLE** (error branch / notify). Silent failure is forbidden.
- **Definition of Done / phase:** built · tested (happy + edge) · cleaned · sanitized · README/case-study ·
  (Loom if relevant) · pushed.

## 2. Division of labor

| Who | Role |
|---|---|
| **Cowork (brain)** | architecture · brainstorming · review/audit (**from git**) · teaching · briefs. **Not building** — incl. the Phase 1 mockup: CC builds it, Cowork reviews it from git. |
| **Claude Code (RS)** | scaffolding · code · config · **builds all artifacts incl. the mockup** · commits/push. Builds Phases 0→8. |
| **Yigitcan** | hands-on (n8n editor, approvals, deploys) · final judge. |

**Review / test / audit = defense-in-depth (multiple independent layers, not one set of eyes):**
- **L1 — Claude Code:** builds + self-checks its own output.
- **L2 — repo's own `.claude/agents`** (scaffold generates them): `code-reviewer` · `qa-tester` · `security-auditor` → automated review / test / secret-scan on every build.
- **L3 — Codex** (independent second tool): audits the §9 Critical-Review Targets — **gate** before a phase is "done".
- **L4 — Cowork:** architectural review (from git) + teaching.
- **L5 — Yigitcan:** final human approval gate (plan-mode approval, deploys).

Each layer catches a different class of error → no single point of dependency.

## 3. Project identity

- **Name:** Barber Booking Bot (config-driven salon template).
- **The one job:** turn an incoming WhatsApp/website message into a **booked appointment** — or a
  **captured lead + human handoff** — automatically, in the shop's voice.
- **Success metric:** % of inbound messages that become a booked appointment or captured lead, with
  **zero owner effort** and **zero double-bookings**.
- **Tier:** **T1** (Chatbot, on n8n) · single-tenant-per-deployment (Model 1). **NOT** T2/T3.
- **Blueprint:** B (Chatbot) implemented on the A (n8n Workflow) substrate.

## 4. Pre-build brief

- **Problem:** the barber loses leads and gets interrupted because WhatsApp/site messages aren't answered
  or booked instantly.
- **User:** triggers = the **end customer** (messages); consumes = the **shop owner** (bookings on
  calendar + leads in dashboard).
- **NOT-build (OUT OF SCOPE — permanent boundary):** online payment/prepay · POS/inventory · multi-staff rota ·
  marketing/email blasts · single-instance multi-tenancy (we use copy-per-client) · Instagram/FB DM ·
  autonomous multi-step agent · loyalty/reviews · **reschedule/cancel an existing booking
  (OUT OF SCOPE → human handoff)** · **time-based reminders (scheduled flow — OUT OF SCOPE)**.
  *(IN SCOPE: the immediate booking-confirmation reply.)*
- **Integrations:** Zernio (WhatsApp) `⚠ verify §13` · Google Calendar (OAuth per client) `⚠ verify §13` ·
  Airtable `⚠ verify limits §13` · LLM (Claude/OpenAI, cheap-model-first) · n8n webhooks · Vercel (frontend).
- **Mock plan:** services/prices/hours come from config (mock); demo via a test WhatsApp number / the
  website widget. **One-swap-to-real** = client's real Zernio number + Google Calendar + Airtable base.

## 5. Architecture — components & where each runs

| Piece | Develops on | Runs on |
|---|---|---|
| Repo / code | RS (VS Code Remote-SSH) | **GitHub** (source of truth) |
| n8n flows (engine/brain) | RS n8n editor | **RS** (Cloudflare tunnel — **webhook endpoints only; editor/admin UI never public**) |
| Frontend (landing + chat widget + owner dashboard) | repo | **Vercel** (push-to-deploy) |
| Data (leads/customers/appointments) | — | **Airtable** (cloud) |
| Appointments (owner's phone) | — | **Google Calendar** (cloud) |
| LLM | — | Claude/OpenAI API |
| Channels | — | WhatsApp (Zernio) + website widget |

## 6. Config / Code / Secret separation (the template mechanism)

- **CODE** — identical engine + frontend for every client. Never changes per client.
- **CONFIG** (non-secret, per client) — `client.config.json`: business name, branding, services + prices,
  working hours, timezone, bot tone, message templates.
- **SECRET** (per client) — n8n Credentials / `.env` / Vercel env: Zernio token, Google Calendar OAuth,
  Airtable key, LLM key.
- **New client = new `client.config.json` + new secrets. No code change.**

## 7. Mandatory core controls (T1 chatbot)

- **Human handoff on low confidence** — **confidence < 0.7 → handoff** (starting threshold, aligned with
  n8n-conventions; tune with real data). Below-threshold behavior = **abstain / fallback → human handoff**
  (never guess the action). *(LLM self-reported confidence is poorly calibrated → prefer intent-classification
  + abstain over trusting a raw self-score.)*
- **Spend / safety brakes** — token/cost cap · timeout · **max-iteration (per-conversation max turns)** ·
  **dry-run default** · **global kill-switch** (force bot into handoff-only mode).
- **Prompt injection = data, not instructions** — allow-list actions: book / capture-lead / answer-FAQ;
  no other write.
- **Structured-output JSON-schema validation** — schema-fail (invalid JSON) → **error branch + handoff
  (VISIBLE)** + bounded retry; never a silent infinite retry.
- **Error branch visible** — no silent failure.
- **Idempotency** (same message processed twice) — dedupe on message-ID via a **persistent store**
  (Airtable `processed_messages` + TTL). *This alone does NOT prevent double-booking.*
- **Concurrency / no-double-book** (two *different* customers, same slot, ~same time) — **no atomic lock**
  across Airtable + Google Calendar (TOCTOU between availability-check and write). Guard =
  **write-then-verify**: write → re-read the slot → if >1 event, cancel one + handoff. The race must be
  **visible + recoverable**; don't pretend a lock exists.
- **Webhook verification** — Zernio = HMAC signature verify; **website widget = no shared secret**
  (runs in browser) → rate-limit + bot-protection (Turnstile / short-lived token) + payload validation.
- **n8n control-plane locked down** — via the Cloudflare tunnel expose **only the webhook endpoints**;
  the n8n **editor/admin UI is never on the public internet** (behind auth / Cloudflare Access).
- **Secrets only in Credentials / `.env`** — never in git (repo is PUBLIC); sanitize **PII** too.

## 8. Data flow

```
[Customer]
  ├ WhatsApp ──(Zernio webhook)──┐
  └ Website widget ──(webhook)───┤
                                  ▼
                         [n8n · RS]  ← engine/brain
   0) Load conversation state (Airtable `conversations`, keyed by sender) → merge prior slots
   1) LLM intent extract → JSON {intent, confidence, slots} → schema-validate (fail → error + handoff)
   2) Route: deterministic (menu/price/hours/slots = IF/Switch) · free text → LLM
   3) Slot-fill: missing slot (service/date/time) → ask + save state → loop until complete
   4) Act: ├ Book → only when slots complete → availability check → write Cal + Airtable
           │        → re-verify slot (no atomic lock; >1 event → cancel one + handoff)
           ├ Capture lead → Airtable
           └ Answer FAQ (from config)
   5) confidence < 0.7 → Human handoff (notify owner)
   6) any failure → Error branch (VISIBLE notify)
                                  ▼
                    reply → (Zernio / widget) → Customer

[Owner] sees: Google Calendar (phone = appointments) · Dashboard (lead/customer CRM) · handoff/error alerts
```

> **Conversation state (multi-turn / slot-filling):** each inbound message is a separate **stateless**
> n8n execution. Dialog state lives in Airtable `conversations` (keyed by sender: `stage` · collected
> slots `service/date/time` · `last_updated`). Every message **loads context → fills the missing slot →
> books ONLY when all slots are complete**. Simple slot-filling state machine; stays T1.

## 9. Critical-Review Targets (Codex audit — gate before "done")

| # | What | Why critical (criterion) | Status |
|---|---|---|---|
| 1a | Idempotency — same message twice → one booking (dedupe store + TTL) | 4 — shared state | [ ] |
| 1b | Concurrency / no-double-book — two customers, same slot; **no atomic lock** → write-then-verify | 4 — race / TOCTOU | [ ] |
| 2 | Google Calendar write (external, hard to undo) | 1 — irreversible | [ ] |
| 3 | Webhook verification — Zernio HMAC + widget (no secret → rate-limit/bot-protect) | 1/3 — origin/leak | [ ] |
| 4 | Secret + PII handling in a PUBLIC repo | 3 — data leak | [ ] |
| 5 | Human-handoff threshold (low-confidence → human) | 1/5 — wrong action / silent | [ ] |
| 6 | Error visibility (no silent failure) | 5 — silent failure | [ ] |
| 7 | n8n control-plane exposure — only webhook endpoints public; editor/admin UI never on the internet (behind auth / Cloudflare Access) | 1/3 — admin takeover | [ ] |

## 10. Roadmap (Phase 0 → 8) + Definition of Done

| Phase | Work | Done criteria |
|---|---|---|
| **0. Scaffold** | `/repo-scaffold` → repo · `.env.example` · `client.config.json` schema · Airtable tables (incl. `conversations`, `processed_messages`) · intent JSON schema · ARCHITECTURE-DECISIONS.md *(analyzes this brief first; needs no mockup)* | Skeleton + schemas in place |
| **1. Visual blueprint** | landing + chat widget + owner dashboard **mockup** + flow diagram *(CC builds → commits; Cowork reviews from git)* | Visual demo approved, gaps logged |
| **2. Core bot** | n8n: webhook → load conversation state → LLM intent → routing → **slot-filling state machine** (`conversations`) → reply (test via website widget first) | Happy path + 2–3 intents work, JSON valid, multi-turn slot-fill completes |
| **3. Booking + data** | availability → write → **re-verify (no atomic lock)** → Google Calendar + Airtable · idempotency (dedupe store + TTL) · **timezone-explicit (store UTC)** | Booking works; duplicate trigger ≠ double-booking; concurrent same-slot → one booking + handoff; edge cases |
| **4. WhatsApp** | Zernio channel `⚠ verify BSP/n8n — §13` | Real WhatsApp message → booking + reply |
| **5. Safety** | handoff · cost cap · **kill-switch · dry-run default · max-iteration** · injection handling · error branch | Low confidence → handoff; kill-switch works; errors visible; jailbreak attempt caught |
| **6. Vitrin frontend** | build landing + widget + owner dashboard (from Phase 0) → live data → Vercel | Deployed, branded, reads live data |
| **7. Test + Codex + DoD** | golden set · edge · jailbreak · critical-targets audit · sanitize · README/case-study · Loom | Full DoD checklist passes |
| **8. Template-ize** | config-only swap → a second mock client | Config swap produces a working 2nd instance |

> **Order discipline:** *works first (Phases 2–5), then shines (Phase 6).* Strong showcase, solid core.

## 11. Where `/repo-scaffold`, `/loop`, and `/goal` are used

- **`/repo-scaffold` — once, at Phase 0 (the first build step).** It *analyzes this brief first*, then
  tailors the repo folder structure + `.claude/` governance + `ARCHITECTURE-DECISIONS.md` to this system
  (it does not blindly stamp a template). It needs no mockup — the mockup (Phase 1) is built into the
  scaffolded structure afterwards.
- **`/loop <interval> <prompt>` —** a **session-level scheduler** (runs a prompt every X minutes while the
  session is open). **NOT** an auto-build/iterate mode. In THIS build use it only as a side convenience:
  - **Phase 6** — watch a Vercel deploy: `/loop 2m check if the Vercel deployment is ready and report`.
  - **Phase 3/4** — poll a test webhook / n8n execution while you work on something else.
  - **Do NOT** use `/loop` to "auto-build" or auto-fix — the build stays **sequential + taught** (plan→approve→build).
  - For **iterative test-fix cycles** (Phase 7), prefer **`/goal`** ("run until tests pass, then stop"), not `/loop`.
  - Caveats: session-bound (dies when the session ends), and each tick costs tokens — keep intervals sane (≥2–5m).
- **`/goal <condition>` —** "**run until the condition is met, then auto-stop**" (grading check every turn).
  - **Primary use: Phase 7 (test + DoD)** — iterate until the golden-set + edge + jailbreak assertions pass,
    then stop. Also fine for any single objective sub-task with a clear pass/fail.
  - **Do NOT use** for: build phases (2–6 — learning-critical, supervised) and subjective/visual judgment
    (UI taste, booking UX → human call).
  - **Precondition (contract-first):** a **machine-checkable success condition must be written first** —
    no `/goal` without it.

## 12. Decision log (deviations & rationale)

- **Build from scratch (not reusing Beauty)** → an owned, reusable, resellable template + stronger portfolio piece.
- **Model 1 (copy-per-client) over multi-tenant** → simpler, fully isolated, fits per-client resale; avoids the
  multi-tenant isolation risk (would be T3).
- **Booking = Google Calendar (owner's phone) + Airtable (CRM)** → customer-POV value: appointment lands where
  the owner already looks.
- **Frontend on Vercel, n8n on RS** → right home per piece; don't self-host the frontend.
- **UI (landing + widget + dashboard) promoted to first-class deliverable** → it is the vitrin (portfolio + sales face).

---

## 13. Assumptions to verify (⚠ — NOT yet confirmed; do not treat as fact)

Verified at build time (Phase 0/4), **not** in the architecture phase:

- **Zernio** — is it a real WhatsApp Business Solution Provider (BSP)? Does it offer n8n integration
  (dedicated node, or generic webhook-in + send-API)? What is the inbound webhook payload + the outbound
  send API? **Not confirmed.** Directly affects Phase 4. **Fallback if it doesn't pan out:** WhatsApp Cloud
  API (Meta) / 360dialog / Twilio.
- **Google Calendar OAuth (per client)** — OAuth consent + Google "unverified app" warning, sensitive-scope
  (calendar) verification, test-mode 100-user cap; or a service-account + calendar-share alternative.
  Confirm the per-client auth path before Phase 3/4.
- **Airtable limits** — free base ≈ 1,000 records/base, API ≈ 5 req/s/base, automation/attachment caps.
  If bookings grow this becomes a ceiling → confirm the plan/tier at build.
