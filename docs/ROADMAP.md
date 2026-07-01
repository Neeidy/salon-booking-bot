# Roadmap — salon-booking-bot (live phase tracking)

> **Role of this file:** the SINGLE live source of phase status. Roadmap content lives ONLY here —
> [../MASTER-BRIEF.md](../MASTER-BRIEF.md) (§10) is the frozen snapshot;
> [ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md) links here rather than duplicating.
> Update the checkboxes as phases complete. Order discipline: **works first (2–5), then shines (6).**

| ✓ | Phase | Work | Done criteria |
|---|---|---|---|
| ✅ | **0. Scaffold** | repo skeleton · `.claude/` governance · schemas · config example · docs | Skeleton + schemas in place — **done + pushed (`a74625d`)** |
| ☐ | **1. Visual blueprint** | landing + widget + dashboard **mockup** + flow diagram *(CC builds → commits; Cowork reviews from git)* | Visual demo approved, gaps logged |
| ☐ | **2. Core bot** | n8n: webhook → load state → LLM intent → routing → slot-filling → reply (test via widget first) | Happy path + 2–3 intents, JSON valid, multi-turn slot-fill completes |
| ☐ | **3. Booking + data** | availability → write → re-verify → Google Calendar + Airtable · idempotency · timezone-UTC | Booking works; duplicate ≠ double-book; concurrent same-slot → one + handoff |
| ☐ | **4. WhatsApp** | Zernio channel `⚠ verify §13` | Real WhatsApp message → booking + reply |
| ☐ | **5. Safety** | handoff · cost cap · kill-switch · dry-run · max-iteration · injection · error branch | Low conf → handoff; kill-switch works; errors visible; jailbreak caught |
| ☐ | **6. Vitrin frontend** | build Next.js landing + widget + dashboard → live data → Vercel | Deployed, branded, reads live data |
| ☐ | **7. Test + Codex + DoD** | golden set · edge · jailbreak · critical-targets audit · sanitize · README/case-study | Full DoD checklist passes |
| ☐ | **8. Template-ize** | config-only swap → a second mock client | Config swap → working 2nd instance |

**Legend:** ▶ in progress · ☐ not started · ✅ done.

## Critical-Review Targets (Codex gate — from MASTER-BRIEF §9)
1a idempotency · 1b concurrency/no-double-book · 2 Google Calendar write · 3 webhook verification ·
4 secret+PII handling · 5 handoff threshold · 6 error visibility · 7 n8n control-plane exposure.
