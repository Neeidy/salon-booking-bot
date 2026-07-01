# booking-integrity

**Purpose:** the core correctness rule — **zero double-bookings**, even without an atomic lock.

Two DISTINCT problems, two DISTINCT guards (do not conflate them):

1. **Idempotency — same message processed twice.**
   Dedupe on message-ID via a persistent store (`processed_messages` in Airtable + a TTL). If the ID was
   seen, return the prior result; do not book again.

2. **Concurrency / no-double-book — two DIFFERENT customers, same slot, ~same time.**
   Airtable + Google Calendar have **no atomic lock / transaction** across them → a TOCTOU gap between the
   availability-check (read) and the write. Guard = **write-then-verify**:
   `write → re-read the slot → if >1 event exists, cancel one + human handoff`.
   The race must be **visible and recoverable** — never pretend a lock exists.

**Timezone:** store times in **UTC**, display in the shop's configured timezone. Handle DST at the boundary.

**Verified by:** `qa-tester` (duplicate trigger → one booking; concurrent same-slot → one booking + handoff)
and Codex (Critical-Review Targets 1a/1b). Owned on the canvas per [n8n-conventions.md](n8n-conventions.md).

**Why:** "zero double-bookings" is in the success metric — this file is the product's correctness contract.
