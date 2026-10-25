# booking-integrity

**Purpose:** the core correctness rule — **zero double-bookings**, even without an atomic lock.

**The store (since the cutover of 2026-10-24):** self-hosted **Postgres**, schema `salon`
(`db/schema/001_init.sql`). Airtable is **read-only until D6c** — the parked original workflows still point at
it as the rollback path, and nothing live writes it (`docs/MIGRATION-PLAN.md` §7).

Two DISTINCT problems, two DISTINCT guards (do not conflate them):

1. **Idempotency — same message processed twice.**
   Dedupe on message-ID via a persistent store: the Postgres table `salon.processed_messages`, whose
   `message_id` is **UNIQUE** (`001_init.sql`), plus a 30-day TTL (the Purge workflow deletes older rows).
   `Check Processed` reads the ID first; if it was seen, `Is Duplicate` → `Idempotent Replay` answers
   `duplicate_ignored` and nothing is booked again. *(It returns no stored copy of the first reply — the
   "Idempotent Replay stored reply" item is in the v2 bucket, PHASE-7-PLAN → "Open items", v2 / LATER row.)*
   `Record Processed` writes it after `Save State` with `INSERT … ON CONFLICT (message_id) DO NOTHING`, so a
   second marker for the same ID is a no-op, not an error.
   ⚠ **The UNIQUE does not close the check-then-record race** (CRT 1a): two deliveries of one message can both
   pass `Check Processed` before either records. The constraint only stops the second MARKER; it does not stop
   the second RUN. That race was deliberately left for Phase 7 (ruling Q5, recorded in the schema comment).

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
   **The known limit, stated rather than hidden:** a truly simultaneous pair can make BOTH writers see the
   other and BOTH yield — no double booking, but no booking either. The race must be **visible and
   recoverable** — never pretend a lock exists.

**Timezone:** store times in **UTC**, display in the shop's configured timezone. Handle DST at the boundary.

**Verified by:** `qa-tester` (duplicate trigger → one booking; concurrent same-slot → one booking + handoff)
and Codex (Critical-Review Targets 1a/1b). On Postgres, the cutover's race drill (MIGRATION-PLAN §3t,
Round 3c, A3) is SEQUENTIAL evidence only — the second confirm was sent after the first reply; the
simultaneous pair is a separate Phase 7 drill. Owned on the canvas per [n8n-conventions.md](n8n-conventions.md).

**Why:** "zero double-bookings" is in the success metric — this file is the product's correctness contract.
