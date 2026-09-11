# Snippet drills — the run sheet

Every drill states what MUST run and what MUST NOT. **Where a drill has an engine-side consequence, the
result is read from the Airtable column or the execution, never from the screen** — the screen is evidence
of RENDERING, the column is evidence of BEHAVIOUR, and this project has been burned by confusing the two.

⚠ **Two corrections to this header, both from Codex CRT #13.** (1) It used to say *every* result is read
from Airtable. That is false and could not be otherwise: the isolation, layout, listener, RTL and
fallback drills have no engine side at all — they ARE screen and DOM measurements, and reading them from a
column would be impossible. The rule is about the drills that touch the engine. (2) **These drills are not
a regression harness and must not be cited as one.** Every row below is a ONE-OFF MANUAL MEASUREMENT taken
on a named bundle; nothing here re-runs on a change, and a future edit can break any of them with every
gate still green. An executable browser harness is a named open item (6c / Phase 7), and until it exists
"this is drilled" means "it was true once, on that build" — which is exactly why each row now carries the
artefact it was measured on.

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
| **ERR-2** | Turnstile blocked | block `challenges.cloudflare.com`, reload | composer stays disabled with *"Couldn't verify this browser — reload to try again"* | — | a composer that accepts text it cannot send |

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
| **ERR-2** Turnstile blocked | **PASS — first measured 2026-09-11 by `qa-tester` (L2), not by the build.** `challenges.cloudflare.com` blocked at the browser (CDP request-block), then the panel opened: composer disabled, send disabled, placeholder exactly *"Verification didn't load — reload the page"* — ⚠ **that was the shipped wording on the day this was measured; the text changed on 2026-09-11** to *"Couldn't verify this browser — reload to try again"* because the old one was false for a challenge that LOADED and then refused (measured with Cloudflare's always-block test key). The drill's behaviour is unchanged; its quoted string was stale (Codex CRT #13, finding 10); typing + Send + Enter produced **zero** new bubbles and **zero** webhook POSTs. Reproduced on BOTH the current tree and a bundle built from `8eccdb8`. ⚠ Until that date this drill had **no result line anywhere** — nine PASSes were listed and two drills silently vanished from the sheet; the gap was in the RECORD, not in the behaviour |
| **HEAD-1** script in `<head>` with no `defer` | **FIXED 2026-09-11 — drilled RED then GREEN.** Before: no widget at all and an `Uncaught TypeError: Cannot read properties of null (reading 'appendChild')`, which on a client's site surfaces as a cross-origin *"Script error."* with no cause. `document.body` does not exist yet there. After: `widgetPresent:true`, one host div, one launcher, **0 exceptions**. `/install` gives the right line; where someone pastes it is the one thing a one-line product cannot control |
| **HEAD-2** TWO `<head>` tags, no `defer` (regression) | **PASS** — the double-insert guard had to MOVE for HEAD-1 (both tags now wait for `DOMContentLoaded`, so a check made before the wait would let two through). Measured on the new bundle: **1** `#barber-widget-root`, **1** launcher, 0 exceptions. On the old bundle: two exceptions, no widget |
| **STUCK-1** the verify wait has no way out | **CLOSED 2026-09-11 (second attempt).** A 20 s watchdog, armed only once Turnstile has actually been asked for a token. Positive control first, because a watchdog that cannot fire makes every silence below meaningless: panel open, token never arrives → at +21 s one `system` bubble and `placeholder:"Still verifying — reload the page"` |
| **STUCK-2** axis (a) `sending` — the engine's wait must not be blamed on Turnstile | **PASS** — healthy 25 s turn: at +21 s zero stuck bubbles, typing up; after the reply, `"Type a message…"`. ⚠ This control also PASSED for v1, and v1 was broken. Passing one axis is not passing |
| **STUCK-3** axis (b) the panel is NEVER opened — **the axis that killed v1** | **PASS** — at +22 s `turnstileRendered: 0`, **zero** stuck bubbles, placeholder still `"Verifying…"`. v1 measured `stuckBubbles: 1` here with nothing verified: it was timing the visitor's browsing speed, not Cloudflare |
| **STUCK-4** axis (c) opened then CLOSED — split in two, because "panel closed" is not one case | **PASS both ways.** c1 opened, closed, token never arrives → **1** bubble (honest: verification WAS requested and stalled). c2 opened, closed, token arrived → **0** bubbles. The difference from (b) is whether anything was ever asked, and the code must tell them apart |
| **STUCK-5** axis (d) the one-shot must RE-ARM | **PASS — and this was a latent v1 defect nobody had named as its own axis.** Stall #1 announced → token delivered late, gate returns to `"Type a message…"` → a second genuine stall → announced **again** (`stuckBubbles: 2`). v1 spent its only shot on the false alarm and had nothing left for the real one |
| **STUCK-6** axis (e) `blocked` — do not stack a contradicting message | **PASS** — Turnstile's `error-callback` fires → placeholder `"Couldn't verify this browser — reload to try again"`, **zero** stuck bubbles. The box already says something true; a second, different sentence on top would be worse than silence |
| **RETRY-0** `Try again` clicked with no token | **FIXED 2026-09-11.** Before: the click changed NOTHING measurable (bubbles 5→5, `.retry` 1→1, POSTs 1→1, placeholder unchanged) — a control that reads as dead. After: one line inside the bubble, *"Not ready to send yet — see the box below."* |
| **EDGE-502** an edge failure the engine never saw | **FIXED 2026-09-11.** Before: `msg bot` — *"I'm passing you to a team member — we'll get back to you shortly."* in the SHOP's voice, and **nothing in the console**. Nobody is passed to anyone: `Build Owner Alert` lives inside the workflow, which never ran. After: `msg system` + `[widget] unmapped engine response: 502`. 429 gets its own decided screen (W59) |
| **ISO-12** isolation after the mount path changed | **PASS** — before/after open, old bundle vs new: 1 host div, 1→2 marker `<style>` (display face on first open), 1 `sessionStorage` key, no cookie, no `localStorage`, `body.children` unchanged. Moving the mount behind `DOMContentLoaded` did not add a single host-document touch |

| **FALLBACK-1** the script loads | **PASS 2026-09-11.** Host page carries `#barber-widget-fallback`; after mount `hidden` is set and the element's height is 0, widget present |
| **FALLBACK-2** the script 404s (ad blocker / CSP / network) | **PASS — the direction that matters.** Same page, `src` pointed at a missing file: no widget, and the fallback is **still visible** (`hidden:false`, height > 0). This is the commonest silent death in the class and the visitor now keeps a way to reach the shop |
| **RTL-1** host page is `dir="rtl"` | **PASS** — `body` computes `direction:rtl` while the widget host computes `direction:ltr` / `unicode-bidi:isolate`; the panel is still anchored 26 px from the right edge |
| **RTL-2** an RTL message inside a bubble | **PASS** — an Arabic reply rendered with `.msg` at `unicode-bidi:isolate`, `direction:ltr`; the stamp stays inside its own bubble instead of being dragged to the wrong end by the RTL run |
| **BUILD-1** a deployment that runs only the site build | **FIXED 2026-09-11, drilled both ways.** With the OLD `prebuild` the bundle was **absent** after a full site build — the one-line embed would 404, and `public/barber-widget.js` is gitignored so the repo does not carry it either. With the new `prebuild` (which calls the snippet build) the bundle is produced. The negative control is the old script restored and re-run |
| **BUILD-2** `--check` with no bundle | **FIXED 2026-09-11.** Previously exit 0 — the gate validated the INPUTS and reported OK while the product did not exist. Now: bundle removed → **exit 1**; bundle restored → exit 0; bundle truncated to 100 B → **exit 1** |
| **FONT-1** an unrecorded `.woff2` in the shipped directory | **FIXED 2026-09-11.** The guard walked the RECORD, so it could only find fonts it already knew. Measured: a rogue `.woff2` dropped into `web/site/public/fonts` → **exit 1, named in the output**; removed → exit 0. ⚠ **The first version of this guard claimed more than it measured** and four silent passes were produced against it the same hour — a `.woff2` in a SUBDIRECTORY, a `.ttf` beside the recorded files, an UPPERCASE `.WOFF2`, and a `.woff2` in `public/` but outside `fonts/`. All four ship. The search now covers the whole `public/` tree, case-insensitively, for `.woff2/.woff/.ttf/.otf`, and all four go RED (re-measured). ⚠ Still NOT covered: a coordinated change to both a font and its recorded checksum — comparing against the upstream blob is a named open item |


### Drilling `scripts/secret-scan.sh` — the false green that catches everyone

**The guard is a PreToolUse hook, not a scanner you can pipe to.** It reads hook JSON from stdin and exits 0
at `[[ "$tool" == "Bash" && "$cmd" == *"git push"* ]] || exit 0`. So ANY invocation that is not a `git push`
Bash call runs **none** of its rules and returns 0 — including piping a diff into it, which looks exactly
like a passing scan.

Measured twice, by two different auditors on 2026-09-11, and BOTH were briefly fooled by it: one ran it with
no payload and got a green that measured nothing; the other planted a full-shaped fake key and STILL got
green, for the same reason. It only goes red when driven properly:

    echo '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' | ~/.claude/hooks/secret-scan.sh
    # clean tree → exit 0 · planted sk-ant-shaped key in an isolated repo → exit 2

⚠ Its scope is `origin/main..HEAD`, i.e. COMMITTED work. An uncommitted change gets zero coverage from it,
and the rule set contains **no PII or phone-number rule at all** — PII is caught by manual scanning every
round, never by this guard. Treat a bare `exit 0` from it as no evidence unless the payload was real.


**Axes SWEPT for the watchdog (2026-09-11):** (a) `sending` · (b) panel never opened · (c) opened-then-closed,
both directions · (d) one-shot re-arm · (e) `blocked`. Plus the positive control, run FIRST.

**Axes NOT swept — named, because an unnamed gap is the one that bites:**
1. **A real Cloudflare widget with a real site key.** The accept direction needs a real token → Yigitcan's
   browser. Every drill above uses a deterministic `window.turnstile` stub, which is what makes the token
   lifecycle controllable at all — and also what makes it not the real thing.
2. **A genuinely slow network where Turnstile legitimately needs more than 20 s on first load.** The message
   there would be premature but not untrue ("still verifying"). The threshold is a judgement call, measured
   against a test key on one machine; it is not validated against a real slow connection.
3. **A backgrounded tab.** Browsers throttle timers in background tabs, so the 20 s can stretch. Not measured.
4. **The exact boundary** — a token arriving within milliseconds of the deadline. `setGate('ready')` clears the
   timer on its first line, so the race is reasoned to be safe; it was not drilled.
5. **Two widgets on one page.** Prevented upstream by the `HOST_ID` guard (drilled separately, HEAD-2); the
   watchdog was not re-swept against it.

### Needs Yigitcan's browser — RESULT (2026-09-11, re-run on the CURRENT bundle)

**E2E-1/2/3 PASS — and the tick is bound to an artefact, not to a date.** The bundle exercised is
byte-for-byte the build of **`7d2c118`** (HEAD at the time; `7d2c118` changed no code, so the widget code
is **`97564b9`**). Proven rather than assumed: the served file was copied aside, the snippet rebuilt from
HEAD, and `cmp` returned identical. The previous E2E result was dated 2026-09-10 and four commits had
landed since — it is superseded here, not stacked beside.

Read from the column and the execution, never from the screen:

| What | Where it was read | Value |
|---|---|---|
| exactly ONE appointment | `appointments` | 1 row, `booked` → **`cancelled`**, `gcal_event_id` + `calendar_id` set, `start_utc 2026-09-12T09:00Z` = 11:00 Vienna |
| exactly ONE calendar event | `Verify Slot` output, exec **2688** | `items` length **1**; `Check Race` → `race_lost:false`, `race_other_count:0` |
| the event really went | `Delete Booking Event` **status code**, exec **2690** | **HTTP 204 No Content** — read from `statusCode`, not from the reply text |
| the mirror write | `Update Appointment Cancelled`, exec 2690 | row `rec…` → `status:"cancelled"`; `cancel_mirror_failed:false` |
| the words on screen | `conversations.computed_reply` | **BYTE-IDENTICAL** to the last bubble — 60 bytes, em dash confirmed as U+2014 |
| conversation state | `conversations` | `turn_count:5`, `stage:"cancelled"`, `cancel_target_id` = the appointment row |
| messages | `processed_messages` | **5 rows, 5 distinct ids.** ⚠ Distinct ids are NOT a dedupe pass signal — nothing was re-sent in this run, so dedupe was never exercised (the 2026-09-10 correction stands) |

**FREE F1 CONFIRMATION — the deterministic resolver is live on this bundle.** Exec **2687**,
`date_resolution`: `expr:"tomorrow"` · `code:"2026-09-12"` · `outcome:**"resolved_by_code"**` ·
`date_dropped:false` · `date_alert:false`. The engine, not the model, produced the booking date.
⚠ **What this run does NOT prove:** the LLM returned the same date (`llm:"2026-09-12"`), so the OVERRIDE
path — code winning over a disagreeing model — was not exercised here. That direction has unit, mutation
and earlier live evidence; this drill adds the resolver's presence, not its override.

**Bonus, measured rather than read off the source:** the event id decodes to
`widget:w-…|2026-09-12|11:00|haircut` — the deterministic booking key the retry comment in
`web/snippet/src/index.ts` names as the bound on an in-flight duplicate. The claim is now measured.

### Needs Yigitcan's browser — the ONLY one
**E2E-1 → E2E-2 → E2E-3** only — a real booking and its cleanup through the bot's own cancel flow.
IDEM was removed from this sheet (see the struck row above): it cannot be exercised from this UI.

## The rule this sheet exists to enforce
E2E-1 creates real data: a Google Calendar event and an `appointments` row. **It is closed in the same
round, in the same session, by the bot's own cancel flow** — which also drills cancel, so the cleanup is
not overhead. Four rows from earlier drills were once left behind and cost hours to trace and remove,
one of them holding a live future calendar slot. That is why cleanup is a numbered drill here and not a
line in someone's memory.
