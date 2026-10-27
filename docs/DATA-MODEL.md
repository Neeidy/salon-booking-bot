# Data model — Postgres (`salon` schema)

> **Role of this file:** the human-readable map of the bot's store. **Since the cutover of 2026-10-24 the store is
> self-hosted Postgres** (`docs/MIGRATION-PLAN.md` §3t, Round 3c). The DDL itself is canonical and lives in
> [`../db/schema/`](../db/schema/): `001_init.sql` (tables), `002_roles.sql` (roles and grants),
> `003_revoke_large_object_writes.sql` (the large-object revoke). If this page and those files disagree, the files
> win and this page is wrong. Machine-checkable message contracts live in [`../schemas/`](../schemas/).
>
> **Airtable is READ-ONLY until D6c** (the Airtable shutdown after a 7-day soak, MIGRATION-PLAN §7). The parked
> original workflows still point at it as the rollback path; no active workflow holds an Airtable node. Its
> description is kept at the bottom of this page as history, not as the current model.

Five tables. `leads` / `appointments` are the CRM; `conversations` / `processed_messages` / `bot_metrics` are the
engine's state (multi-turn · idempotency · spend meter).

**Shared shapes (001_init.sql):**
- **Every `id` is `text PRIMARY KEY DEFAULT salon.gen_rec_id()`** — an Airtable-shaped record id, `'rec'` + 14
  characters from `[A-Za-z0-9]`, drawn from a v4 UUID's bytes (ruling Q3: the owner path's allow-list, the drill
  fixtures and the export masks key on that shape, so keeping it changed none of them). Uniqueness is the primary
  key's job.
- **Timestamps are `timestamptz`**, `NOT NULL` where the row must have one. An empty string can no longer be stored:
  a write of `''` fails the cast loudly instead of becoming a row that sorts before everything (the old
  `processed_messages.created_at` was text).
- **Values the flow writes as text stay text** (`slot_date`, `slot_time`, `confirm_turn`, `last_intent`…): the
  migration changed the store, not the values the nodes produce.
- `salon.at_ts(timestamptz)` renders a timestamp in Airtable's text form (`YYYY-MM-DDTHH:MM:SS.mmmZ`), so every
  read returns the exact shape the downstream nodes were written against.
- The workflows reach the tables only through Postgres nodes running parameterised SQL (`$1…$N` via
  `queryReplacement`, never an expression in the SQL text); `scripts/check-sql-params.py` enforces it over every
  committed export.

> **`customers` is NOT part of the model (FIX-1, 2026-08-27).** The CP6 decision (2026-08-10) dropped it — the
> returning-customer greeting uses `found` (computed in `Merge State`) + a session-gap instead. It was never created
> in Postgres; the empty table still sits in the read-only Airtable base and is part of D6c's export.

## `leads`
| Column | Type | Constraint / notes |
|---|---|---|
| id | text | PK, `gen_rec_id()` |
| lead_no | bigint | `GENERATED ALWAYS AS IDENTITY UNIQUE` — the lead autonumber; `001_init.sql`'s comment says the dashboard shows it as `fields.id`, which described the Airtable-era dashboard: the Postgres dashboard's leads read (`web/dashboard/lib/store.ts`) does not select it |
| name | text | customer name (PII) |
| phone | text | E.164 (PII) |
| source | text | `CHECK (source IN ('whatsapp', 'widget', 'instagram'))` |
| message | text | first message |
| status | text | `NOT NULL DEFAULT 'new'`, `CHECK (status IN ('new', 'contacted', 'converted'))` |
| created_at | timestamptz | `NOT NULL DEFAULT now()` |

**TTL:** the Purge workflow's leads branch deletes leads older than `leadsRetentionDays`, and FAILS CLOSED when that
key is absent (deletes nothing and alerts) — `Compute Leads Cutoff` in the Purge export (`n8n/workflow.purge.sanitized.json`).

## `appointments` (the CRM mirror of Google Calendar)
| Column | Type | Constraint / notes |
|---|---|---|
| id | text | PK, `gen_rec_id()` |
| sender_key | text | `NOT NULL` — `"{channel}:{id}"`, the booking's owner; the IDOR-safe cancel/reschedule lookup key (never a customer-supplied id) (PII) |
| service | text | service name, from client.config services |
| start_utc | timestamptz | `NOT NULL` — **UTC**, displayed in the shop tz |
| end_utc | timestamptz | `NOT NULL` |
| gcal_event_id | text | `NOT NULL`, **`UNIQUE`** (`appointments_gcal_event_id_key`) — `Write Appointment`'s upsert key (`ON CONFLICT (gcal_event_id) DO UPDATE`). Re-verify · cancel/reschedule delete. ⚠ It reverses to the `sender_key` (`security-secrets.md`) — treat a full one like a full `sender_key` |
| calendar_id | text | the GCal calendar the event lives on, stored at booking (CP3/Codex#8) — cancel/reschedule delete uses the STORED calendar+event pair, so a later config-calendar change can't delete on the wrong calendar |
| channel | text | origin channel — whatsapp \| widget \| instagram (no CHECK) |
| customer_name | text | nullable (PII) |
| status | text | `NOT NULL`, `CHECK (status IN ('booked', 'cancelled'))` |
| **reminded** | boolean | `NOT NULL DEFAULT false` — **CONTROL**, the reminder dedupe flag (CP5). Reminders selects the not-reminded rows; Stamp sets `true`; **reschedule sets `false`** so a moved appointment re-reminds. *(It became a boolean on Airtable, where native n8n could not clear a dateTime; the column kept that shape.)* |
| reminder_sent | timestamptz | **INFO** (nullable) — when the last reminder fired. NOT the dedupe key (`reminded` is); reschedule does **not** touch it, so it honestly records the last send (CP5). |
| created_at | timestamptz | `NOT NULL DEFAULT now()` |

Indexes: `(sender_key, status)` and `(status, start_utc)`.

> **Availability source of truth = Google Calendar** (owner "busy" blocks live in GCal too); `appointments` mirrors
> it. Booking write order: **GCal first, then Postgres** — and the Calendar write sits outside any Postgres
> transaction, so there is no atomic lock across the two. See
> [../.claude/rules/booking-integrity.md](../.claude/rules/booking-integrity.md).

## `bot_metrics` (the LLM spend meter — NOT PII)
| Column | Type | Constraint / notes |
|---|---|---|
| id | text | PK, `gen_rec_id()` |
| period_key | text | `NOT NULL`, **`UNIQUE`** — the UTC month, e.g. `2026-10`. `Read Spend` filters on it; `Record LLM Spend` upserts on it (`ON CONFLICT (period_key) DO UPDATE`) |
| cost_usd | numeric(12,6) | `NOT NULL DEFAULT 0` — accumulated estimated LLM cost for the period = Σ(tokens × `bot.llmPricePer1kTokensIn/Out`). Read BEFORE the LLM (`Spend Gate`), written AFTER a successful call. Over `bot.llmCostCapUsd` → deterministic handoff, no LLM (CP5b-2) |
| updated_at | timestamptz | nullable — last increment |
| created_at | timestamptz | `NOT NULL DEFAULT now()` |

Read-fail/write-fail → fail-OPEN (the LLM still runs) + a `spend_meter_unavailable` owner alert. TOCTOU across
concurrent turns is accepted at this tier (a soft brake, not an atomic ledger): the upsert writes the total the
turn computed, it does not add to the stored one. The month's row is the real spend meter since the cutover (kept
at Round 3c's cleanup by ruling).

## `conversations` (multi-turn slot-filling state, one row per sender)
| Column | Type | Constraint / notes |
|---|---|---|
| id | text | PK, `gen_rec_id()` |
| sender_key | text | `NOT NULL`, **`UNIQUE`** (`conversations_sender_key_key`) — `Save State`'s upsert key (`ON CONFLICT (sender_key) DO UPDATE`). `"{channel}:{id}"` using the FULL channel name, e.g. `whatsapp:+43…` — namespaced so channels can never collide (PII; on the widget it is a bearer credential, `security-secrets.md`) |
| stage | text | `NOT NULL DEFAULT 'new'`, **`CHECK` on the nine values Main can write:** `new` \| `collecting` \| `ready` \| `confirming` \| `booked` \| `cancel_confirming` \| `cancelled` \| `reschedule_confirming` \| `handoff`. A value outside the list is now a VISIBLE error, where Airtable's single-select stored it silently. While `handoff` the bot sends no auto-reply to this sender (decision log 2026-07-02) — and **nothing in the bot's flow clears that lock**; releasing it is the owner action D11 (the dashboard's release → Owner Actions). ⚠ **UNLOCKING MEANS CLEARING `stage` AND `last_intent` — clearing `stage` alone leaves a half-armed conversation** (`code-reviewer`, 2026-09-09f). Two escalation ladders read `last_intent` as a carried-in strike: `Repeat Uncertain?` (`'clarify'`) and `Repeat Extraction Failure?` (`'invalid'`). `Mark Handoff` writes `stage='handoff'` while `Validate Intent` has already written `last_intent='invalid'`, so a `stage`-only unlock leaves `'invalid'` standing and the first extraction failure on the next turn that WRITES STATE escalates straight back to a handoff. (Any valid turn in between rewrites `last_intent` and clears the strike.) The release sets `last_intent` empty in the same write (Round 3c, A4: the row went to `new` with an empty `last_intent`). **`done` is NOT a stage.** |
| slot_service | text | nullable |
| slot_date | text | nullable |
| slot_time | text | nullable |
| last_updated | timestamptz | `NOT NULL DEFAULT now()` — UTC; session-gap calculation (`Build Reply Payload`) and the 30-day PII-scrub cutoff. **It does not expire the row** (no job deletes `conversations` rows). |
| turn_count | integer | `NOT NULL DEFAULT 0` — +1 on every inbound message; compared with config `bot.maxTurnsPerConversation` for the max-turns guard (CP3) |
| last_intent | text | last classified intent. ⚠ **NOT a debug field** — two escalation ladders READ it as a carried-in strike (see `stage`). It also carries two non-enum control values (`'invalid'`, `'clarify'`) that are not intents at all. |
| recent_messages | text | **PII (message content)** — rolling **last-5** inbound customer message texts, newline-joined, each truncated to 80 chars (CP5a Step 7). Written every turn by `Save State`/`Save State (Post-Write)`, read by `Build Owner Alert` for handoff context. **TTL = 30 days** — the Purge workflow's second branch (`Compute PII Cutoff` → `Find Stale Conversations` → `Scrub Recent Messages`) clears it on rows whose `last_updated` is older than 30 days. **Never export/screenshot unsanitized.** |
| gcal_event_id | text | the booking's calendar event id, carried into state so a post-write failure still leaves a breadcrumb a human can follow |
| cancel_target_id | text | the `appointments.id` a pending `yes` is bound to — this is what makes cancel/reschedule confirmation IDOR-safe. **Deliberately NO foreign key:** the flow writes it empty and can leave it dangling, and `Validate Cancel Target` re-reads and refuses a bad one; an FK would have turned those writes into errors (001_init.sql) |
| confirm_turn | text | `turn_count + 1` at the moment the confirm question was asked → the confirm is honoured only on the **immediate next turn** (confirm-TTL). Text, to match how it is written |
| computed_reply | text | the single source of this turn's reply (Refactor #5); every reply-producing builder writes it, `Build Reply Payload` reads it, and an empty value raises the `reply_fallback` alert. May contain a customer name/service — treat as borderline PII |
| last_alert_class | text | the class of the last owner alert **actually delivered** for this conversation. Written by `Record Alert Class` **only after `Send Owner Alert (Telegram)` succeeds** (Codex #5): if delivery fails it stays EMPTY, because empty is the true statement. **Update by id, never upsert** (Codex #4: `UPDATE … WHERE id = $1` on the row `Find Conversation Row` found), so a client-controlled `sessionId` cannot mint a metadata-only junk row |
| last_alert_at | timestamptz | nullable — when that alert was delivered (same write, same condition) |
| **sender_masked** | text | **`GENERATED ALWAYS AS (…) STORED`** — never written by the flow. `whatsapp:` keys of 15+ characters → the first 12 characters + `…` + the last 2 (channel and country code kept, subscriber dropped); every other key → the first `MIN(16, length − 4)` characters + `…`, clamped at 0 with `GREATEST`, so at least four characters are always removed (an unclamped `left()` with a negative length would return almost the whole key). The dashboard re-masks on read as well; this column is the first line, not the only one |
| created_at | timestamptz | `NOT NULL DEFAULT now()` |

> **Honest limits on the two alert columns:** `Build Owner Alert` returns `[]` when an alert is throttled (30 min per
> class+sender), so they record the last **delivered** alert, not the last **occurring** one, and a second class
> overwrites the first. Front-gate alerts whose sender has no conversation row leave **no database trace at all** —
> by design, since the alternative was creating junk rows. On a session's FIRST turn `Find Conversation Row` runs
> before `Save State` has created the row, so that alert is not recorded either (PHASE-7-PLAN named item (4)).

> ### PII expiry — what is and is NOT solved (FIX-1)
> The 30-day scrub covers **message content** (`recent_messages`). It does **NOT** make the row anonymous:
> **`sender_key` contains a phone number on the whatsapp channel and stays for the row's lifetime**, because the row
> is deliberately kept rather than deleted. Deleting the row would silently release a `stage='handoff'` lock and drop
> `cancel_target_id`/`confirm_turn`, so row deletion is a **separate** decision (UX-ARCHITECTURE §9 K2). Do not
> describe this as "PII TTL solved" — it is message-content expiry only.

> **Owner-alert context (CP5a):** `recent_messages` is why `Build Owner Alert` can include recent customer lines.
> Design decision D-a (rolling last-N in `conversations`, **no separate `messages` table**) — see
> [ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md) §5.

## `processed_messages` (idempotency / dedupe)
| Column | Type | Constraint / notes |
|---|---|---|
| id | text | PK, `gen_rec_id()` |
| message_id | text | `NOT NULL`, **`UNIQUE`** (`processed_messages_message_id_key`) — the dedupe key, GLOBALLY unique (provider message id: Zernio `platformMessageId`; widget client UUID). `Check Processed` filters on it alone |
| sender_key | text | `"{channel}:{id}"` (PII) |
| channel | text | whatsapp \| widget \| instagram (no CHECK) |
| created_at | timestamptz | `NOT NULL DEFAULT now()` — written by `Check Processed`'s claim at the START of the turn (since 7-2 R3) |

Index: `(created_at)`, for the purge.

`Check Processed` CLAIMS the id with `INSERT … ON CONFLICT (message_id) DO NOTHING RETURNING` (7-2 Tur 2, ruling R-1a;
live since 7-2 R3): a returned row = this run owns the message, none = a duplicate. Because the UNIQUE makes the claim
atomic, CRT 1a's check-then-record race is closed; the cost is at-most-once (a run that dies after its claim is not
retried). `Record Processed` is gone. *(Until R3 the marker was written after `Save State` and the race stood — ruling Q5.)*

**TTL purge (CP5e):** the daily Purge workflow (`MIG COPY — Processed Purge`, renamed at D6c) deletes rows with
`created_at` older than 30 days (dedupe only needs to outlive the provider retry window = hours). The filter is a
`timestamptz` comparison now, not a text one.

**Booking integrity:** `processed_messages` guards idempotency; `appointments` + Google Calendar are guarded by
write-then-verify (no atomic lock). See [../.claude/rules/booking-integrity.md](../.claude/rules/booking-integrity.md).

## Roles and privileges (`002_roles.sql`, `003_revoke_large_object_writes.sql`)
| Role | Login | What it can do |
|---|---|---|
| `salon_owner` | NOLOGIN | owns the schema, the five tables and both functions (DDL lives here) |
| `salon_migrator` | LOGIN | member of `salon_owner` `WITH INHERIT FALSE, SET TRUE` — it must `SET ROLE salon_owner` to run DDL, so a later migration's objects are owned by `salon_owner` and fall under the default privileges |
| `salon_app` | LOGIN | **the n8n credential:** `SELECT, INSERT, UPDATE, DELETE` on the tables, `USAGE, SELECT` on the sequences, `EXECUTE` on both functions. No `CREATE`, not an owner, no `TRUNCATE` |
| `salon_ro` | LOGIN | **the dashboard and Claude's verification:** `SELECT` on the tables, `EXECUTE` on `at_ts` only. Claude holds only this role (ruling Q6) |

- `PUBLIC` loses everything: `ALL` on database `salon` (CONNECT and TEMPORARY included), `CONNECT, TEMPORARY` on
  `postgres` and `template1`, `ALL` on schemas `public` and `salon`, `EXECUTE` on the schema's functions.
- `ALTER DEFAULT PRIVILEGES FOR ROLE salon_owner` gives objects a later migration creates the same split, and revokes
  `EXECUTE` on future functions from `PUBLIC` GLOBALLY (a schema-scoped default can only add to the global one).
- Each login role has `search_path = salon`. Passwords never appear in the file: psql reads them with `\getenv` from
  the operator's environment, at least 24 characters and pairwise distinct, or the script aborts.
- **003** revokes `EXECUTE` from `PUBLIC` on the eight large-object functions that create, write, truncate or delete a
  large object (`lo_create`, `lo_creat`, `lo_from_bytea`, `lo_put`, `lowrite`, `lo_truncate`, `lo_truncate64`,
  `lo_unlink`), in database `salon` only, and checks inside the same transaction that `public`, `salon_app` and
  `salon_ro` can no longer execute any of them. Reason: `salon_ro` held SELECT only on the tables yet could create
  and write a persistent large object through PUBLIC's default grant (Codex CRT #10 F1). Applied by the operator and
  measured as `salon_ro` on 2026-10-24 (MIGRATION-PLAN §3t, Round 3c).

## Backups (`db/ops/pg-backup.sh`)
The nightly job dumps database `salon` from one consistent snapshot, records a sha256, and restores the dump whole
into a throwaway container with no network, comparing per-table row counts and ordered md5s for all five tables; any
failed step prints one line and exits non-zero. The restore check passed at D6a (operator run: restore equal on 107 rows; MIGRATION-PLAN §3 and §3t). ⚠ The verify
restore uses `--no-privileges`, and the script has no real-restore path: a real restore done the same way loses 002's
grants and 003's revoke — re-apply 002, then 003 (stated in 003's header). *The first nightly run against the live
Postgres store is a soak item (Round 3c) — not recorded here as passed.*

---

## Historical — the Airtable base (READ-ONLY until D6c)

Until the cutover of 2026-10-24 the same five tables lived in an Airtable base (plus the unused `customers`). The
field names and meanings above were carried over 1:1 — the migration's rule was that behaviour does not change — with
these differences, all from 001_init.sql:
- Airtable's autonumber `leads.id` is now `leads.lead_no`; `id` is the rec-shaped text key on every table.
- Single-selects (`stage`, `status`, `source`) are now `CHECK` constraints, so an unknown value fails loudly.
- `processed_messages.created_at` was a TEXT ISO-8601 string (the purge relied on lexicographic order = chronological
  order); it is `timestamptz` now, and `''` cannot be stored.
- `sender_masked` was an Airtable formula; it is a generated column now, with the one deliberate difference that a
  `whatsapp:` key shorter than 15 characters takes the generic branch (it errs toward hiding).
- The upsert keys (`sender_key`, `gcal_event_id`, `period_key`) and the dedupe key (`message_id`) are declared as
  `UNIQUE` constraints in the schema now.

The base is not deleted by D6c; it stays as an exported, unreferenced archive (MIGRATION-PLAN §7, step 5).
