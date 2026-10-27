# booking-integrity

**Purpose:** the core correctness rule — **zero double-bookings**, even without an atomic lock.

**The store (since the cutover of 2026-10-24):** self-hosted **Postgres**, schema `salon`
(`db/schema/001_init.sql`). Airtable was **retired at D6c** (2026-10-27): the original workflows
are archived and n8n's Airtable credential is deleted, so nothing reaches it (`docs/MIGRATION-PLAN.md` §7a).

Two DISTINCT problems, two DISTINCT guards (do not conflate them):

1. **Idempotency — same message processed twice.**
   Dedupe on message-ID via a persistent store: the Postgres table `salon.processed_messages`, whose
   `message_id` is **UNIQUE** (`001_init.sql`), plus a 30-day TTL (the Purge workflow deletes older rows).
   **Claim-first** (7-2 Tur 2, ruling R-1a; live since 7-2 R3): `Check Processed` CLAIMS the ID at the start of the
   turn in ONE statement — `INSERT … ON CONFLICT (message_id) DO NOTHING RETURNING` — and `Dedupe Gate` reads the
   result: a returned row means this run owns the message; no row means another delivery already claimed it
   (sequential redelivery or a concurrent run alike), so `Is Duplicate` → `Idempotent Replay` answers
   `duplicate_ignored` and nothing is booked again. *(It returns no stored copy of the first reply — the
   "Idempotent Replay stored reply" item is in the v2 bucket, PHASE-7-PLAN → "Open items", v2 / LATER row.)*
   The UNIQUE on `message_id` is what makes the claim atomic, so the check-then-record race of CRT 1a is CLOSED:
   two deliveries cannot both claim. `Record Processed` (the end-of-turn marker) and its alert are gone.
   ⚠ **The cost, stated:** at-most-once. A run that dies AFTER its claim is not retried for that message — node
   failures still reach their error branches and owner alerts; an engine crash shows only in n8n's execution log.

2. **Concurrency / no-double-book — two DIFFERENT customers, same slot, ~same time.**
   **Google Calendar is the availability source of truth**, and the Calendar write happens **outside any
   Postgres transaction**. Postgres has transactions; they cannot span an HTTP call to Google. So there is
   still **no atomic lock across Postgres + Calendar** → a TOCTOU gap between the availability check (read)
   and the write. Guard = **write-then-verify**, and it is what the Main workflow does:
   `Book Appointment` (Calendar insert) → `Verify Slot` (re-read the slot window with `events.list`) →
   `Check Race` (any OTHER non-cancelled, non-transparent event overlapping our slot = we lost) →
   `Race Gate`: lost → `Cancel Our Event` (we yield OUR event, never the other one) → `Build Race-Lost State`
   (handoff); won → only then `Write Appointment` (the Postgres mirror row).
   A verify read that is paginated or whose calendar timezone differs from the shop's is treated as lost
   (`verify_incomplete`) — an uncertain read never enters the happy path. If the yield itself fails →
   `Build Orphan State` + owner alert.
   **The known limits, stated rather than hidden:**
   - A truly simultaneous pair whose verify reads SUCCEED can make BOTH writers see the other and BOTH yield — no
     double booking, but no booking either.
   - A verify read that FAILS (Calendar unreachable: `Build Verify-Unavailable State` and its reschedule twin) is a
     different path, and there "no double booking" does NOT hold: the writer cannot tell whether it lost, so it keeps
     its event and hands off — and two such writers can BOTH keep theirs, leaving two events on one slot. The bound
     there (ruling R-Q1, staged Main of 7-2 Tur 2): both customers are handed off, and the owner is alerted with the
     slot and the possible overlap, to keep one event and cancel the other by hand. *(This paragraph used to state the
     first limit as the only one; Codex 7-2 target 1b showed the second path, R2 found the text still uncorrected.)*
   The race must be **visible and recoverable** — never pretend a lock exists.

**Timezone:** store times in **UTC**, display in the shop's configured timezone. Handle DST at the boundary.

**Verified by:** `qa-tester` (duplicate trigger → one booking; concurrent same-slot → one booking + handoff)
and Codex (Critical-Review Targets 1a/1b). On Postgres, the cutover's race drill (MIGRATION-PLAN §3t,
Round 3c, A3) is SEQUENTIAL evidence only — the second confirm was sent after the first reply; the
simultaneous pair is a separate Phase 7 drill. Owned on the canvas per [n8n-conventions.md](n8n-conventions.md).

**Why:** "zero double-bookings" is in the success metric — this file is the product's correctness contract.
