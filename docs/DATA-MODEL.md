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
| Field | Type | Notes |
|---|---|---|
| id | autonumber | PK |
| customer_phone | text | link to customer (PII) |
| service_id | text | from client.config services |
| start_utc | datetime | **UTC** — display in shop tz |
| end_utc | datetime | UTC |
| gcal_event_id | text | Google Calendar event id (for re-verify + undo) |
| channel | single-select | whatsapp \| widget \| instagram — origin channel of the booking (reply-to-origin; shown on the owner dashboard) |
| status | single-select | booked \| cancelled \| handoff |
| created_at | datetime | UTC |

## `conversations` (multi-turn slot-filling state)
| Field | Type | Notes |
|---|---|---|
| sender_key | text | PK — `"{channel}:{id}"` using the FULL channel name (matches the config channels enum), e.g. `whatsapp:+43…`, `instagram:12345` — namespaced so channels can never collide (PII) |
| stage | single-select | new \| collecting \| ready \| done \| handoff — while `handoff`, the bot sends no auto-reply to this sender (see decision log 2026-07-02) |
| slot_service | text | nullable |
| slot_date | text | nullable |
| slot_time | text | nullable |
| last_updated | datetime | UTC (for TTL/expiry) |

## `processed_messages` (idempotency / dedupe)
| Field | Type | Notes |
|---|---|---|
| message_id | text | PK — provider message id |
| result_ref | text | booking/lead id produced |
| processed_at | datetime | UTC (with TTL) |

**Booking integrity:** `processed_messages` guards idempotency; `appointments` + Google Calendar guarded by
write-then-verify (no atomic lock). See [../.claude/rules/booking-integrity.md](../.claude/rules/booking-integrity.md).

<TODO (Phase 3): confirm exact field types against the real Airtable base>
