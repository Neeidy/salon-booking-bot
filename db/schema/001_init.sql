-- 001_init.sql — the bot's data store on Postgres (migration phase, docs/MIGRATION-PLAN.md §3d).
--
-- Applied ONCE, by the operator, as the bootstrap superuser, inside the Postgres container, with the file
-- on STDIN (no secret appears anywhere in this file, and nothing here is passed on a command line).
-- 002_roles.sql runs after it, creates the roles and hands ownership to salon_owner.
--
-- NO BEGIN/COMMIT here, on purpose: the runner wraps BOTH files in ONE transaction. First as a dry run
-- that ends in ROLLBACK (it proves every statement, CREATE ROLE included, which is transactional in
-- Postgres), then for real with COMMIT. A failure at any point leaves nothing behind.
--
-- Contract notes (why the types look the way they do):
-- · Every row has an Airtable-shaped record id: 'rec' + 14 [A-Za-z0-9] (ruling Q3). The owner path's
--   allow-list, the drill fixtures and the export masks all key on that shape, so keeping it means none of
--   them change. Uniqueness is the PRIMARY KEY's job; the generator only has to be unpredictable enough.
-- · Timestamps are timestamptz NOT NULL: a text column is how the "blank sorts first" defect existed
--   (processed_messages.created_at was TEXT); '' can no longer be stored, and a write of '' fails the cast
--   loudly instead of becoming a row that sorts before everything.
-- · Columns the flow writes as text (slot_date, slot_time, confirm_turn, last_intent…) stay text: the swap
--   changes the store, not the values the nodes produce (the migration's rule: behaviour does not change).

\set ON_ERROR_STOP on

CREATE SCHEMA salon;

-- 'rec' + 14 characters from [A-Za-z0-9], from the bytes of a v4 UUID (122 random bits; core since PG13, no
-- extension). get_byte % 62 carries a negligible bias; an id is a key, not a secret.
CREATE FUNCTION salon.gen_rec_id() RETURNS text
LANGUAGE sql VOLATILE PARALLEL SAFE AS $$
  SELECT 'rec' || string_agg(
           substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
                  (get_byte(b, i) % 62) + 1, 1), '' ORDER BY i)
  FROM (SELECT uuid_send(gen_random_uuid()) AS b) s, generate_series(0, 13) AS i
$$;

-- Airtable's timestamp text form ("2026-10-19T18:23:51.000Z"), so a read can return the exact shape the
-- downstream nodes were written against (§3b).
CREATE FUNCTION salon.at_ts(timestamptz) RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE AS $$                -- STABLE, like the to_char it wraps
  SELECT to_char($1 AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
$$;

-- conversations — multi-turn state, one row per sender.
CREATE TABLE salon.conversations (
  id               text PRIMARY KEY DEFAULT salon.gen_rec_id(),
  sender_key       text NOT NULL,
  -- The nine values Main can WRITE, measured from the committed export 2026-10-19 (executable nodes only):
  -- literal writes (booked, cancel_confirming, cancelled, handoff, new), assignments (confirming,
  -- reschedule_confirming) and Slot Gate's ternary (collecting, ready). Owner Actions writes only 'new'.
  -- A value outside this list is now a VISIBLE error, where Airtable's single-select stored it silently.
  stage            text NOT NULL DEFAULT 'new' CHECK (stage IN (
                     'new', 'collecting', 'ready', 'confirming', 'booked',
                     'cancel_confirming', 'cancelled', 'reschedule_confirming', 'handoff')),
  slot_service     text,
  slot_date        text,
  slot_time        text,
  last_updated     timestamptz NOT NULL DEFAULT now(),
  turn_count       integer NOT NULL DEFAULT 0,
  last_intent      text,
  recent_messages  text,            -- PII (message content); scrubbed by the purge after 30 days
  gcal_event_id    text,
  -- The appointment record id a pending "yes" is bound to. Deliberately NO foreign key: the flow writes it
  -- empty and can leave it dangling, and Validate Cancel Target re-reads and refuses a bad one. An FK would
  -- turn those writes into errors — a behaviour change (§3d).
  cancel_target_id text,
  confirm_turn     text,
  computed_reply   text,
  last_alert_class text,
  last_alert_at    timestamptz,
  -- The FIXED Airtable formula's behaviour (ROADMAP: two defects measured over 592 rows, both fixed):
  --   whatsapp:…  → first 12 chars + "…" + last 2   (keeps the channel + country code, drops the subscriber)
  --   anything else → first MIN(16, LEN-4) chars + "…"  (at least four characters are always removed)
  -- One deliberate difference: a whatsapp key SHORTER than 15 characters takes the generic branch. The
  -- Airtable formula returned such a key whole (12 + 2 ≥ its length); no real E.164 key is that short, so
  -- the change only matters for malformed keys, and it errs toward hiding.
  -- GREATEST(…, 0) is Postgres-specific: left(s, n) with a NEGATIVE n returns all but the last |n|
  -- characters, so an unclamped very short key would come back almost whole — the very defect the formula
  -- was fixed for. The dashboard re-masks on read as well; this column is the first line, not the only one.
  sender_masked    text GENERATED ALWAYS AS (
                     CASE WHEN left(sender_key, 9) = 'whatsapp:' AND length(sender_key) >= 15
                          THEN left(sender_key, 12) || '…' || right(sender_key, 2)
                          ELSE left(sender_key, GREATEST(LEAST(16, length(sender_key) - 4), 0)) || '…'
                     END) STORED,
  created_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT conversations_sender_key_key UNIQUE (sender_key)   -- = Save State's upsert key
);

-- appointments — the CRM mirror of Google Calendar (GCal stays the availability source of truth).
CREATE TABLE salon.appointments (
  id             text PRIMARY KEY DEFAULT salon.gen_rec_id(),
  sender_key     text NOT NULL,
  service        text,
  start_utc      timestamptz NOT NULL,
  end_utc        timestamptz NOT NULL,
  gcal_event_id  text NOT NULL,
  calendar_id    text,
  channel        text,
  customer_name  text,             -- PII
  status         text NOT NULL CHECK (status IN ('booked', 'cancelled')),
  reminded       boolean NOT NULL DEFAULT false,   -- the reminder dedupe flag (reschedule re-arms it)
  reminder_sent  timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT appointments_gcal_event_id_key UNIQUE (gcal_event_id)   -- = Write Appointment's upsert key
);
CREATE INDEX appointments_sender_status_idx ON salon.appointments (sender_key, status);
CREATE INDEX appointments_status_start_idx  ON salon.appointments (status, start_utc);

-- leads — captured contacts. `lead_no` is the autonumber the dashboard shows as fields.id (and, through
-- its `{ id: r.id, ...r.fields }` spread, as the row id — kept as-is, §3b).
CREATE TABLE salon.leads (
  id          text PRIMARY KEY DEFAULT salon.gen_rec_id(),
  lead_no     bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
  name        text,                -- PII
  phone       text,                -- PII
  source      text CHECK (source IN ('whatsapp', 'widget', 'instagram')),
  message     text,
  status      text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'converted')),
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- processed_messages — idempotency. message_id is GLOBALLY unique. Since 7-2 R3 (ruling R-1a) Check Processed
-- CLAIMS the id with INSERT … ON CONFLICT (message_id) DO NOTHING RETURNING at the start of a turn, and this
-- UNIQUE is what makes that claim atomic: CRT 1a's check-then-record race is closed (at-most-once). Until R3 a
-- Record Processed marker was written at the end of the turn and the race stood (ruling Q5). Comment only.
CREATE TABLE salon.processed_messages (
  id          text PRIMARY KEY DEFAULT salon.gen_rec_id(),
  message_id  text NOT NULL,
  sender_key  text,
  channel     text,
  created_at  timestamptz NOT NULL DEFAULT now(),   -- was TEXT on Airtable: the blank-timestamp class
  CONSTRAINT processed_messages_message_id_key UNIQUE (message_id)
);
CREATE INDEX processed_messages_created_idx ON salon.processed_messages (created_at);

-- bot_metrics — the LLM spend meter (not PII). One row per period.
CREATE TABLE salon.bot_metrics (
  id          text PRIMARY KEY DEFAULT salon.gen_rec_id(),
  period_key  text NOT NULL,
  cost_usd    numeric(12,6) NOT NULL DEFAULT 0,
  updated_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT bot_metrics_period_key_key UNIQUE (period_key)   -- = Record LLM Spend's upsert key
);
