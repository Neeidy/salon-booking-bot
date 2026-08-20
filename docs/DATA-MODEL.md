# Data model — Airtable tables

> **Role of this file:** the human-readable field map for the Airtable base (the CRM + state store).
> Machine-checkable contracts live in [`../schemas/`](../schemas/). Draft — finalized in Phase 1/3.

Five tables. `leads` / `customers` / `appointments` are the CRM; `conversations` / `processed_messages`
are the engine's state (multi-turn + idempotency).

## `leads`
| Field | Type | Notes |
|---|---|---|
| id | autonumber | PK |
| name | text | customer name (PII) |
| phone | text | E.164 (PII) |
| source | single-select | whatsapp \| widget \| instagram |
| message | long text | first message |
| status | single-select | new \| contacted \| converted |
| created_at | datetime | UTC |

## `customers`
| Field | Type | Notes |
|---|---|---|
| id | autonumber | PK |
| name | text | PII |
| phone | text | E.164, unique-ish (PII) |
| notes | long text | preferences |
| created_at | datetime | UTC |

## `appointments`
> Field names reflect the **live Airtable base** (corrected CP5 2026-08-20 — the earlier
> `customer_phone`/`service_id` names never matched the running system; see decision log).

| Field | Type | Notes |
|---|---|---|
| sender_key | text | `"{channel}:{id}"` — the booking's owner; the IDOR-safe cancel/reschedule lookup key (never a customer-supplied id) (PII) |
| service | text | service name, from client.config services |
| start_utc | datetime | **UTC** — display in shop tz |
| end_utc | datetime | UTC |
| gcal_event_id | text | Google Calendar event id (re-verify · cancel/reschedule delete) |
| calendar_id | text | the GCal calendar the event lives on, stored at booking (CP3/Codex#8) — cancel/reschedule delete uses the STORED calendar+event pair, so a later config-calendar change can't delete on the wrong calendar |
| channel | text | origin channel — whatsapp \| widget \| instagram |
| customer_name | text | nullable (PII) |
| status | single-select | booked \| cancelled |
| **reminded** | checkbox | **CONTROL** — the reminder dedupe flag (CP5). Reminders selects `NOT({reminded})`; Stamp sets `true`; **reschedule sets `false`** so a moved appointment re-reminds. It is a boolean because native n8n cannot clear a dateTime (null is omitted, `''` is rejected → a `reminder_sent` clear would 422 into Mirror-Failed). |
| reminder_sent | datetime | **INFO** (nullable) — when the last reminder fired (`bot.reminderHoursBefore` before `start_utc`). NOT the dedupe key (`reminded` is); reschedule does **not** touch it, so it honestly records the last send (CP5). |
| created_at | datetime | UTC |

> **Availability source of truth = Google Calendar** (owner "busy" blocks live in GCal too); Airtable
> `appointments` mirrors it. Booking write order: **GCal first, then Airtable**. See
> [ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md) §6.

## `conversations` (multi-turn slot-filling state)
| Field | Type | Notes |
|---|---|---|
| sender_key | text | PK — `"{channel}:{id}"` using the FULL channel name (matches the config channels enum), e.g. `whatsapp:+43…`, `instagram:12345` — namespaced so channels can never collide (PII) |
| stage | single-select | new \| collecting \| ready \| done \| handoff — while `handoff`, the bot sends no auto-reply to this sender (see decision log 2026-07-02) |
| slot_service | text | nullable |
| slot_date | text | nullable |
| slot_time | text | nullable |
| last_updated | datetime | UTC (for TTL/expiry) |
| turn_count | number | default 0 — +1 on every inbound message; compared with config `bot.maxTurnsPerConversation` for the max-turns guard (CP3) |
| last_intent | single line text | nullable — last classified intent (debug/analysis) (CP3) |

> **CP3 prerequisite:** `turn_count` and `last_intent` must also be created as columns in the real Airtable
> `conversations` table (Yigitcan) before the CP3 flow can write them.

## `processed_messages` (idempotency / dedupe)
| Field | Type | Notes |
|---|---|---|
| message_id | text | PK — provider message id |
| result_ref | text | booking/lead id produced |
| processed_at | datetime | UTC (with TTL) |

**Booking integrity:** `processed_messages` guards idempotency; `appointments` + Google Calendar guarded by
write-then-verify (no atomic lock). See [../.claude/rules/booking-integrity.md](../.claude/rules/booking-integrity.md).

<TODO (Phase 3): confirm exact field types against the real Airtable base>
