# Phase 6 backlog — design gaps to close when the vitrin frontend is built

> **Role of this file:** a durable log of design/UX gaps surfaced during the Phase 1 mockup review
> (Cowork director review, 2026-07-03/04). The Phase 1 mockups are a **skin** — approved for direction,
> not a complete product. These items are **out of scope for Phase 1** and get built/decided in
> **Phase 6 (vitrin frontend)** — except the conversation spec, which is Phase 2 core work. Nothing here
> blocks Phase 2. Linked from [ROADMAP.md](ROADMAP.md).

## 1. Empty / loading / error states — *dashboard, widget*
The mockups only show the happy, populated state. Phase 6 must design: **dashboard** zero-states
(0 appointments today, 0 new leads, 0 pending handoffs — each needs an intentional empty view, not a blank
table), and a **widget** "no slots available" reply (what the chat shows when the requested day is full).
Loading and error/failure states (request failed, offline) are undesigned across both surfaces.

## 2. Dashboard interactions (no design yet) — *dashboard*
The dashboard is a static read view; these interactions are drawn as affordances but have no flow behind them:
**Reply flow** (the "Reply" button on handoff alerts → what happens), **conversation / thread detail view**
(the "View thread" target), **date navigation** (Today → tomorrow / past days), **pagination** (tables show
a handful of rows; real data needs paging), and **search / filter** across leads and appointments.

## 3. Mobile — *all three surfaces (verified 2026-07-04 at 390px)*
Headless render at 390px passed the hard checks: **zero page overflow, zero console errors** on all three;
landing is clean single-column; widget panel is near-full-width (~366px) bottom-sheet-style with the launcher
visible; dashboard KPI cards stack and both tables scroll horizontally inside their own containers.
Two **minor cosmetic** polish items (not broken, logged not fixed): (a) the widget panel keeps a 12px side
margin on mobile — it is not a true edge-to-edge bottom sheet; decide in Phase 6 whether to go full-bleed.
(b) On the dashboard the "Owner Dashboard" top-bar pill visually overlaps the diagonal MOCK ribbon at 390px —
reposition/hide one on small screens. Real on-device testing (not just headless) is still recommended since
a barbershop audience is mobile-heavy.

## 4. Landing scope — DECISION NEEDED — *landing*
Decide whether the landing is a **full salon website** or a **focused bot showcase**. The current mockup is the
showcase. If it becomes a full site, it needs: **location / map**, a **call button** (phone), **address**,
**reviews / rating**, and a **gallery**. If it stays a showcase, explicitly cut those. This decision shapes the
Phase 6 build scope.

## 5. Conversation spec — *Phase 2 core (not Phase 6)*
The chat mockups show one scripted happy path. The bot's **full branching dialogue tree** — every intent,
slot-fill branch, fallback, and handoff trigger — is the actual Phase 2 core work. The mockup is the skin;
this spec is the brain and must be written before/with the n8n flow.

## 6. Minor
- **Contrast:** re-check oxide `#B4472E` on cream `#F1EEE6` for small label text against WCAG AA (4.5:1) —
  it is used for eyebrow labels and accents; verify each small-text use passes, drop to ink where it does not.
- **Config wiring:** the "config-driven" footer claim is currently config-*consistent* (values mirror
  `client.config.example.json`) but not config-*wired*. Phase 6 must actually read brand name / colors /
  services / hours from config at build/runtime, so one config swap re-brands every surface for real.

## 7. Dashboard authentication — SECURITY-CRITICAL — *dashboard*
The dashboard exposes PII (names, phones, threads) and a destructive one-click Cancel →
**owner-only, authenticated access; never public without auth**. Locked in
[ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md) Final Feature Log (2026-07-04);
Critical-Review Target #9 (Codex gate).

## 8. Dark/light theme — *all three surfaces*
Dark/light theme support across landing + widget + dashboard (locked 2026-07-04).
Interacts with §6 config wiring: theme becomes a `client.config` field.
