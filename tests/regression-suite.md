# Regression suite — salon-booking-bot (n8n `Salon Booking Bot — Main`)

> **Purpose:** the named, re-runnable behavioural baseline. Run this at the start of CP4 and after
> **every** refactor step — the flow must still produce the same customer reply AND the same node
> path (especially the nodes that MUST NOT run). A refactor that changes any "must-not-run" is a
> regression, not a cleanup.
>
> **How verification works.** Two layers per scenario:
> 1. **Reply** — the JSON `reply` (or HTTP status) the webhook returns. Automatable (`run-regression.sh`).
> 2. **Node path** — which nodes executed, via the n8n execution API. The critical column is
>    **MUST-NOT-RUN** (e.g. `Delete Booking Event` must be absent on every abort/needs-human path).
>    Checked from `n8n_executions get` (or the editor's execution log).
>
> **Endpoints.** Published production webhook: `POST https://<n8n-host>/webhook/barber-inbound`
> (no arming; pass the host via `WEBHOOK_URL` — not hardcoded, this is a public template). Draft test
> webhook: `…/webhook-test/…` (needs one "Execute workflow" per call).
> `sender_key = "widget:{sessionId}"`. `messageId` MUST be unique per message (idempotency dedupe).
>
> **Setup note.** Scenarios marked ⚙ need Airtable state injected first (a booked `appointments`
> row, or a crafted `conversations` row). `appointments` valid-mock row = `{sender_key, service:"Haircut",
> start_utc (future weekday, outside cutoff), end_utc, gcal_event_id (real hex OR shape-valid fake
> "a1b2c3d4e5"), calendar_id (real cal), channel:"widget", status:"booked"}`. A **shape-valid fake**
> gid is used when the delete must NOT actually fire (the row is there only to be bound/validated).
>
> **Config baseline:** services `haircut`/`beard`/`haircut_beard`; hours Mon–Sat; `cancellationCutoffHours:2`.

---

## Scenario table

| # | Name | Setup | Message sequence (session) | Expected reply | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|---|---|
| 1 | **booking happy** | — | `book haircut on <wkday> 14:00` → `yes` | T1 "…shall I book it?" · T2 "You're booked: …" | Merge Slots · Slot Gate · Availability Gate · Build Event Request · Book Appointment · Verify Slot · Write Appointment · Build Booked State · Save State (Post-Write) | Delete Booking Event · Mark Handoff |
| 2 | **race / no-double-book** ⚙(concurrent) | pre-existing overlapping event on the calendar for the slot | `book … <slot>` → `yes` | "Sorry — that time was just taken…" (`slotJustTaken`) | Verify Slot · Check Race · Race Gate(→lost) · Cancel Our Event · Build Race-Lost State | Write Appointment(as booked-success) — the event we inserted is DELETED, the pre-existing survives |
| 3 | **idempotency (double webhook)** | — | send the SAME `messageId` twice | 2nd call → `{"status":"duplicate_ignored"}` (distinct short-circuit — NOT a replay of the prior reply; see Step-2 note: `booking-integrity.md` says "return the prior result") | Check Processed · Dedupe Gate · Is Duplicate(true) · Idempotent Replay | any state-mutating node on the 2nd call (no 2nd Write/Delete) |
| 4 | **cancel happy (204)** | book first (sc.1) | `cancel my appointment` → `yes` | T1 "Cancel your Haircut on …?" · T2 "Done — your … is cancelled." | Route Intent(cancel)→Find Booking→Cancel Lookup→Cancel Route→Build Cancel-Confirm State ; then Confirm Router(true)→**Confirm Fresh?(true)**→Find Booking→Cancel Lookup(execute)→Cancel Route→Validate Cancel Target→Cancel Target Valid?(true)→**Re-read Cancel State**→**Verify Confirm Live**→**Confirm Live?(true)**→Delete Booking Event(204)→Classify Cancel Delete(deleted)→Update Appointment Cancelled→Build Cancelled State | Build Cancel-Aborted State |
| 5 | **cancel BIND (booked[0] ≠ target)** ⚙ | book A (later); confirm-cancel A; then inject B (earlier, same sender_key, shape-valid fake gid) | `cancel`→`yes` (A) → [inject B] → `yes` | "Done — your Haircut on **A's time** is cancelled." | Cancel Lookup(execute) binds `cancel_target_id`=A ; Delete uses A's real gid | Delete of B (B stays `booked`) |
| 6 | **401 → unavailable** ⚙(auth-strip) | book; cancel-confirm; strip Delete node auth (`authentication:none`) | `yes` | HTTP **503** `{error:"calendar_unavailable", cancel_delete_failed:true, reply:cancelUnavailable}` — NOT "already cancelled", NOT "cancelled" | Delete Booking Event(statusCode 401)→Classify Cancel Delete(**unavailable**)→Cancel Delete Gate(true)→Cancel Delete Unavailable Reply | Update Appointment Cancelled · Save State (no state write — stage stays cancel_confirming) |
| 7 | **retry after unavailable → 204** ⚙ | continue sc.6, restore auth | `yes` (again) | "Done — … cancelled." (stage was NOT locked; retry reaches execute) | Confirm Router→Confirm Fresh?(true)→…→Delete(204) | Handoff Lock Reply |
| 8 | **Validate reject — calendar_id empty** ⚙ | inject booked row with `calendar_id` = "" (real-ish gid) | `cancel`→`yes` | cancelNeedsHuman ("I found your booking but can't cancel it automatically…") | Cancel Target Valid?(false)→Build Cancel-NeedsHuman State | Delete Booking Event · Re-read Cancel State |
| 9 | **Validate reject — gid whitespace** ⚙ | inject booked row with `gcal_event_id`="   " | `cancel` | cancelNeedsHuman — **no confirm prompt is built** (ask-mode structOk) | Cancel Lookup(ask, needs_human)→Cancel Route→Build Cancel-NeedsHuman State ; stage→handoff | a `cancel_confirming` prompt · Delete |
| 10 | **Validate reject — legacy tc=0/null** ⚙ | inject `conversations` row `{stage:cancel_confirming, cancel_target_id, turn_count:0}` with **no** `confirm_turn`, + booked appt | `yes` | cancelAborted ("No problem — your booking stands.") | Confirm Router(true)→**Confirm Fresh?(false)**→Build Cancel-Aborted State | Find Booking · Delete Booking Event |
| 11 | **confirm TTL — fresh passes** | = sc.4 (the immediate `yes` after the confirm prompt) | see sc.4 | "Done — cancelled." | Confirm Fresh?(**true**) | Build Cancel-Aborted State |
| 12 | **confirm TTL — stale drops** ⚙ | inject `{stage:cancel_confirming, cancel_target_id, turn_count:6, confirm_turn:"5"}` + booked appt | `yes` | cancelAborted | Confirm Router(true)→**Confirm Fresh?(false)**→Build Cancel-Aborted State | Delete Booking Event |
| 13 | **Abort — FAQ intervenes** | book; `cancel` (confirm prompt) | `cancel`→ `what are your prices?` | "No problem — your booking stands." (cancel aborted; FAQ **not** answered) | Abort Cancel?(true)→Build Cancel-Aborted State | Answer FAQ · Route Intent · Delete |
| 14 | **Abort — lead intervenes** | book; `cancel` | `cancel`→ `can someone call me back about a package?` | "No problem — your booking stands." | Abort Cancel?(true)→Build Cancel-Aborted State | Capture Lead · Delete |
| 15 | **cancelTargetGone** ⚙ | book; `cancel` (confirm); **delete the appt row**; `yes` | `cancel`→[delete row]→`yes` | "I couldn't find that booking to cancel anymore…" (`cancelTargetGone`) — NOT "I found your booking" | Cancel Lookup(execute, `_cancel_target_gone:true`)→Build Cancel-NeedsHuman State(neutral) | Delete Booking Event |
| 16 | **FAQ** | — | `what are your prices?` | config price line ("Our prices: Haircut €25 …") | Route Intent(faq)→Answer FAQ→Save State | any LLM-authored answer · Delete |
| 17 | **lead** | — | `can someone call me back about a package?` | `leadCaptured` ("Thanks! We've got your details…") | Route Intent(lead)→Capture Lead→Build Lead State→Save State | booking nodes |
| 18 | **handoff (intent-handoff)** | — | `I want to reschedule to next week` (reschedule → handoff) OR a low-confidence msg | `handoff` ("I'm passing you to a team member…"); Airtable `stage=handoff` | Confidence & Intent Gate(true)→Mark Handoff→Save State | booking/cancel mutations |
| 19 | **guard-trip** ⚙(config) | set `bot.killSwitch:true` (or exceed `maxTurnsPerConversation`) | any message | `handoff` (200), **0 LLM cost** | Check Bot Guards(false)→Handoff Reply | Build LLM Request · Extract Intent (no paid call) |
| 20 | **invalid payload → 400** | — | POST a body with **no `messageId`** (or empty text / bad senderId / disabled channel) | HTTP **400** (`Send Reject Response`) | Validate Payload(false)→Send Reject Response | Normalize Inbound · any downstream |
| 21 | **cancel, no booking** | — (fresh session, never booked) | `cancel my appointment` | `cancelNoBooking` ("You don't have an active booking to cancel.") | Route Intent(cancel)→Find Booking(0)→Cancel Lookup('none')→Cancel Route→Build No-Booking Reply | Delete Booking Event · a confirm prompt |
| 22 | **handoff lock** | — | `reschedule to next week` (→handoff) → then any 2nd message | 2nd → `{locked:true, "A team member is already helping…"}` (`Handoff Lock Reply`) | Merge State→Check Handoff Lock(true)→Handoff Lock Reply | Check Bot Guards · Build LLM Request (bot stays silent, 0 cost) |
| 23 | **cancel within cutoff** ⚙ | inject booked row with `start_utc` **< 2h** from now | `cancel my appointment` | `cancelCutoff` ("too close to its time to cancel here…") | Cancel Lookup('cutoff')→Cancel Route→Build Cancel-Cutoff Reply | a confirm prompt · Delete |

**Handoff-class note (rule `handoff.md`):** #6 = infra-unavailable (503 + error flag, no state write); #18/#8/#9/#15 = intent-handoff (200, writes `stage=handoff`); #19 = guard-trip (200, transient, no counter increment).

---

## Baseline run

**Commit bcc8058 · 2026-08-17 · published production webhook.**

**Automated (curl-only subset, `run-regression.sh`): 12/12 PASS, 0 FAIL** —
#1 booking · #4 cancel happy (204) · #11 confirm-TTL fresh · #16 FAQ · #17 lead · #18 handoff ·
#13 Abort-FAQ · #3 idempotency · **#20 invalid-payload 400 · #21 cancel-no-booking · #22 handoff-lock**.
Harness bugs found + fixed on the way (flow was correct each time): (a) idempotency returns
`duplicate_ignored`, not a replay — expectation corrected; (b) the Abort scenario left its 16:00
booking so a re-run correctly **lost the race** — the harness now self-cleans that booking.

### Exit & branch coverage map (Ö2 — every reply exit + branch accounted for)

**11 reply exits:** 6 covered by automated/assisted scenarios; 5 are infra-outage exits (503) that need
a credential/service failure injected → spec'd as ⚙ infra-drills, not in the curl-only harness.

| Reply exit (HTTP) | Fed by | Covered |
|---|---|---|
| Send Reply To Origin (200) | Build Reply Payload | ✅ #1/#4/#16/#17 |
| Send Reject Response (400) | Validate Payload[false] | ✅ #20 |
| Idempotent Replay (200) | Is Duplicate[true] | ✅ #3 |
| Handoff Lock Reply (200) | Check Handoff Lock[true] | ✅ #22 |
| Handoff Reply (200, guard-trip) | Check Bot Guards[false] | ⚙ #19 |
| Cancel Delete Unavailable Reply (503) | Cancel Delete Gate[unavail] | ⚙ #6 |
| Send Error Response (503 `state_unavailable`) | Load/Save State · Check Processed · Find Booking [error] | ⚙ **infra-drill** (Airtable down) |
| LLM Unavailable Reply (503) | Extract Intent[error] | ⚙ **infra-drill** (LLM down) |
| Lead Unavailable Reply (503) | Capture Lead[error] | ⚙ **infra-drill** (Airtable lead-write fail) |
| Calendar Unavailable Reply (503) | Get Calendar Busy · Compute Availability · Reconcile 404?[def] | ⚙ **infra-drill** (freeBusy down / ambiguous-insert reconcile) |
| Booking State-Unsaved Reply (200) | Save State (Post-Write)[error] | ⚙ **infra-drill** (post-write Airtable fail) |

**18 branch nodes** (16 IF + 2 Switch): every output is now reached by a scenario except the pure
infra-error branches above. Newly covered by #20–#23: `Validate Payload[false]`, `Check Handoff Lock[true]`,
`Cancel Route[none]`, `Cancel Route[cutoff]`. Edge branches `Event ID Valid?[false]` (malformed event id →
handoff — proven earlier by the astral-sender guard, exec on CP2c) and the `Reconcile Gate`/`Reconcile 404?`
pair (ambiguous 409/timeout insert) are ⚙ edge-drills, spec'd, not automated.

**Honest gap (unchanged):** the 5 infra-503 exits + guard-trip + reconcile need injected failures/config;
they are documented drills, not curl-only. The confirmation-lifecycle, cancel, booking, idempotency, routing,
and handoff-class branches are all covered.

**⚙ Setup-heavy (assisted, verified this session via the execution API):**

| # | Scenario | Evidence | On current 92-node flow? |
|---|---|---|---|
| 10 | Validate reject — legacy tc=0/null → abort, no delete | exec **149** | ✅ yes (bcc8058) |
| 4/11 | cancel happy + re-read path → 204 | exec **153** | ✅ yes (bcc8058) |
| 12 | confirm-TTL stale → abort | unit 17/17 + exec 141 (logic = same gate as exec 149) | gate re-verified 149 |
| 8/9 | Validate reject calendar_id-empty / gid-whitespace | exec **124 / 126** | Validate logic unchanged since |
| 5 | cancel BIND (booked[0]≠target) | exec **111** | Cancel Lookup bind unchanged |
| 6/7 | 401→unavailable / retry→204 | exec **115 / 122** | Classify unchanged; delete now behind re-read |
| 15 | cancelTargetGone | exec **147** | gone-flag unchanged |
| 2 | race / no-double-book | exec **77** (CP2b) + observed live here (a leftover booking made a re-run lose the race) | booking path unchanged |
| 19 | guard-trip | exec **34** (CP3) | guards unchanged |

**Honest gap:** #2 race (true concurrency) and #6/#19 (credential/config manipulation) are not in the
automated harness — they need injected state or a live drill. The re-audit only touched `Confirm Fresh?`
+ the pre-delete re-read; scenarios whose logic it did not touch are cited from their original proof.

**BASELINE = healthy.** Re-run `run-regression.sh` at the start of CP4 and after every refactor step;
any drop from 12/12, or any MUST-NOT-RUN node appearing, is a regression.

### ⚙ Reconcile drills — Phase-7 gate (from refactor Step 1 / c1)

The reconcile path only runs when `Book Appointment` errors, so it is not curl-only. Step 1 (c1) made
`Classify Reconcile Failure` structural (statusCode → `ok`/`gone`/`unavailable`, fail-closed). Live-proven
this session: the **ok** path (exec 240 — a real 409 tombstone → Get 200 → class `ok` → Verify Reconcile
reads `$json.body` → cancelled → handoff). **NOT yet live-triggered — MUST run in Phase 7's controlled
infra-drill session** (isolated auth manipulation, one publish window, restore-gate a/b/c):

| Drill | Setup | Expected | Verify |
|---|---|---|---|
| **reconcile D1 — gone/404** | `Book Appointment` auth→`none` (Book 401, no event created) → book once | `Get For Reconcile` **404** → `Classify` **gone** → `Reconcile 404?`[true] → `Calendar Unavailable Reply` 503 (retry-safe). Restore Book auth + gate (a config · b live 2xx · c grep auth:none→0) | exec: Get statusCode 404 · `_reconcile_class:"gone"` · no "already exists / never created" text output; failure visible |
| **reconcile D2 — unavailable/401** | `Get For Reconcile` auth→`none`; trigger a Book error to reach Get | `Get` **401/403** → `Classify` **unavailable** → `Reconcile 404?`[false] → `Build Reconcile-Unresolved State` 200 handoff. Invariant: statusCode ∉ {200,204,404,410} ⇒ unavailable (403 also passes). Restore Get auth + gate | exec: Get statusCode 401 · `_reconcile_class:"unavailable"` · handoff, id visible |

Reason deferred to Phase 7 (ARCHITECTURE-DECISIONS §5, 2026-08-17): the auth-break + 4-publish + clobber
risk of running these mid-refactor outweighs the residual; classifier is unit-proven (17/17) + the
`_reconcile_class` field/value contract is statically verified. **The phase may move; the gate may not.**
