/**
 * The ONLY module in this repo that holds the dashboard's database credential (salon_ro, from `PG*` env vars).
 * It replaced `airtable.ts` in D5 (MIGRATION-PLAN §3t, decision 1): ONE path, no store switch.
 *
 * CRT #10 is four claims, and this file is where three of them are either true or false:
 *   1. the credential never reaches a browser — it is read from process.env here and nowhere else, and the
 *                                                runtime guard below throws in a browser bundle;
 *   2. the credential is READ-ONLY              — `salon_ro` is granted SELECT only on the salon tables
 *                                                (db/schema/002_roles.sql). What THIS module adds is narrower, and
 *                                                it is a table-privilege check, not a proof: see `WRITE_CHECK` and
 *                                                the list of what it does not see, below;
 *   3. this is NOT a general proxy              — see below, it is the whole design of this file;
 *   4. no dashboard/PII code ships to Vercel    — that is `web/`'s two-app split, not this file.
 *
 * WHY IT IS NOT A PROXY, stated as a rule and not as an intention: **no exported function takes a table, a
 * filter, a column list, a sort or a record id from its caller.** There are exactly four reads, each one a
 * constant SQL string in `SQL` below, each with NO bound parameter: the only inputs are the clock, read by the
 * database itself. `lib/store.test.ts` CHECKS this from the file's own text, and a text check is not a proof: it
 * catches the spellings it looks for (a read that grows a parameter, a `.query(` that takes something other than
 * a module constant, a `$n` placeholder) and nothing else. Codex CRT #10 F4 wrote twelve mutants that turn this
 * module into a proxy and keep every test green (`p['query']`, `.query (`, code hidden between comment-looking
 * strings, an aliased export). A behaviour-based test, a mocked driver recording what is actually sent, is a
 * named Phase 7 item; until it exists, the rule above holds because the code is short enough to read.
 *
 * COLUMN SELECTION IS A SECURITY CONTROL, NOT AN OPTIMISATION (Yigitcan's addition E2). The rule is unchanged
 * from the Airtable version: **a field that is DISPLAYED is fetched; a field that is not displayed is not
 * fetched; and no PII crosses a client-component boundary.** ⚠ The middle clause is NOT met today: five non-PII
 * context columns are fetched and never drawn (appointments' `end_utc`, `reminder_sent`, `created_at`; leads'
 * `created_at`; the queue's `stage`), and an earlier version of this paragraph permitted that in the same breath
 * as stating the rule (Codex CRT #10 F7). Trimming them is a named Phase 7 item. Deliberately never selected, and asserted by
 * the test: `sender_key` (a BEARER credential on the widget lane), `gcal_event_id` (a hex ENCODING of the
 * sender key, `security-secrets.md`), `computed_reply`, `cancel_target_id`. The handoff queue reads
 * `sender_masked`, now a STORED generated column (db/schema/001_init.sql) computed by the corrected formula
 * the Airtable field carried (at least four characters always removed). `recent_messages` IS fetched, because
 * the queue shows it; what protects it is `maskFreeText` plus the SERVER-component boundary.
 * ⚠ `salon_ro` itself can read every column (Q16, splitting its column access, is in the final security pass);
 * the column lists here are the control, exactly as the field lists were with an Airtable PAT that could read
 * every field.
 *
 * THE SHAPE IS THE ONE THE PANELS WERE WRITTEN AGAINST: Airtable omitted empty fields, so every row is built
 * with `jsonb_strip_nulls` + `NULLIF(x, '')` + `CASE WHEN flag THEN true END`, the same rules the workflow
 * copies use, and handed on as `{ id, ...fields }`. Timestamps are ISO with milliseconds (`salon.at_ts`).
 * `cost_usd` is cast to float8. Inside `jsonb_build_object` a `numeric` already becomes a JSON number (spike S2, and
 * re-measured in D5: the same statement without the cast gave a number), so today the cast is a guard, not a fix:
 * `SystemHealth` tests `typeof === 'number'`, and a refactor that selected the column RAW would hand it a string
 * (S2: a raw `numeric` arrives as a string), and the panel would silently show no spend.
 */
import pg from 'pg';
import type { Appointment, Lead, HandoffRow, SpendRow } from './types.ts';

/** Server-only. A RUNTIME guard, the same shape `@salon/shared/config` carries and for the same reason. */
if (typeof globalThis === 'object' && 'window' in globalThis && 'document' in globalThis) {
  throw new Error(
    'web/dashboard/lib/store.ts was imported into a browser bundle. It holds the database credential. '
    + 'The build-time boundary is scripts/check-client-imports.cjs; this throw is the runtime half.',
  );
}

/** Rows per panel. One more is fetched so `truncated` can be told apart from "exactly this many". */
export const PAGE_ROWS = 100;

/**
 * THE FOUR READS. Constants, frozen, no `$n`: nothing a caller passes can reach a statement.
 * Each filter reads only the clock, in UTC, matching what the Airtable formulas did:
 *   appointments — from yesterday 00:00 UTC onwards, ascending, so the first hundred ARE the next hundred
 *                  (a 30-day ascending window once showed a busy shop the OLDEST hundred, all in the past);
 *   leads        — the last 90 days, newest first (a working list, not an archive);
 *   handoff      — every conversation at `stage = 'handoff'`, NOT date-filtered (a lock from July is still a
 *                  lock), newest first;
 *   spend        — this UTC month's bucket, the one `Spend Gate` reads.
 */
export const SQL = Object.freeze({
  appointments: `SELECT id, jsonb_strip_nulls(jsonb_build_object(
      'start_utc', salon.at_ts(start_utc), 'end_utc', salon.at_ts(end_utc), 'service', NULLIF(service, ''),
      'channel', NULLIF(channel, ''), 'status', NULLIF(status, ''), 'reminded', CASE WHEN reminded THEN true END,
      'reminder_sent', salon.at_ts(reminder_sent), 'created_at', salon.at_ts(created_at),
      'customer_name', NULLIF(customer_name, ''))) AS fields
    FROM salon.appointments
    WHERE start_utc > (((now() AT TIME ZONE 'UTC')::date - 1)::timestamp AT TIME ZONE 'UTC')
    ORDER BY start_utc ASC, id
    LIMIT ${PAGE_ROWS + 1}`,
  leads: `SELECT id, jsonb_strip_nulls(jsonb_build_object(
      'name', NULLIF(name, ''), 'phone', NULLIF(phone, ''), 'source', NULLIF(source, ''),
      'status', NULLIF(status, ''), 'created_at', salon.at_ts(created_at))) AS fields
    FROM salon.leads
    WHERE created_at > (((now() AT TIME ZONE 'UTC')::date - 90)::timestamp AT TIME ZONE 'UTC')
    ORDER BY created_at DESC, id
    LIMIT ${PAGE_ROWS + 1}`,
  handoff: `SELECT id, jsonb_strip_nulls(jsonb_build_object(
      'sender_masked', NULLIF(sender_masked, ''), 'stage', NULLIF(stage, ''),
      'last_alert_class', NULLIF(last_alert_class, ''), 'last_alert_at', salon.at_ts(last_alert_at),
      'last_intent', NULLIF(last_intent, ''), 'turn_count', turn_count, 'last_updated', salon.at_ts(last_updated),
      'recent_messages', NULLIF(recent_messages, ''))) AS fields
    FROM salon.conversations
    WHERE stage = 'handoff'
    ORDER BY last_updated DESC, id
    LIMIT ${PAGE_ROWS + 1}`,
  spend: `SELECT id, jsonb_strip_nulls(jsonb_build_object(
      'period_key', NULLIF(period_key, ''), 'cost_usd', cost_usd::float8, 'updated_at', salon.at_ts(updated_at))) AS fields
    FROM salon.bot_metrics
    WHERE period_key = to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM')
    ORDER BY id
    LIMIT ${PAGE_ROWS + 1}`,
});

/**
 * WHAT THIS IS, exactly: a TABLE-privilege check. It asks `has_table_privilege` for INSERT, UPDATE, DELETE and
 * TRUNCATE on the five salon tables, for `current_user`, the role of the ONE pooled connection that happens to
 * run it. `has_table_privilege` counts privileges held directly, through PUBLIC, through ownership, and through
 * membership in a role whose privileges are INHERITED; a superuser answers true everywhere (Codex's inherited-
 * grant and superuser controls both came back non-zero). Any true answer refuses every read. It exists because
 * a configuration can break claim 2 silently: a `PGUSER` pointed at the app role reads exactly the same rows,
 * and this check catches that case.
 *
 * WHAT IT DOES NOT SEE (Codex CRT #10 F1, most of it measured in a scratch database built from the two schema
 * files; the rest follows from what the function asks), so a zero here does NOT mean the credential cannot write:
 *   - column-level grants (`GRANT UPDATE (name) ON salon.leads` leaves every table-level answer false);
 *   - roles the login can `SET ROLE` into without inheriting them (membership with INHERIT FALSE);
 *   - functions: the built-in large-object writers (`lo_create`, `lo_from_bytea` among them), which PUBLIC may
 *     execute by default, and any SECURITY DEFINER function that writes on its owner's behalf;
 *   - sequences (`setval`, `nextval`), tables outside these five, and every other schema;
 *   - schema CREATE and database TEMPORARY;
 *   - ownership whose DML was revoked (an owner can grant it straight back);
 *   - BYPASSRLS (it grants no DML itself, but it voids any row policy).
 * The large-object writers are closed at the DATABASE, not here: db/schema/003_revoke_large_object_writes.sql
 * revokes their EXECUTE from PUBLIC, the operator applies it, and its before/after measurement belongs in
 * docs/MIGRATION-PLAN.md §3t. This SQL is deliberately NOT broadened now (ruling 2026-10-24).
 *
 * ⚠ It runs ONCE per process and a pass is cached (`readOnly` below): a grant made after the first render is
 * never re-asked (Codex F2). Deferred to the final security pass.
 */
const WRITE_CHECK = `SELECT current_user AS role, count(*)::int AS writable
    FROM unnest(ARRAY['appointments', 'bot_metrics', 'conversations', 'leads', 'processed_messages']) t,
         unnest(ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) p
    WHERE has_table_privilege(current_user, 'salon.' || t, p)`;

export class StoreError extends Error {
  // Written out rather than as TypeScript parameter properties: Node's strip-only type removal does NOT
  // support them, so the shorthand would make this module unrunnable by `node --test`.
  readonly table: string;
  /** The Postgres SQLSTATE or the driver's error code (`ECONNREFUSED`); never the message, which can carry a host. */
  readonly code: string;
  /** The database is busy (too many connections, a statement timeout): the bot shares the cluster and has priority. */
  readonly busy: boolean;
  constructor(table: string, code: string, busy: boolean) {
    super(`store ${table}: ${code}`);
    this.name = 'StoreError';
    this.table = table;
    this.code = code;
    this.busy = busy;
  }
}

/**
 * A configuration fault, distinct from a transport fault ON PURPOSE (`code-reviewer` #6, 2026-09-12): it is
 * raised before anything is read, so "the data service did not answer" would blame a service that was never
 * asked. The page only ever sees `e.name`, so the NAME is the whole signal.
 */
export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

/** Too many connections (53300) or a statement timeout (57014): the cluster is busy, not broken. */
const BUSY = new Set(['53300', '57014']);

let pool: pg.Pool | null = null;
let readOnly: Promise<void> | null = null;

function getPool(): pg.Pool {
  // Fail loudly and EARLY. A dashboard that renders empty panels because a variable is missing looks exactly
  // like a dashboard whose shop has no bookings, and that is the worst failure available here.
  const missing = ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD'].filter((k) => !process.env[k]);
  if (missing.length) {
    throw new ConfigError(
      `${missing.join(', ')} must be set (web/dashboard/.env.local). `
      + 'Refusing to render: an unconfigured dashboard and an empty one look identical.',
    );
  }
  // `pg` reads PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD itself; nothing here copies the password.
  // max 4: one connection per read of a render, and no more, because the bot's role shares the cluster.
  if (!pool) {
    pool = new pg.Pool({ max: 4, statement_timeout: 10_000, connectionTimeoutMillis: 10_000, idleTimeoutMillis: 30_000 });
    // An IDLE pooled connection that fails (a database restart, a dropped link) makes pg emit 'error' on the
    // pool, outside every read's try/catch. With no listener that is an unhandled 'error' event and it takes the
    // dashboard process down (Codex CRT #10 F3). pg has already discarded that client, so the next read opens a
    // fresh one; all that is left to do here is make the failure visible. Only the CLASS is logged, never the
    // message or the object: a pg/libpq message can carry the host, the user or the database name.
    // Attached once, at construction: `getPool` runs on every read.
    pool.on('error', (e) => {
      console.error(`store: an idle database connection failed (${errorClass(e)}); pg discarded it, the next read reconnects`);
    });
  }
  return pool;
}

/** A SQLSTATE (`57P01`) or a Node errno code (`ECONNRESET`), else 'unknown'. Safe to log: a code, never text. */
function errorClass(e: unknown): string {
  const code = (e && typeof e === 'object' && 'code' in e) ? e.code : undefined;
  return typeof code === 'string' && (/^[0-9A-Z]{5}$/.test(code) || /^E[A-Z0-9_]+$/.test(code)) ? code : 'unknown';
}

function storeError(table: string, e: unknown): StoreError {
  const code = (e && typeof e === 'object' && 'code' in e && typeof e.code === 'string') ? e.code : 'unknown';
  return new StoreError(table, code, BUSY.has(code));
}

function ensureReadOnly(p: pg.Pool): Promise<void> {
  readOnly ??= p.query(WRITE_CHECK).then(
    (r) => {
      const { role, writable } = r.rows[0] as { role: string; writable: number };
      if (writable !== 0) {
        throw new ConfigError(
          `The dashboard's database role (${role}) can write ${writable} table privilege(s). It must be read-only `
          + '(salon_ro): refusing to read.',
        );
      }
    },
    (e) => { throw storeError('privilege-check', e); },
  );
  // A failed check is not cached: the next render asks again (a database that was down may be back).
  readOnly.catch(() => { readOnly = null; });
  return readOnly;
}

/**
 * A tripwire against one render fanning out: four reads per page, counted here. It is per-PROCESS, not
 * per-render (two concurrent renders each reset it), so it catches the mistake it was written for and cannot
 * see concurrency; the pool's `max: 4` is the bound on what reaches the database at once. ⚠ It used to guard
 * Airtable's 5 requests/second, a base-wide limit shared with the bot; on Postgres the shared resource is the
 * cluster's connections, which the pool bounds.
 */
let readsThisRender = 0;
export function resetBudget(): void { readsThisRender = 0; }
export function budgetUsed(): number { return readsThisRender; }
export const BUDGET_PER_PAGE = 4;

export interface Page<T> {
  rows: T[];
  /**
   * TRUE when there are more rows than the panel shows. Not a nicety: a dashboard that shows 100 of 340
   * appointments with no mark is worse than one that shows none. One extra row is fetched to know it.
   */
  truncated: boolean;
}

/** `{ id, fields }` rows → the panels' flat rows, and the truncation flag. Pure; tested on its own. */
export function toPage<T>(rows: Array<{ id: string; fields: Record<string, unknown> | null }>): Page<T> {
  return {
    rows: rows.slice(0, PAGE_ROWS).map((r) => ({ ...(r.fields ?? {}), id: r.id })) as T[],
    truncated: rows.length > PAGE_ROWS,
  };
}

async function read<T>(table: keyof typeof SQL): Promise<Page<T>> {
  const p = getPool();
  if (readsThisRender >= BUDGET_PER_PAGE) {
    throw new Error(`Read budget exceeded: ${readsThisRender + 1} reads in one render, cap is ${BUDGET_PER_PAGE}.`);
  }
  readsThisRender++;
  await ensureReadOnly(p);
  try {
    const r = await p.query(SQL[table]);
    return toPage<T>(r.rows);
  } catch (e) {
    throw storeError(table, e);
  }
}

export async function readAppointments(): Promise<Page<Appointment>> { return read<Appointment>('appointments'); }
export async function readLeads(): Promise<Page<Lead>> { return read<Lead>('leads'); }
export async function readHandoffQueue(): Promise<Page<HandoffRow>> { return read<HandoffRow>('handoff'); }
export async function readSpend(): Promise<Page<SpendRow>> { return read<SpendRow>('spend'); }
