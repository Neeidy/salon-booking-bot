# Data model — Airtable tables

> **Role of this file:** the human-readable field map for the Airtable base (the CRM + state store).
> Machine-checkable contracts live in [`../schemas/`](../schemas/). Draft — finalized in Phase 1/3.

Five live tables. `leads` / `appointments` are the CRM; `conversations` / `processed_messages` /
`bot_metrics` are the engine's state (multi-turn · idempotency · spend meter).

> **`customers` was REMOVED from this document (FIX-1, 2026-08-27).** The CP6 decision (2026-08-10)
> dropped it — the returning-customer greeting uses `conversations.found` + a session-gap instead. A
> repo-wide scan of all three workflow exports finds **zero** references to a `customers` table, so
> documenting it was describing a table the system never touches. The empty table is left in the
> Airtable base (deleting data is irreversible and it breaks nothing); it is simply not part of the
> data model.

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

## `bot_metrics` (CP5b spend-cap rolling counter — NOT PII)
| Field | Type | Notes |
|---|---|---|
| period_key | text | PK-ish — UTC period bucket, e.g. `2026-08` (month). Matches `Spend Gate`'s granularity; `Read Spend` filters on it, `Record LLM Spend` upserts on it. |
| cost_usd | number (precision 6) | accumulated estimated LLM cost for the period = Σ(tokens × `bot.llmPricePer1kTokensIn/Out`). Read BEFORE the LLM (Spend Gate), incremented AFTER a successful call. Over `bot.llmCostCapUsd` → deterministic handoff, no LLM (CP5b-2). |
| updated_at | datetime | UTC — last increment. |

**Not PII** — a monthly spend total only. Read-fail/write-fail → fail-OPEN (LLM still runs) + a `spend_meter_unavailable` owner alert. TOCTOU across concurrent turns is accepted at this tier (a soft brake, not an atomic ledger).

## `conversations` (multi-turn slot-filling state)
| Field | Type | Notes |
|---|---|---|
| sender_key | text | PK — `"{channel}:{id}"` using the FULL channel name (matches the config channels enum), e.g. `whatsapp:+43…`, `instagram:12345` — namespaced so channels can never collide (PII) |
| stage | single-select | **9 values, verified against the live flow (FIX-1 2026-08-27):** `new` \| `collecting` \| `ready` \| `confirming` \| `booked` \| `cancel_confirming` \| `cancelled` \| `reschedule_confirming` \| `handoff`. While `handoff` the bot sends no auto-reply to this sender (decision log 2026-07-02) — and **nothing in the flow clears that lock**, so releasing it is an owner action (UX-ARCHITECTURE §9 K6, Phase 6). **`done` is NOT a stage** — it was in this table for months but no node ever writes it. Writers: `Slot Gate` (`collecting`/`ready`) · `Compute Availability` (`collecting`/`confirming`) · `Compute Reschedule Availability` (`reschedule_confirming`) · `Build Cancel-Confirm State` · `Build Cancelled State` · the booked/reschedule-done builders · `Mark Handoff` + 14 error builders. |
| slot_service | text | nullable |
| slot_date | text | nullable |
| slot_time | text | nullable |
| last_updated | datetime | UTC — session-gap calculation (`Build Reply Payload`) and the 30-day PII-scrub cutoff. **It does not expire the row** (no job deletes `conversations` rows). |
| turn_count | number | default 0 — +1 on every inbound message; compared with config `bot.maxTurnsPerConversation` for the max-turns guard (CP3) |
| last_intent | single line text | nullable — last classified intent (debug/analysis) (CP3) |
| recent_messages | long text (multilineText) | **PII (message content)** — rolling **last-5** inbound customer message texts, newline-joined, each truncated to 80 chars (CP5a Step 7). Written every turn by `Save State`/`Save State (Post-Write)`, read by `Build Owner Alert` for handoff context so the owner sees what the customer said. **TTL = 30 days** — the daily purge workflow's second branch (`Compute PII Cutoff` → `Find Stale Conversations` → `Scrub Recent Messages`, FIX-1) clears this column on rows whose `last_updated` is older than 30 days. **Never export/screenshot unsanitized**; `/sanitize` + `security-auditor` scrub it like any PII column. |
| **gcal_event_id** | text | the booking's calendar event id, carried into state so a post-write failure still leaves a breadcrumb a human can follow (was undocumented until FIX-1) |
| **cancel_target_id** | text | the Airtable record id of the booking a pending `yes` is bound to — this is what makes cancel/reschedule confirmation IDOR-safe (was undocumented until FIX-1) |
| **confirm_turn** | text | `turn_count + 1` at the moment the confirm question was asked → the confirm is honored only on the **immediate next turn** (confirm-TTL). Text, not number, to match how it is written (was undocumented until FIX-1) |
| **computed_reply** | long text | the single source of this turn's reply (Refactor #5); every reply-producing builder writes it, `Build Reply Payload` reads it, and an empty value is what raises the `reply_fallback` alert. May contain a customer name/service — treat as borderline PII (was undocumented until FIX-1) |
| **last_alert_class** | single line text | **FIX-1 / UX-ARCHITECTURE §9 K1** — the class of the last owner-alert **delivered** for this conversation (one of the 19 classes). Written best-effort by `Record Alert Class` on the alert branch, never on the reply path (D-c invariant). Before this, every residue flag was ephemeral: once the Telegram message scrolled past, nothing in Airtable said *why* a conversation was stuck. |
| **last_alert_at** | datetime | UTC — when that alert was delivered. |

> **Honest limit on the two alert fields:** `Build Owner Alert` returns `[]` when an alert is
> throttled (30 min per class+sender), so these fields record the last **delivered** alert, not the
> last **occurring** one. They are also a *last* value, not a history — a second class overwrites the
> first. Alert history / full transcript was deliberately deferred (§9 K1).

> ### PII expiry — what is and is NOT solved (FIX-1)
> The 30-day scrub covers **message content** (`recent_messages`). It does **NOT** make the row
> anonymous: **`sender_key` contains a phone number on the whatsapp channel and stays for the row's
> lifetime**, because the row is deliberately kept rather than deleted. Deleting the row would
> silently release a `stage='handoff'` lock and drop `cancel_target_id`/`confirm_turn`, so row
> deletion is a **separate** decision (UX-ARCHITECTURE §9 K2). Do not describe this as "PII TTL
> solved" — it is message-content expiry only.

> **Owner-alert context (CP5a):** `recent_messages` is why `Build Owner Alert` can include recent
> customer lines. Design decision D-a (rolling last-N in `conversations`, **no separate `messages`
> table**) — see [ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md) §5.

> **CP3 prerequisite:** `turn_count` and `last_intent` must also be created as columns in the real Airtable
> `conversations` table (Yigitcan) before the CP3 flow can write them.

## `processed_messages` (idempotency / dedupe)
| Field | Type | Notes |
|---|---|---|
| message_id | text | the dedupe key — provider message id (Zernio `platformMessageId`; widget client UUID) |
| sender_key | text | `"{channel}:{id}"` (PII) |
| channel | text | whatsapp \| widget \| instagram |
| created_at | text | ISO-8601 UTC string, written AFTER Save State succeeds |

**TTL purge (CP5e):** a separate ACTIVE daily workflow `Salon Booking Bot — Processed Purge` deletes rows with
`created_at` older than 30 days (dedupe only needs to outlive the provider retry window = hours; 30d is amply
safe) so the store stays bounded. `created_at` is text, but ISO-8601 sorts lexicographically = chronologically,
so the purge filter is a plain `{created_at} < cutoff`.

**Booking integrity:** `processed_messages` guards idempotency; `appointments` + Google Calendar guarded by
write-then-verify (no atomic lock). See [../.claude/rules/booking-integrity.md](../.claude/rules/booking-integrity.md).

<TODO (Phase 3): confirm exact field types against the real Airtable base>
