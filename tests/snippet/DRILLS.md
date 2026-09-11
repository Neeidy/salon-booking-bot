# Snippet drills — the run sheet

Every drill states what MUST run and what MUST NOT, and every result is read from the Airtable column,
never from the screen. The screen is evidence of RENDERING; the column is evidence of BEHAVIOUR, and this
project has been burned by confusing the two.

**Setup, both servers, two ORIGINS on purpose** (a client's site is never our origin):

    # terminal 1 — the widget + fonts
    npm run build -w @salon/snippet --prefix web
    cd web/site && npx next start -p 3001

    # terminal 2 — the hostile host page
    cd tests/snippet && python3 -m http.server 8788

Open **http://localhost:8788/host-demo.html** in a REAL browser. Headless cannot complete a Turnstile
challenge (measured repeatedly: error 600010), so every drill that sends a message needs a real one.

A fresh TAB is a fresh conversation: the session id lives in `sessionStorage`.

| # | Drill | Setup | Expected | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|---|
| **E2E-1** | **Real booking, end to end, from the hostile page** | fresh tab | `Which service…` → chips → `What day and time…` → `…shall I book it? (yes / no)` → **`You're booked: …`** | `Merge Slots` · `Slot Gate` · `Availability Gate` · `Build Event Request` · `Book Appointment` · `Verify Slot` · `Write Appointment` · `Build Booked State` · `Save State (Post-Write)` | `Mark Handoff` · `Delete Booking Event` |
| **E2E-2 · CLEANUP — NOT OPTIONAL, SAME SESSION, SAME ROUND** | **Cancel the booking E2E-1 just made, through the bot's own cancel flow** | immediately after E2E-1, same tab | `Cancel your …?` → `yes` → **`Done — your … is cancelled.`** | cancel chain through `Delete Booking Event` (204) → `Update Appointment Cancelled` | — |
| **E2E-3** | **Cleanup verified from the column, not the reply** | after E2E-2 | `appointments` row `status=cancelled`; the calendar slot is free (operator's eyes — the connector here cannot see that calendar) | — | any row left `booked` |
| ~~**IDEM**~~ | **NOT DRILLABLE FROM THIS UI — removed rather than left as a step that measures nothing.** Two reasons, both structural: the widget mints a FRESH `message_id` per send, so typing the same text twice is two DIFFERENT messages and never reaches dedupe; and a Turnstile token is SINGLE-USE, so a literal replay of the same request dies at the gate with 403 before the dedupe node is ever evaluated. Idempotency is real and is covered where it can actually be exercised (engine-level, `tests/regression-suite.md`). ⚠ **NARROWED 2026-09-11 (`qa-tester`): that sentence is true about SAME-ID dedupe and must not be read as covering the adjacent open risk.** Every idempotency scenario in the suite (#3, W-idem, O5, D1-c, S4) replays the SAME `message_id`. A re-typed `yes` after a client timeout carries a **NEW** id by definition, so it falls outside ALL of them — that question is open and unmeasured (ROADMAP §6b), not covered here. A UI step here would have produced a green tick for a mechanism it never touched. | — | — |
| **ISO-9** | Two script tags | add a second `<script src=…barber-widget.js>` to the host page | **one** widget: one `#barber-widget-root`, one launcher | double-insert guard | a second shadow host |
| **ISO-10** | JS disabled | disable JS, reload | the host page is **untouched** — no gap, no broken layout, no error | — | anything of ours rendering |
| **ISO-11** | Mobile, 390 px | narrow the window / device toolbar to 390 | panel becomes a bottom sheet; **zero horizontal overflow on the HOST page** | — | the host page scrolling sideways |
| **A11Y** | Keyboard only | Tab to the launcher, Enter, Tab through the panel, **Esc** | Esc closes; focus returns to the launcher; the composer is reachable by Tab | — | focus trapped or lost to the page behind |
| **ERR-1** | Engine unreachable | stop the network / block the webhook host, then send | a **visible** message — the transport speaking, not the shop's voice | frontend error path | a silent failure or a dead composer |
| **ERR-2** | Turnstile blocked | block `challenges.cloudflare.com`, reload | composer stays disabled with *"Verification didn't load — reload the page"* | — | a composer that accepts text it cannot send |

## Who runs what — the dividing question is whether a REAL TURNSTILE TOKEN is needed

Everything that is DOM, CSS, layout, events or asset loading is run headless by Claude. Only a live
conversation needs Yigitcan's browser, because headless cannot complete a Turnstile challenge
(measured repeatedly: error 600010). Sending him a drill that does not need a token spends one of his
turns for nothing (`.claude/rules/remote-operator.md`).

### Run headless by Claude — RESULTS (2026-09-10)

| Drill | Result |
|---|---|
| ISO-9 double script tag | **PASS** — 2 tags → 1 host, 1 launcher; font `<style>` tags still 1 (ui) / 0 (display, panel closed) |
| Stacking vs the sticky `z-index:99999` header | **PASS** — the widget is the topmost element at the launcher's centre |
| ISO-10 JS disabled | **PASS** — no widget host, no `<style>` of ours, no widget markup; the host page's own heading, canary and button all intact. ⚠ The `javaScriptEnabled:false` self-check is UNRELIABLE (Playwright's `evaluate` still runs), so the evidence is the controlled comparison: same URL, same server, widget present in every JS-enabled run and absent here |
| ISO-11 mobile 390 px | **PASS for the widget** — panel becomes a 366 px bottom sheet, 12 px each side, inside the viewport; launcher still visible. ⚠ The page shows **107 px** of horizontal overflow — measure before blaming the widget: with the widget REMOVED it is still 107 px, and restoring it keeps 107 px, so the **widget contributes 0 px**. The culprit is the test bed's own header CTA at 390 px |
| Focus lands inside the panel on open | **PASS after a fix.** It did not: `input.focus()` is a silent no-op while the composer is disabled (Turnstile pending), so focus stayed on the launcher and the next Tab left the widget. Now focuses the close button when the composer is unavailable |
| Escape closes the panel | **PASS after a fix.** It only worked while focus was INSIDE the widget — the listener was bound to the shadow root. Measured: focus on a host-page link → Escape did nothing, panel stayed open. Now a document-level listener, attached only while open |
| Escape listener removed on close | **PASS** — a second Escape does nothing and throws nothing |
| The host page still receives Escape | **PASS** — its own handler fired exactly once with `defaultPrevented === false`; we never swallow the event. ⚠ The first version of this probe measured NOTHING (the key was pressed after the listener had been removed) and returned 0; re-run correctly |
| Display font deferred to first open | **PASS** — before open only the UI face is requested; on open both; re-opening does not re-inject. Swap measured at 6 ms / 2.12 px locally (**localhost, not a real network**) |
| **ERR-1** engine unreachable | **PASS — drilled by accident during the E2E run (2026-09-10), and the result is recorded HERE as well as in ROADMAP §6b.** The timeout rendered as a `system` bubble (dashed, muted, centred) carrying `FRONTEND_TEXT.timeout` verbatim, NOT dressed in the shop's voice — the transport speaking as itself |
| **ERR-2** Turnstile blocked | **PASS — first measured 2026-09-11 by `qa-tester` (L2), not by the build.** `challenges.cloudflare.com` blocked at the browser (CDP request-block), then the panel opened: composer disabled, send disabled, placeholder exactly *"Verification didn't load — reload the page"*; typing + Send + Enter produced **zero** new bubbles and **zero** webhook POSTs. Reproduced on BOTH the current tree and a bundle built from `8eccdb8`. ⚠ Until that date this drill had **no result line anywhere** — nine PASSes were listed and two drills silently vanished from the sheet; the gap was in the RECORD, not in the behaviour |
| **HEAD-1** script in `<head>` with no `defer` | **FIXED 2026-09-11 — drilled RED then GREEN.** Before: no widget at all and an `Uncaught TypeError: Cannot read properties of null (reading 'appendChild')`, which on a client's site surfaces as a cross-origin *"Script error."* with no cause. `document.body` does not exist yet there. After: `widgetPresent:true`, one host div, one launcher, **0 exceptions**. `/install` gives the right line; where someone pastes it is the one thing a one-line product cannot control |
| **HEAD-2** TWO `<head>` tags, no `defer` (regression) | **PASS** — the double-insert guard had to MOVE for HEAD-1 (both tags now wait for `DOMContentLoaded`, so a check made before the wait would let two through). Measured on the new bundle: **1** `#barber-widget-root`, **1** launcher, 0 exceptions. On the old bundle: two exceptions, no widget |
| **STUCK-1** the verify wait has no way out | ❌ **STILL OPEN — a 20 s watchdog was built for this and REVERTED the same day; see STUCK-3.** The gap is real and measured: `window.turnstile` stubbed so `reset()` never calls back, 21 s later the composer is still `placeholder:"Verifying…"`, disabled, with no explanation. The structural reason is one producer of `ready` and no timeout on `pending` |
| **STUCK-2** the watchdog must NOT accuse the engine (negative control) | **PASSED — and passing was not enough, which is the lesson.** A healthy 25 s turn: at +5 s, +12 s and +21 s `system:0`, typing up; at +27 s the reply landed. The control was real, but it swept ONE axis (`sending`) and the defect lived on another (the panel being closed) — see STUCK-3 |
| **STUCK-3** the axis the negative control did NOT sweep: the panel never opened | 🔴 **THIS DRILL KILLED THE FIX.** Turnstile mounts on FIRST PANEL OPEN, but `setGate('pending')` runs at MOUNT, so the timer armed before anything was being verified. Measured with a `render()` counter in the host page: at T+1.5 s and **T+22 s** `turnstileRendered: 0` — not one line of verification code had run — yet the thread already carried *"Still checking this browser…"*. Opening then gave a token instantly (`placeholder:"Type a message…"`) while the false alarm stayed in the transcript, and the one-shot flag was spent, so a LATER genuine stall printed nothing. Watchdog reverted; gap recorded as open |
| **RETRY-0** `Try again` clicked with no token | **FIXED 2026-09-11.** Before: the click changed NOTHING measurable (bubbles 5→5, `.retry` 1→1, POSTs 1→1, placeholder unchanged) — a control that reads as dead. After: one line inside the bubble, *"Not ready to send yet — see the box below."* |
| **EDGE-502** an edge failure the engine never saw | **FIXED 2026-09-11.** Before: `msg bot` — *"I'm passing you to a team member — we'll get back to you shortly."* in the SHOP's voice, and **nothing in the console**. Nobody is passed to anyone: `Build Owner Alert` lives inside the workflow, which never ran. After: `msg system` + `[widget] unmapped engine response: 502`. 429 gets its own decided screen (W59) |
| **ISO-12** isolation after the mount path changed | **PASS** — before/after open, old bundle vs new: 1 host div, 1→2 marker `<style>` (display face on first open), 1 `sessionStorage` key, no cookie, no `localStorage`, `body.children` unchanged. Moving the mount behind `DOMContentLoaded` did not add a single host-document touch |

### Needs Yigitcan's browser — RESULT (2026-09-10)
**E2E-1/2/3 PASSED**, verified from the column: one `appointments` row, booked then cancelled, `gcal_event_id` + `calendar_id` set; `conversations` `turn_count=5`, `stage=cancelled`; `processed_messages` **5 distinct ids — and that is NOT a dedupe pass signal.** ⚠ Corrected 2026-09-11 (`qa-tester`): five distinct ids is the fingerprint of the 🔴 finding below — the re-sent message got a NEW id and was processed as a separate turn, i.e. **dedupe never engaged in this session at all**. Nothing about idempotency may be concluded from this run. Cleanup ran in the same session, as this sheet requires.
⚠ **The run also exposed something the screen could not show:** the first message timed out client-side (20 s) and the visitor re-sent it — but the engine had processed the abandoned one anyway. See the 🔴 item in ROADMAP §6b; the engine-side drill it calls for is NOT yet written.

### Needs Yigitcan's browser — the ONLY one
**E2E-1 → E2E-2 → E2E-3** only — a real booking and its cleanup through the bot's own cancel flow.
IDEM was removed from this sheet (see the struck row above): it cannot be exercised from this UI.

## The rule this sheet exists to enforce
E2E-1 creates real data: a Google Calendar event and an `appointments` row. **It is closed in the same
round, in the same session, by the bot's own cancel flow** — which also drills cancel, so the cleanup is
not overhead. Four rows from earlier drills were once left behind and cost hours to trace and remove,
one of them holding a live future calendar slot. That is why cleanup is a numbered drill here and not a
line in someone's memory.
