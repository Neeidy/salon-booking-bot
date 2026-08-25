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

### Reschedule (CP4 sub-step 3 — insert-new + verify/race + commit; book-new-first). "R:" prefixes the reschedule execute nodes.

| # | Name | Setup (+ restore) | Message sequence (session) | Expected reply | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|---|---|
| 24 | **reschedule, no booking** | — (fresh session) | `reschedule my appointment` | `rescheduleNoBooking` ("You don't have a booking to reschedule.") | Route Intent(reschedule)→Find Booking (Reschedule)(0)→Reschedule Lookup('none')→…→handoff | any R: execute node · Delete Old Event (Reschedule) |
| 25 | **reschedule happy (end-to-end move)** | book slot A first | `Move … to <B>` → `yes` | T3 "Move your Haircut from A to B?" · T4 **"Moved — your Haircut is now B."** (`rescheduleDone`, stage=booked) | Reschedule Fresh?(true)→Find Old Booking (R)→Validate Reschedule Target(valid)→Build Reschedule Event Request→Book Reschedule Appointment→Verify Slot (R)→Check Race (R)(won)→Update Appointment (R)→Delete Old Event (R)(204)→Classify Reschedule Delete(done)→Build Reschedule-Done State | Build Reschedule Insert-Failed/NeedsHuman/Race-Lost/Orphan/Mirror-Failed State · Build Reschedule-Aborted State |
| 26 | **reschedule available → confirm-ask** | book slot A | `Move … to <free B>` | "Move your Haircut from A to B? Reply \"yes\"…" — `stage=reschedule_confirming`, `confirm_turn` set | Compute Reschedule Availability('available')→confirm-ask | any R: execute node (no move on the ASK turn) |
| 27 | **reschedule abort (FAQ intervenes)** | book slot A; ask reschedule to B (confirm prompt) | `Move … to B` → `what are your prices?` | `rescheduleAborted` ("No problem — your booking stays as it is.") — FAQ **not** answered | Abort Reschedule?(true)→Build Reschedule-Aborted State (clears confirm state) | Answer FAQ · any R: execute node |
| 28 | **reschedule past-guard** ⚙(handoff→locked, curl cannot self-clean) | book slot A | `Move … to <past date>` | "<when> has already passed — a team member will help you pick a new time." (handoff) | Compute Reschedule Availability('past')→handoff | any R: execute node |
| 29 | **reschedule target-invalid → NeedsHuman** ⚙(inject; restore: none — row deleted at cleanup) | book A; ask reschedule to B (confirm); **blank the appt row `calendar_id`** (or delete the row) | `yes` | `rescheduleNeedsHuman` ("I found your booking but can't reschedule it automatically…") | Validate Reschedule Target(`_reschedule_valid:false`)→Reschedule Target Valid?(false)→Build Reschedule-NeedsHuman State | Book Reschedule Appointment (**NO insert**) · Delete Old Event (R) |
| 30 | **reschedule insert-fail → original stands** ⚙(auth-strip; restore Book Reschedule auth → live 2xx) | book A; ask reschedule to B; strip `Book Reschedule Appointment` auth (`authentication:none`) | `yes` | `rescheduleInsertFailed` ("Sorry — I couldn't move your booking; your original appointment still stands…") | Book Reschedule Appointment(401 error out1)→Build Reschedule Insert-Failed State→Save State (Post-Write) | Verify Slot (R) · Update Appointment (R) · Delete Old Event (R) — OLD row + event untouched |
| 31 | **reschedule race-lost** ⚙(2nd sender fills B before `yes`) | book A; ask reschedule to B; a **2nd sender books B** | `yes` | `slotJustTaken` ("Sorry — that time was just taken…") | Verify Slot (R)→Check Race (R)(`race_lost:true`)→Race Gate (R)(lost)→Cancel New Event (R)(204, deletes OUR new event)→Build Reschedule Race-Lost State | Update Appointment (R) · Delete Old Event (R) — OLD row + event untouched; the 2nd sender's event survives |
| 32 | **reschedule verify-unavailable** ⚙(auth-strip; restore Verify Slot (R) auth → 2xx) | book A; ask reschedule to B; strip `Verify Slot (Reschedule)` auth | `yes` | `verifyIncomplete` ("We couldn't finish confirming that time just now…") | Book Reschedule Appointment(ok)→Verify Slot (R)(error out1)→Build Reschedule Verify-Unavailable State(`verify_unavailable`, NEW event KEPT) | Check Race (R) · Cancel New Event (R) · Delete Old Event (R) — never delete on an unverified read; OLD intact |
| 33 | **reschedule delete-old 404/gone → success** ⚙(inject fake OLD gid; restore: none — cleanup deletes rows) | book A; ask reschedule to B; set the appt row `gcal_event_id` to a **valid-shaped nonexistent** id | `yes` | `rescheduleDone` ("Moved — …") — a 404 on the OLD delete is a **success**, never a "couldn't move" | Delete Old Event (R)(404)→Classify Reschedule Delete(**gone**)→Reschedule Delete Gate(done/gone)→Build Reschedule-Done State | Build Reschedule Orphan State · any "couldn't move" message |
| 34 | **reschedule delete-old unavailable → orphan** ⚙(auth-strip; restore Delete Old Event (R) auth → 2xx) | book A; ask reschedule to B; strip `Delete Old Event (Reschedule)` auth | `yes` | `rescheduleDone` ("Moved — …") — honest, it WAS moved; `stage=handoff` + `reschedule_orphan` owner flag | Update Appointment (R)(ok)→Delete Old Event (R)(401)→Classify Reschedule Delete(**unavailable**)→Reschedule Delete Gate(unavailable)→Build Reschedule Orphan State | Build Reschedule-Done State — two events exist (OLD lingers), row→NEW |
| 35 | **reschedule update-row fail → mirror-failed** ⚙(break Update Appointment (R) table id; restore table → 2xx) | book A; ask reschedule to B; set `Update Appointment (Reschedule)` table to a bad id | `yes` | `rescheduleMirrorFailed` ("Your booking change is being finalized — a team member will confirm…") | Update Appointment (R)(error out1)→Build Reschedule Mirror-Failed State(`reschedule_mirror_failed`, NEW event exists) | Delete Old Event (R) (**does NOT run**) — row stays stale (OLD), NEW event exists |
| 36 | **reschedule stale-TTL → aborted** ⚙(inject stale `confirm_turn`) | book A; ask reschedule to B; set the conversation `confirm_turn` to a stale value (≠ turn_count) | `yes` | `rescheduleAborted` ("No problem — your booking stays as it is.") — fail-closed, NO move | Reschedule Router(true)→Reschedule Fresh?(**false**)→Build Reschedule-Aborted State | Find Old Booking (R) · Book Reschedule Appointment · any R: execute node — nothing moves |

**Handoff-class note (rule `handoff.md`):** #6 = infra-unavailable (503 + error flag, no state write); #18/#8/#9/#15 = intent-handoff (200, writes `stage=handoff`); #19 = guard-trip (200, transient, no counter increment). Reschedule: #28/#29/#31/#32/#34/#36 hand off (`stage=handoff`) with context; #25/#33 finish `stage=booked`; #27/#36 abort to `stage=new`.

### Pre-hours class fix — a REJECTED availability slot must not remain bookable

Compute Availability CLEARS the rejected slot on every non-available status, and Build Event Request has a
fail-closed booking-confirm gate (`stage='confirming'` + complete slot; else emit an empty eventId → the
existing `Event ID Valid?[false]→Mark Handoff` branch). A stray "yes" after a rejected slot **hands off,
never books**. Needle "team member" = the handoff reply (a real booking "You're booked…" never contains it).

| # | Name | Setup | Message sequence (session) | Expected reply | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|---|---|
| 37 | **pre-hours: closed → no book** | — | `Book … <before opening>` → `yes` | T1 "We're closed then — …" · T2 handoff ("…passing you to a team member…") | Compute Availability('closed', slot time CLEARED)→…; then Build Event Request(gate → `eventId:''`)→Event ID Valid?(false)→Mark Handoff | Book Appointment · Write Appointment — **no appointments row** |
| 38 | **pre-hours: past → no book** | — | `Book … <past date>` → `yes` | T1 "…has already passed…" · T2 handoff | Compute Availability('past', date+time CLEARED)→…→Mark Handoff | Book Appointment |
| 39 | **pre-hours: invalid date → no book** | — | `Book … 2026-02-30 …` → `yes` | T1 re-ask ("What day and time works…") · T2 handoff | Slot Gate(collecting; 2026-02-30 caught here)→…; stray `yes` → Build Event Request(gate)→Mark Handoff | Book Appointment |
| 40 | **pre-hours: busy → no book** ⚙(blocker) | a 2nd sender books slot X first | `Book … X` → `yes` | T1 "X is taken. Free that day: … Which works?" · T2 handoff | Compute Availability('busy', time CLEARED)→…→Mark Handoff | Book Appointment on X |

**Evidence (execution API + Airtable column, 2026-08-19):** closed = exec **690** (Compute Availability
`slots.time:null`, Save State drops `slot_time`; stage=collecting) + exec **691** (Build Event Request →
`booking.eventId:""` → Event ID Valid?(false) → Mark Handoff; **Book Appointment absent**). past · invalid ·
busy verified the same turn; **zero appointments rows** created across all four (column-verified). #37–#39
are in `run-regression.sh` (self-clean: they create no booking); #40 needs a blocker booking → ⚙.

---

### Phase 4 — Zernio inbound adapter + signature (CP4a) — ⚙ assisted (nested payload + HMAC signing; not in the widget-only `run-regression.sh`)
Fire against the production webhook with a Zernio-shaped body. For W1 the `X-Zernio-Signature` = lowercase-hex HMAC-SHA256 of the RAW body under the `crypto` credential's `hmacSecret`. Verify via the execution API / reply, never assume.

| # | Scenario | Setup | Steps | Expected | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|---|---|
| W1 | **valid Zernio signature → brain** | crypto cred hmacSecret set | POST nested `message.received` (whatsapp) + correct `X-Zernio-Signature` | 200; normal reply; `channel:whatsapp`, `sender_key:whatsapp:<sender.id>` | Is Zernio Inbound?(true)→Compute Body HMAC→Signature Valid?(true)→Load Config→…brain | Reject Unsigned Request |
| W2a | **wrong signature → 403** | — | same body + a bogus `X-Zernio-Signature` | HTTP **403** `{ok:false,error:"invalid_signature"}` | Signature Valid?(false)→Reject Unsigned Request | Load Config · Normalize · Extract Intent · Save State (exec 863: only 5 nodes ran) |
| W2b | **missing signature → 403** | — | same body, no signature header | HTTP **403** `invalid_signature` | Reject Unsigned Request | brain |
| W6 | **whatsapp missing sender.id → fail-loud** | — | nested body, `sender:{}` | execution `error` at Normalize (`missing sender.id (whatsapp)`); brain never runs | Normalize Inbound (throw) | Validate · Check Processed · Extract Intent (exec 853: 3 nodes) |
| IDOR | **forged channel → widget, not whatsapp** | — | UNSIGNED flat `{channel:'whatsapp', from:'<victim>', sessionId:'<attacker>'}` | `sender_key:widget:<attacker>` (NOT `whatsapp:<victim>`); no signature = no whatsapp: identity | Is Zernio Inbound?(false)→Normalize(widget branch, channel FORCED 'widget') | any `whatsapp:` sender_key |
| W-idem | **whatsapp idempotency** | 1st fire recorded | POST same nested body twice (same `platformMessageId`) | 2nd → `{status:"duplicate_ignored"}` (no LLM) | Check Processed(dup)→Idempotent Replay | 2nd Extract Intent / Save State |

**GATED (not "verified"):** byte-exact raw-body ↔ a real Zernio-signed request — confirm via Zernio `webhook.test` when the account is provisioned (the crypto credential currently holds a TEST secret; fail-closed until swapped to the real Zernio secret).

### Phase 4 — outbound lane (CP4b-1 convergence · CP4b-2 whatsapp send · CP4b-3 5xx/ACK policy)
The ONE channel-aware transport: 11 reply branches → Code tags (`_outbound_status/_body/_should_send`) → **Finalize Outbound** → **Channel Switch** → widget (synchronous, bit-identical) / whatsapp (ACK-200-first → Should Send? → Send WhatsApp (Zernio) → Outbound Send Failed). O2–O5 are ⚙ assisted (signed nested payload; execution API, never the reply). Empirical gate first: n8n continues after `respondToWebhook` (throwaway probe exec 996).

Full format — MUST-RUN / MUST-NOT-RUN are the topology assertions; exec-id is the committed proof.
| # | Scenario | Setup | Expected | MUST-RUN | MUST-NOT-RUN | exec-id |
|---|---|---|---|---|---|---|
| O1 | widget reply/status unchanged (convergence parity) | 11 branches converged; fire each branch on the widget channel | every branch's (status, body) **byte-identical** to pre-convergence (200 exact body · 400 → HTTP 400, responseCode expression works) | Finalize Outbound · Channel Switch(widget) · Send Reply (widget) | Respond ACK 200 (whatsapp) · Send WhatsApp (Zernio) | before==after **11/11** + **18/18** suite |
| O2 | whatsapp normal reply → send success | signed nested Zernio payload, normal-reply intent; Send URL → httpbin (2xx path) | ACK **200**; Send WhatsApp out0 body `{accountId, message}` correct; synchronous body NOT returned | Respond ACK 200 (whatsapp) · Should Send?(true) · Send WhatsApp (Zernio) | Send Reply (widget) · Outbound Send Failed | exec **998** (echo `{accountId:acct-mock-2, message:prices}`) |
| O3 | send-fail (real zernio, no account → 401) | signed payload; Send URL → real zernio.com, no account | ACK **200**; Send WhatsApp 401 → Outbound Send Failed (`zernio_send_failed` + owner-flag); **no 5xx** | Respond ACK 200 (whatsapp) · Send WhatsApp (Zernio) · Outbound Send Failed | Send Reply (widget) | exec **997** |
| O4 | whatsapp 400/503-class → coalesce (never-5xx) | signed payload, empty-text (400-class outcome) | **ACK 200** (NOT 400/503) + polite reply (notUnderstood) still sent | Respond ACK 200 (whatsapp) · Send WhatsApp (Zernio) | Send Reply (widget) · any 4xx/5xx respond | exec **1001** |
| O5 | whatsapp duplicate → no send | signed payload, duplicate messageId (already replied) | ACK **200**; `_outbound_should_send=false` | Respond ACK 200 (whatsapp) · Should Send?(false) | **Send WhatsApp (Zernio)** | exec **1000** |
| O6 | widget regression (whatsapp path stays dormant) | widget channel, full 18-case suite | widget synchronous body/status unchanged | Send Reply (widget) | Respond ACK 200 (whatsapp) · Send WhatsApp (Zernio) | **18/18** suite |

Guard: `check-outbound-inventory.py` holds the should_send rule + security-separation + widget-status-from-tag (FAIL-ability proven ×3: should_send flip · Reject-Unsigned converge · widget status hardcoded).

**GATED:** real Zernio 2xx delivery → CP4d (Zernio sandbox). The Bearer credential holds a TEST token (fail-closed) until swapped to the real Zernio API key.

### Phase 4 — CP4c reminder Zernio TEMPLATE send (STUB → real, dry-run gated) — ⚙ assisted
The reminders `Send Reminder (STUB)` NoOp is now `Send Disabled?` (IF on `bot.whatsappSendDisabled`) → dry-run log / `Send Reminder (Zernio Template)` (`POST /v1/inbox/conversations`, business-initiated → TEMPLATE required, not free text). Default `whatsappSendDisabled=true` = the shipped state = NO live send. Drilled via a temporary every-minute schedule + one planted due appointment (whatsapp, fake number `+490000000001`); both the appointment and the hourly schedule were RESTORED after (restore gate). Execution API, never a reply.
| # | Scenario | Setup | Expected | MUST-RUN | MUST-NOT-RUN | exec-id |
|---|---|---|---|---|---|---|
| RS1 | reminder normal (brake ON = dry-run) | `whatsappSendDisabled=true`; 1 due booked whatsapp appt | Send Disabled?→dry-run; payload correct (participantId=phone · templateName/Language from config · templateParams=`[service, {when} shop-tz]`); Stamp sets reminded=true | Send Disabled?(true) · Reminder Send (dry-run) · Stamp Reminded | **Send Reminder (Zernio Template)** · Reminder Error | exec **1080** (`{participantId:+490000000001, templateName:appointment_reminder, templateLanguage:en_US, templateParams:["Haircut","Sunday 23 Aug 22:00"]}`) |
| RS2 | reminder send-fail (brake OFF) | `whatsappSendDisabled=false`; 1 due appt; TEST bearer + mock accountId → real zernio.com **401** | Send Disabled?→Zernio send; 401 → error output → **Reminder Error visible**; `reminded` STAYS false (at-least-once → retried) | Send Disabled?(false) · Send Reminder (Zernio Template) · Reminder Error | Reminder Send (dry-run) · **Stamp Reminded** | exec **1081** (send node out0 empty, out1 populated → Reminder Error; Stamp did NOT run) |
| RS3 | restore gate (brake ON again) | `whatsappSendDisabled` restored true; 1 due appt | dry-run branch runs again; NO real send — proves the send brake is back on | Send Disabled?(true) · Reminder Send (dry-run) · Stamp Reminded | **Send Reminder (Zernio Template)** | exec **1082** |
| RS4 | **batch — TWO due in ONE run** (≥2 items) | `whatsappSendDisabled=true`; **2** due booked whatsapp appts (distinct numbers/services) | **BOTH** reminded in the single run: 2 dry-run payloads + 2 Stamps + both rows `reminded=true` | Build Reminder Payload=**2** · Reminder Send (dry-run)=**2** · Stamp Reminded=**2** | any 1-item cap | exec **1083** (`+490000000002` Haircut + `+490000000003` Beard Trim, both stamped) |

**Batch-drop fix (2026-08-23):** `Build Reminder Payload` + `Reminder Send (dry-run)` defaulted to `runOnceForAllItems` → `$json` = first item only → >1 due row in one hourly run reminded only the FIRST (rest slip to later hours; not a permanent loss but the reminder fires hours late, not 24h before). Fixed to `runOnceForEachItem` (both bodies were already per-item; return changed `[{json}]`→`{json}`). **SUITE LESSON:** RS1–RS3 (and CP5's R1–R8) all ran with a SINGLE due row, so a single-item test could NEVER see this — RS4 exists because **every batch/loop path must be tested with ≥2 items** (ARCH-DEC §5, 2026-08-23).
R1/R2/R4 (CP5 reminder engine — happy · idempotency · kill-switch) regression: R1 happy now covered by RS4 (multi) + RS1 (single); R2 0-due clean no-op re-proven post-fix (exec 1085 — Find Due ran, 0 items, no downstream node); R4 kill-switch is upstream of the changed nodes (Kill-Switch Gate untouched) → inherited from CP5 exec 790.
**GATED:** real Zernio 2xx template delivery → CP4d (Zernio sandbox + Yigitcan's cost approval). `whatsappSendDisabled=true` is the shipped default — flipping it to `false` is the one-config-flag switch to live.

### Phase 4 — CP4d-1 real WhatsApp e2e (shared Zernio sandbox, LIVE — 2026-08-23)
A real WhatsApp message from the tester's own phone (activated as a sandbox recipient), delivered SIGNED by Zernio to the production `/webhook/barber-inbound`. Verified via the execution API (tester's number masked/purged; the Zernio webhook was set `isActive:false` after the drill).
| # | Scenario | Expected | Proof |
|---|---|---|---|
| D1-a | real signed inbound → HMAC gate | real Zernio `X-Zernio-Signature` passes `Compute Body HMAC → Signature Valid?`; `Reject Unsigned Request` MUST-NOT-RUN | exec **1100/1102** HMAC OK (closes CP4a "GATED: real signed request") |
| D1-b | real booking + real 2xx reply | brain books (Book + Write Appointment) → `Send WhatsApp (Zernio)` delivers a **real 2xx** to the phone ("You're booked: …") | exec **1102** (closes CP4b-2 "GATED: real 2xx delivery" — was httpbin/401 before) |
| D1-c | **real provider double-delivery → idempotency** | Zernio delivered EACH message **twice** (4 execs / 2 unique `message_id`s) → the duplicate hits `Check Processed → Is Duplicate → Idempotent Replay` → **exactly one booking, no double-book** | exec **1101 + 1103** (Idempotent Replay) — booking-integrity idempotency under a REAL retry, **not a synthetic duplicate**; case-study-grade |
| D1-d | (B) sandbox isolation | only the tester's single `sender_key` across all execs; no foreign sandbox user's traffic reaches our webhook | all 4 execs one sender_key (empirical isolation, not just docs) |

**Case-study note:** D1-c is the strongest kind of evidence — the idempotency guard was designed for exactly this (a provider retrying at-least-once), and Zernio *actually did it* in the wild, and the guard held. No test could manufacture a more honest proof.

### ⚙ Owner-alert drills (CP5a) — execution API + real Telegram delivery, NEVER the reply text
Verify from the execution (`Build Owner Alert` output + `Send Owner Alert` Telegram 2xx) and a real message to the
owner chat; **D-c**: the customer reply is byte-identical to pre-CP5a on every one (alert branch is off the reply path).

| # | Scenario | Setup | Expected | MUST-RUN | MUST-NOT-RUN | Evidence |
|---|---|---|---|---|---|---|
| A1 | intent-handoff alert | low-conf/gibberish msg | Telegram `handoff` alert w/ sender/intent/stage; reply = `handoff` template | Build Owner Alert · Send Owner Alert | — | exec 1131 (msg_id 4) |
| A2 | **throttle 5→1 (KK1)** | lock a thread, then 5 msgs to it | first locked → `handoff_lock` alert; msgs 2-5 → Build Owner Alert `[]` (throttled) | (1st) Send Owner Alert | (2-5) Send Owner Alert | exec 1138 alert / 1142 suppressed |
| A3 | D-c on throttle | same 5 msgs | every reply = `handoffLocked`, 200 (unchanged) | Finalize Outbound | — | 1138/1142 Finalize |
| A4 | mirror_failed (post-write builder) | break Write Appointment table, book | reply still **"You're booked"** (D-c) + `mirror-failed` alert w/ slots | Build Mirror-Failed State · Send Owner Alert | — | exec 1147 (msg_id 8) |
| A5 | **KK2 max-turns** | `maxTurns=2`, 3rd msg | `max-turns` alert; reply = handoff | Handoff Reply · Send Owner Alert | — | exec 1152 (msg_id 9) |
| A6 | **KK2 kill-switch SUPPRESS** | `killSwitch=true`, 1 msg | Build Owner Alert `[]` (owner set it); reply = handoff | Handoff Reply | Send Owner Alert | exec 1153 |
| A7 | alert-channel-down (D-c) | underscore class → Telegram parse-error | `Owner Alert Failed` visible; reply unaffected | Owner Alert Failed | — | exec 1138 (pre Markdown-safe fix) |
| A8 | reminders reminder-error | temp trigger + break Find Due | `reminder_error` alert w/ detail (reminders wf) | Build Owner Alert (Reminders) · Send | — | exec 1154 (msg_id 10) |
| A9 | recent_messages context (D-a) | 2 normal msgs + handoff | alert carries `recent: … | … | …` (last-5) | Build Owner Alert | — | exec 1240 (msg_id 24) |
| A10 | no false-positive | normal FAQ | Build Owner Alert `[]`, no alert; reply normal | — | Send Owner Alert | exec 1155 |

## Baseline run

**CP4 reschedule end-to-end · 2026-08-19 · published production webhook.**

**Automated (curl-only subset, `run-regression.sh`): 18/18 PASS, 0 FAIL** —
#1 booking · #4 cancel happy (204) · #11 confirm-TTL fresh · #16 FAQ · #17 lead · #18 handoff ·
#13 Abort-FAQ · #3 idempotency · #20 invalid-payload 400 · #21 cancel-no-booking · #22 handoff-lock ·
#24 reschedule-no-booking · #25 reschedule-happy (end-to-end move → "Moved") · #27 reschedule-abort ·
**#37 pre-hours-closed · #38 pre-hours-past · #39 pre-hours-invalid** (stray "yes" → handoff, never a booking).
The 3 reschedule scenarios self-clean (happy cancels the MOVED booking; abort cancels the standing one); the
pre-hours scenarios create no booking (handoff). The reschedule FAILURE paths (#28–#36) need injected Airtable
state / stripped auth (and #28 past-guard hands off → locked, so curl cannot self-clean it), and #40 pre-hours
busy needs a blocker booking → they are ⚙, verified via the execution API (below).
Harness bugs found + fixed on the way (flow was correct each time): (a) idempotency returns
`duplicate_ignored`, not a replay — expectation corrected; (b) the Abort scenario left its 16:00
booking so a re-run correctly **lost the race** — the harness now self-cleans that booking.

### Known-failing under a full rapid run — flagged for Phase 7 CRT #1a review (NOT dismissed as flake)
A full `run-regression.sh` pass on 2026-08-24 (during CP5a) returned **18/20**: two scenarios failed under
rapid sequential load and BOTH passed on isolated retry. They are recorded here as **open items to
investigate**, not test noise — a "flake" label would wrongly close the investigation.

- **#3 idempotency — SUSPECTED PRODUCT RACE (Phase 7, CRT #1a).** Observed: under load, a duplicate `messageId`
  fired **immediately** after the first response was NOT deduped (got the real reply, not `duplicate_ignored`).
  Isolated retry (×4) always dedupes correctly. **Hypothesised cause = a narrow real product race, not test
  noise:** `Record Processed` writes the id AFTER the webhook response is sent (it is a sibling of Build Reply
  Payload, whose subtree emits the response), so a fast enough duplicate reaches `Check Processed` before the
  id is recorded. This is **not hypothetical** — CP4d-1 showed Zernio itself double-delivers in the wild
  (exec 1101/1103), and there the deterministic booking event-id (409 reconcile) is what actually prevented a
  double-book, i.e. the front-gate idempotency was already best-effort. Phase 7 must decide: record-before-respond
  (adds latency) vs accept-and-document (the event-id is the real no-double-book guard). Do NOT close as flake.
- **#27 reschedule-abort — SHARED-CALENDAR TEST ISOLATION (confirm under Phase 7).** Observed: the move-target
  slot was busy during the full run → the product **correctly handed off** (`stage=handoff`) → the next FAQ turn
  hit the handoff-lock, so the assertion ("booking stays") failed. Isolated retry on a clean date/time aborts
  correctly. Likely root = the suite shares ONE Google Calendar, so a sibling scenario's event can occupy the
  target; the product behaviour looks correct (busy → handoff). Phase 7: give reschedule scenarios
  non-colliding slots (or a dedicated calendar) and confirm no concurrency angle (CRT #1b) hides behind it.

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

**⚙ Reschedule setup-heavy (assisted, verified 2026-08-19 via the execution API + Airtable column, never the reply):**

| # | Scenario | Evidence (exec) | Verified |
|---|---|---|---|
| 29 | target-invalid → NeedsHuman, NO insert | **497** | `_reschedule_valid:false` → Build Reschedule-NeedsHuman State; Book Reschedule Appointment did NOT run |
| 30 | insert-fail → original stands | **501** | Book Reschedule 401 out1 → Insert-Failed → Save State (Post-Write); OLD row + event untouched |
| 31 | race-lost → slotJustTaken | **538** | `race_lost:true`/`race_other_count:1` → Cancel New Event (R) 204 (OUR new event) → Race-Lost; OLD intact |
| 25/26 | race-WIN + happy commit | **532 / 577** | 532: `race_lost:false`, Race Gate won, Cancel New Event did NOT run. 577: Update ran BEFORE Delete; OLD 204-deleted, NEW exists, row=B, stage=booked, "Moved" |
| 32 | verify-unavailable → NEW kept | **542** | Verify Slot (R) 403 out1 → Verify-Unavailable (`verify_unavailable`, NEW kept); Check Race did NOT run; OLD intact |
| 33 | delete-old 404/gone → success | **588** | fake OLD gid → Delete 404 → Classify `gone` → Done, "Moved", NO false error |
| 34 | delete-old unavailable → orphan | **592** | Delete 401 → Classify `unavailable` → Orphan (`reschedule_orphan`, two events, row→NEW, honest "moved") |
| 35 | update-row fail → mirror-failed | **596** | Update table broken → error out1 → Mirror-Failed; Delete did NOT run; NEW exists, row stale |
| 36 | stale-TTL → aborted | **600** | injected stale `confirm_turn` → Reschedule Fresh?(false) → Aborted; NO R: execute node ran; old intact |

Every auth/table-break drill was **restored** (Book/Verify/Delete auth → `predefinedCredentialType`; Update
table id → real) and re-verified (live 2xx, suite 15/15, content-parity byte-for-byte, committed
injection-free). All drill GCal events + Airtable rows cleaned via bot-cancel + delete (reschedule creates a
2nd event; orphan events are cleaned by re-pointing the row and bot-cancelling again).

**BASELINE = healthy.** Re-run `run-regression.sh` at the start of a phase and after every step;
any drop from 18/18, or any MUST-NOT-RUN node appearing, is a regression.

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
