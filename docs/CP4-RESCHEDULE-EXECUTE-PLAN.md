# CP4 sub-step 3 — Reschedule EXECUTE (locked build plan)

> **Status when written (2026-08-18):** sub-step 2 (confirm lifecycle) DONE + pushed. Phases 0–2 of
> sub-step 3 DONE + pushed (`51dd9aa`): push · Save State `|| ''` alignment (`acd3c4b`) · content-parity
> guard (`51dd9aa`). **This doc is the locked plan for the remaining build — reschedule EXECUTE.** A fresh
> session reads this + the resume-memory and continues at the "Next step" marker below.

## What this replaces
The live workflow has a TEMP placeholder `Build Reschedule-Executing State` (sub-step 2) wired at
`Reschedule Fresh? [out0 = fresh]`. It sets `stage=handoff` + "Great — I'm moving your booking now…" and
hands off. This build replaces it with the real move.

## Inputs available at `Reschedule Fresh? [out0 fresh]`
On the confirm ("yes") turn, the loaded conversation state carries what sub-step 2's confirm-ask persisted:
- `state.slots = { serviceId, date, time }` — the **NEW** slot (persisted by Compute Reschedule Availability).
- `state.cancel_target_id` — the **OLD** appointment's Airtable `recordId`.
- `sender_key`, etc. (`Merge Slots` does NOT run on a confirm turn, so slots are the persisted NEW slot.)

## Locked order (MANDATORY — never reorder)
**book-new-first → update-row → delete-old.** At every intermediate point the customer still has a valid
booking. The reverse order would leave the customer with no booking if a step fails mid-way.

### (a) Open the new booking
1. **Find Old Booking (Reschedule)** — Airtable search appointments by `sender_key` + `status=booked`
   (clone of `Find Booking (Reschedule)`; IDOR-safe, never a customer-supplied id). Error → `Send Error
   Response` (503, infra class, like `Find Booking`).
2. **Validate Reschedule Target** — bind to `state.cancel_target_id` among the results; validate the OLD row
   `structOk` = {finite `start_utc`, `gcal_event_id` shape `^[0-9a-v]{5,1024}$`, `calendar_id` present} AND
   the cancellation cutoff on the OLD booking (clone of `Validate Cancel Target` logic). Sets
   `_reschedule_target = {recordId, gcal_event_id, calendar_id, service, start_utc}` + `_reschedule_valid`.
   Target vanished/invalid → `_reschedule_valid=false`.
3. **Reschedule Target Valid?** (IF) — true → Build Reschedule Event Request · false → **Build
   Reschedule-NeedsHuman State** (handoff, neutral message; **NO delete, NO insert** on this branch).
4. **Build Reschedule Event Request** — clone `Build Event Request`; reads `state.slots` (the NEW slot),
   builds the events.insert payload + a **new deterministic** `eventId = hex(sender_key|newdate|newtime|
   serviceId)`. **Change vs template:** spread `...$json` (NOT `...vi`) so `_reschedule_target` survives.
5. **Book Reschedule Appointment** — clone `Book Appointment` (POST events.insert, googleApi, 15 s timeout).
   `onError` → **Build Reschedule Insert-Failed State** (OLD booking intact, "couldn't move — your original
   stands", handoff). **Decision:** a 409 (same key already inserted) routes here too, NOT to a reconcile
   chain — message-level idempotency (`processed_messages`) already dedupes a repeated messageId, so the
   only 409 is a lost-response retry; "original stands + handoff" is safe. (Deviation from booking, which
   reconciles; recorded in ARCH-DEC §5.)

### (b) Verify the new booking (write-then-verify, no double-book on the NEW slot)
6. **Verify Slot (Reschedule)** — clone `Verify Slot`; refs `Build Reschedule Event Request` (NOT `Build
   Event Request`). `onError` → **Build Reschedule Verify-Unavailable State** (new event kept, OLD intact,
   handoff — never delete old on an unverified new booking).
7. **Check Race (Reschedule)** — clone `Check Race`; refs `Build Reschedule Event Request`. Drops
   cancelled + transparent + OUR new event; any OTHER overlap ⇒ `race_lost`.
8. **Race Gate (Reschedule)** (IF `race_lost`):
   - lost → **Cancel New Event (Reschedule)** (DELETE OUR new event, never a pre-existing one) → **Build
     Reschedule Race-Lost State** (OLD intact, `slotJustTaken`, handoff).
   - won → (c).

### (c) Commit the move
9. **Update Appointment (Reschedule)** — Airtable UPDATE the SAME row (`_reschedule_target.recordId`):
   `gcal_event_id=` new id, `start_utc`/`end_utc=` new UTC, `calendar_id`. `onError` → **Build Reschedule
   Mirror-Failed State** (new event booked, row NOT updated → handoff + visible flag).
10. **Delete Old Event (Reschedule)** — clone `Delete Booking Event` (DELETE OLD `_reschedule_target.
    gcal_event_id`, `fullResponse+neverError`, 15 s).
11. **Classify Reschedule Delete** — clone `Classify Cancel Delete`, **statusCode ONLY** (204/200→`done` ·
    404/410→`gone` · else→`unavailable`). **NO error-text matching.**
12. **Reschedule Delete Gate** (IF `unavailable`):
    - unavailable → **Build Reschedule Orphan State** (new booked + row updated, OLD event lingers →
      handoff + visible flag for owner reconcile; the customer IS told "moved" because it was).
    - done/gone → **Build Reschedule-Done State** (`stage=booked`, `gcal_event_id=` new, "Moved: your
      {service} is now {newWhen}").

## Failure builders (all set `computed_reply`; all → `Save State (Post-Write)` except NeedsHuman → `Save State`)
| Builder | State | Customer message | Owner-visible flag |
|---|---|---|---|
| Build Reschedule-Done State | stage=booked, new gcal_id | "Moved: {old} → {new}" | — |
| Build Reschedule Insert-Failed State | handoff (old intact) | "couldn't move — your original stands" | — |
| Build Reschedule Race-Lost State | handoff (old intact) | slotJustTaken | — |
| Build Reschedule Verify-Unavailable State | handoff (new kept, old intact) | verifyIncomplete-style | verify_unavailable |
| Build Reschedule Mirror-Failed State | handoff (new booked, row stale) | "confirming the move…" | reschedule_mirror_failed |
| Build Reschedule Orphan State | booked (new), old lingers | "moved" (honest — it was) | reschedule_orphan |
| Build Reschedule-NeedsHuman State | handoff | rescheduleNeedsHuman / neutral gone | — |

## Config templates to add (both places: `config/client.config.example.json` AND the `Load Config` node)
`rescheduleDone` ("Moved — your {service} is now {when}."); reuse existing `slotJustTaken`,
`verifyIncomplete`, `rescheduleNeedsHuman` where they fit; add `rescheduleMirrorFailed` /
`rescheduleOrphan` only if a distinct message is wanted (else fold into a neutral handoff).

## Decisions (record in ARCHITECTURE-DECISIONS.md §5 at commit)
- **book-new-first order** — customer always holds a valid booking at every intermediate failure point.
- **409 → insert-failed (not reconcile)** — message-dedup covers repeated messageIds; a lost-response 409
  is rare and "original stands + handoff" is safe. Simpler than cloning the reconcile chain.
- **delete-old classification = statusCode only** — identical to `Classify Cancel Delete`; never text-match.
- **Parallel chain, not routing through the booking path** — isolates the proven booking/cancel paths from
  reschedule changes (same reasoning as the sub-step-1 dedicated discovery nodes).

## ⚙ Drill matrix (ALL hand-run BEFORE commit; execution API + Airtable column, NEVER the reply)
| Drill | Setup | Expected |
|---|---|---|
| happy | book 11:00 → reschedule 13:00 → yes | OLD event GONE, NEW event EXISTS, row = 13:00, reply "Moved: 11:00 → 13:00" |
| race | a 2nd event fills the NEW slot before "yes" | no move, OLD intact, Cancel New Event ran, race-lost |
| delete-old fail | pre-delete the OLD event (404) | `gone` classified, move still succeeds (done) |
| insert fail | Book Reschedule auth:none (or force error) | OLD intact, "original stands", NO row update, NO delete |
| idempotency | same messageId twice | one move (message-dedup short-circuits the 2nd) |
| stale TTL | inject a stale `confirm_turn` | NO move (Reschedule Fresh? out1 → aborted) — regression of sub-step 2 |
| target-valid false | invalid/gone target | NeedsHuman, **NO delete, NO insert** |

## Build method
Python construction-script clones the templates (lower error risk than hand-written JSON), rewires each
clone's internal `$('...')` node refs to the reschedule node names, adds nodes + connections to a GET'd
live workflow, and PUTs via the raw API (MCP save is blocked — see [n8n-rollback.md](n8n-rollback.md)).
After each PUT: `n8n_validate_workflow` + the drills. Snapshot the whole live workflow to
`n8n/.snapshots/` (gitignored) before the first PUT for rollback.

**Node-ref rewiring checklist (the #1 clone hazard):** `Verify Slot (Reschedule)` and `Check Race
(Reschedule)` reference `Build Reschedule Event Request`, NOT `Build Event Request`. `Build Cancelled
State`-style refs to `Validate Cancel Target` / `Classify Cancel Delete` become `Validate Reschedule
Target` / `Classify Reschedule Delete`. `Delete Old Event` uses `_reschedule_target.{calendar_id,
gcal_event_id}`. Miss one and a reschedule node silently reads booking-path data.

## Incremental build order (one verifiable step at a time — NEVER 13 nodes at once)
- **Next step → sub-phase (a)** — the ~6 new-event-core nodes (Find Old Booking · Validate Reschedule
  Target · Reschedule Target Valid? · Build Reschedule Event Request · Book Reschedule Appointment · Build
  Reschedule Insert-Failed State · Build Reschedule-NeedsHuman State). **Book success is TEMPORARILY wired
  to the existing `Build Reschedule-Executing State` placeholder** until (b) is built. Verify: new GCal
  event created · OLD event still present · validate chain (bind + structOk + cutoff) works · the
  `Reschedule Target Valid? = false` branch does NO delete / NO insert. Then suite 12/12 · 5 guards ·
  parity · host-leak · security-auditor · commit.
- **Then (b)** — verify/race, only after (a) is green. **Then (c)** — update/delete/done + failure builders.
- Each sub-phase: snapshot → construct → PUT → `n8n_validate_workflow` → ⚙ drills → guards → commit.

## Stop conditions (unchanged)
guard FAIL-ability unprovable · suite/⚙ drill breaks · content-parity shows an unexpected drift · a change
not in this plan becomes necessary → snapshot rollback + report + STOP.
