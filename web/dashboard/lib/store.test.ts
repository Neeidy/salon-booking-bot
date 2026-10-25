/**
 * CRT #10's offline half for the Postgres read path (D5, MIGRATION-PLAN §3t). What these check WITHOUT a
 * database:
 *   - the not-a-proxy rule, by reading `store.ts`'s own TEXT. A spelling check, and not a proof: Codex CRT #10 F4
 *     kept all of these green with twelve proxy mutants. The behaviour check that turns all twelve red is
 *     `lib/store.behaviour.test.ts`; these stay because they fail faster and catch a declared-but-unused
 *     parameter, which changes no behaviour and so cannot show up there;
 *   - E2: no statement selects a column E2 keeps out; each projection equals its DISPLAYED list below; and every
 *     projected column has a reader in components/, app/ or lib/ (Codex F7, trimmed in Phase 7 F2);
 *   - F12: the handoff queue's ORDER BY is the panel's triage order, checked against `alertState`'s own functions
 *     through a transliteration of the SQL (what that cannot prove is stated at the test);
 *   - that truncation and configuration faults surface; and, through the REAL pg pool with a fake connection,
 *     that an idle-connection error neither kills the process nor leaks its message.
 * The live half (the queries on seeded rows, the read-only role refusing a write, the ORDER BY run for real) is a
 * later window's.
 *
 * Run: node --test lib/store.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { EventEmitter } from 'node:events';
import { inspect } from 'node:util';
import pg from 'pg';
import * as store from './store.ts';
import { alertState, triageRank, triageCompare, STALE_AFTER_MINUTES } from './alertState.ts';

const SRC = readFileSync(new URL('./store.ts', import.meta.url), 'utf8');
// The source without comments, so a word in a comment cannot satisfy or trip a check.
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

const FORBIDDEN = ['sender_key', 'gcal_event_id', 'computed_reply', 'cancel_target_id', 'calendar_id', 'confirm_turn'];
const DISPLAYED = {
  appointments: ['start_utc', 'service', 'channel', 'status', 'reminded', 'customer_name'],
  leads: ['name', 'phone', 'source', 'status'],
  handoff: ['sender_masked', 'last_alert_class', 'last_alert_at', 'last_intent', 'turn_count', 'last_updated', 'recent_messages'],
  spend: ['period_key', 'cost_usd', 'updated_at'],
};
/** Codex CRT #10 F7: fetched, never drawn, removed in Phase 7 F2. Re-adding one must fail. */
const TRIMMED = ['end_utc', 'reminder_sent', 'created_at', 'stage'];
/** The keys a statement's jsonb_build_object projects: the part that LEAVES the database. */
const projected = (q: string) => {
  const m = q.match(/jsonb_build_object\(([\s\S]*?)\)\) AS fields/);
  assert.ok(m, 'no jsonb_build_object projection found');
  return [...m[1].matchAll(/'([a-z_]+)',\s/g)].map((x) => x[1]).sort();
};

test('not a proxy (Function.length): the exported API is exactly the known set, and every read takes NO argument', () => {
  const fns = Object.entries(store).filter(([, v]) => typeof v === 'function' && !/^class\s/.test(String(v)));
  const arity = Object.fromEntries(fns.map(([k, v]) => [k, (v as (...a: unknown[]) => unknown).length]));
  // A new export, or a read that grows a parameter, fails here and has to be argued for.
  assert.deepEqual(arity, { budgetUsed: 0, readAppointments: 0, readHandoffQueue: 0, readLeads: 0, readSpend: 0, resetBudget: 0, toPage: 1 });
});

test('source text (a spelling check): no exported function declares a parameter, except the pure toPage, and each read names ONE fixed table', () => {
  // Function.length misses a parameter with a default value (a mutant proved it), so the SOURCE is read too.
  const decls = [...CODE.matchAll(/export\s+(?:async\s+)?function\s+(\w+)\s*(?:<[^>]*>)?\(([^)]*)\)/g)];
  assert.ok(decls.length >= 7, `found ${decls.length} exported functions; the check would be vacuous`);
  for (const [, name, params] of decls) {
    if (name === 'toPage') continue;
    assert.equal(params.trim(), '', `${name} declares parameters: (${params})`);
  }
  const reads = [...CODE.matchAll(/export\s+async\s+function\s+(read\w+)\(\)[^{]*\{([^}]*)\}/g)];
  assert.equal(reads.length, 4, 'expected exactly four exported reads');
  for (const [, name, body] of reads) assert.match(body.trim(), /^return read<\w+>\('(appointments|leads|handoff|spend)'\);$/, `${name} must pass one literal table`);
});

test('source text (a spelling check): each `.query(` names a module constant; SQL is frozen, four statements, no `$n`, LIMIT 101', () => {
  const calls = [...CODE.matchAll(/\.query\(\s*([^)]*?)\s*\)/g)].map((m) => m[1]);
  assert.ok(calls.length >= 2, `found ${calls.length} .query( calls; the check would be vacuous`);
  for (const arg of calls) assert.match(arg, /^(SQL\[table\]|WRITE_CHECK)$/, `a query takes '${arg}', not a module constant`);
  assert.ok(Object.isFrozen(store.SQL), 'SQL must be frozen so nothing can swap a statement at runtime');
  assert.deepEqual(Object.keys(store.SQL).sort(), ['appointments', 'handoff', 'leads', 'spend']);
  for (const [k, q] of Object.entries(store.SQL)) {
    assert.doesNotMatch(q, /\$\d/, `${k} carries a bound parameter`);
    assert.match(q, new RegExp(`LIMIT ${store.PAGE_ROWS + 1}\\b`), `${k} must fetch PAGE_ROWS + 1 to know it truncated`);
  }
});

test('E2: no statement selects a column the dashboard does not display', () => {
  for (const [k, q] of Object.entries(store.SQL)) {
    for (const col of FORBIDDEN) assert.ok(!new RegExp(`\\b${col}\\b`).test(q), `${k} selects ${col}`);
  }
  for (const col of FORBIDDEN) assert.ok(!new RegExp(`\\b${col}\\b`).test(CODE), `store.ts names ${col} outside a comment`);
});

test('E2: each panel selects exactly its displayed columns, and none of the five trimmed context columns', () => {
  for (const [k, q] of Object.entries(store.SQL)) {
    const keys = projected(q);
    assert.deepEqual(keys, [...DISPLAYED[k as keyof typeof DISPLAYED]].sort(), `${k}'s column list drifted`);
    for (const t of TRIMMED) assert.ok(!keys.includes(t), `${k} projects ${t} again; no panel reads it (Codex F7)`);
  }
});

test('E2 (F7): every projected column has a reader outside store.ts and types.ts; the trimmed ones have none', () => {
  // "A field that is displayed is fetched; a field that is not displayed is not fetched." The second half is
  // checked here by looking for the READER: a property access `.col` in components/, app/ or lib/, comments
  // stripped, tests, store.ts and types.ts excluded. A text search, so it proves a reader EXISTS, not that it
  // draws; its value is the negative direction, a projected column nobody touches.
  const root = new URL('../', import.meta.url);
  const files: string[] = [];
  const walk = (dir: URL) => {
    for (const n of readdirSync(dir)) {
      const u = new URL(n, dir);
      if (statSync(u).isDirectory()) walk(new URL(`${n}/`, dir));
      else if (/\.(ts|tsx)$/.test(n) && !/\.test\.ts$/.test(n) && !/lib\/(store|types)\.ts$/.test(u.pathname)) files.push(u.pathname);
    }
  };
  for (const d of ['components/', 'app/', 'lib/']) walk(new URL(d, root));
  assert.ok(files.length >= 10, `scanned ${files.length} files; the search would be vacuous`);
  const code = files.map((f) => readFileSync(f, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')).join('\n');
  const readers = (col: string) => new RegExp(`\\.${col}\\b`).test(code);
  const all = [...new Set(Object.values(store.SQL).flatMap(projected))];
  assert.ok(all.length >= 15, 'the projections yielded too few columns; the check would be vacuous');
  for (const col of all) assert.ok(readers(col), `${col} is fetched but nothing in components/, app/ or lib/ reads it`);
  for (const col of TRIMMED) assert.ok(!readers(col), `${col} now has a reader: re-add it to its projection and to DISPLAYED, deliberately`);
});

test('shape: the Airtable rules the panels were written against (no null, no "", no false; ISO-ms; a NUMBER for cost)', () => {
  for (const [k, q] of Object.entries(store.SQL)) assert.match(q, /jsonb_strip_nulls\(jsonb_build_object\(/, k);
  assert.match(store.SQL.appointments, /'reminded', CASE WHEN reminded THEN true END/);
  assert.match(store.SQL.spend, /'cost_usd', cost_usd::float8/, 'the cast guards SystemHealth\'s typeof check against a raw numeric, which arrives as a STRING');
  for (const ts of ['start_utc', 'last_alert_at', 'last_updated', 'updated_at']) {
    const q = Object.values(store.SQL).find((s) => s.includes(`'${ts}'`))!;
    assert.match(q, new RegExp(`'${ts}', salon\\.at_ts\\(${ts}\\)`), `${ts} must go through salon.at_ts`);
  }
});

test('toPage: 101 rows → the first 100 and truncated; 100 → not truncated; empty fields → just the id', () => {
  const rows = Array.from({ length: 101 }, (_, i) => ({ id: `rec${String(i).padStart(14, '0')}`, fields: { last_intent: 'handoff' } }));
  const p = store.toPage<{ id: string; last_intent: string }>(rows);
  assert.equal(p.rows.length, 100); assert.equal(p.truncated, true); assert.equal(p.rows[0].last_intent, 'handoff');
  assert.equal(store.toPage(rows.slice(0, 100)).truncated, false);
  assert.deepEqual(store.toPage([{ id: 'recAAAAAAAAAAAAAA', fields: null }]).rows, [{ id: 'recAAAAAAAAAAAAAA' }]);
  // A field can never overwrite the id.
  assert.equal(store.toPage<{ id: string }>([{ id: 'recBBBBBBBBBBBBBB', fields: { id: 'forged' } }]).rows[0].id, 'recBBBBBBBBBBBBBB');
});

test('config: a missing PG variable is a ConfigError, raised before any connection', async () => {
  const saved = { ...process.env };
  for (const k of ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD']) delete process.env[k];
  try {
    store.resetBudget();
    await assert.rejects(store.readSpend(), (e: Error) => e.name === 'ConfigError' && /PGHOST/.test(e.message));
    assert.equal(store.budgetUsed(), 0, 'a configuration fault must not count as a read');
  } finally {
    Object.assign(process.env, saved);
  }
});

test('WRITE_CHECK asks the four table privileges on all five salon tables, and any one refuses', () => {
  // The NARROW claim, on purpose: a table-privilege count, not proof the credential cannot write (store.ts lists
  // what it does not see, Codex CRT #10 F1).
  const m = CODE.match(/const WRITE_CHECK = `([\s\S]*?)`;/);
  assert.ok(m, 'WRITE_CHECK not found');
  for (const t of ['appointments', 'bot_metrics', 'conversations', 'leads', 'processed_messages']) assert.ok(m[1].includes(`'${t}'`), t);
  for (const p of ['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) assert.ok(m[1].includes(`'${p}'`), p);
  assert.match(CODE, /if \(writable !== 0\)/, 'the check must refuse on ANY writable privilege');
});

// ── F12: the handoff queue's ORDER BY is the panel's triage order ───────────────────────────────────────────
//
// WHAT THIS PROVES OFFLINE: `sqlRank` below is the CASE in `SQL.handoff`, transliterated line for line, and the
// first test pins the SQL text it was transliterated from, so the two cannot drift apart silently. On fixture rows
// held as the DATABASE holds them (microsecond timestamps, NULLs, '' and whitespace classes), the transliteration
// agrees with `triageRank(alertState(...))` applied to what the store would hand the panel (`salon.at_ts`'s
// millisecond ISO strings, `NULLIF`/`jsonb_strip_nulls` dropping empties), and the panel's sort is a no-op on
// rows that arrive in the SQL's order.
// WHAT IT CANNOT PROVE, and belongs to a live window: that Postgres evaluates the statement as transliterated.
// Three points rest on that: `to_char(..., 'MS')` inside `salon.at_ts` TRUNCATES microseconds (assumed here, and
// it is why the CASE compares `date_trunc('milliseconds', …)` values, so a 29:59.9995 gap ranks as JavaScript
// sees it); `[[:space:]]` matches the ASCII whitespace JavaScript's `trim` removes (a class made only of
// Unicode spaces such as U+00A0 may be ranked differently; the engine writes fixed class names); and ids
// compare in byte order (fixture ids are same-length digit strings, so any collation agrees; the panel never
// compares ids itself, see `triageCompare`).
const ORDER_BY = `ORDER BY CASE
        WHEN last_alert_class IS NULL OR last_alert_class ~ '^[[:space:]]*$' OR last_alert_at IS NULL THEN 0
        WHEN date_trunc('milliseconds', last_updated) - date_trunc('milliseconds', last_alert_at)
             >= interval '${STALE_AFTER_MINUTES} minutes' THEN 1
        ELSE 2
      END, last_updated DESC NULLS LAST, id`;
const squash = (s: string) => s.replace(/\s+/g, ' ').trim();

/** A conversations row as Postgres holds it: timestamps in epoch MICROseconds, or null. */
interface DbRow { id: string; cls: string | null; alertUs: number | null; updatedUs: number | null }
const truncMs = (us: number) => Math.floor(us / 1000);
/** The CASE, transliterated. */
function sqlRank(r: DbRow): number {
  if (r.cls === null || /^[ \t\n\v\f\r]*$/.test(r.cls) || r.alertUs === null) return 0;
  if (r.updatedUs !== null && (truncMs(r.updatedUs) - truncMs(r.alertUs)) * 1000 >= STALE_AFTER_MINUTES * 60_000_000) return 1;
  return 2;
}
/** ORDER BY <rank>, last_updated DESC NULLS LAST, id. */
function sqlOrder(rows: DbRow[]): DbRow[] {
  return [...rows].sort((a, b) => {
    const d = sqlRank(a) - sqlRank(b);
    if (d) return d;
    if ((a.updatedUs === null) !== (b.updatedUs === null)) return a.updatedUs === null ? 1 : -1;
    if (a.updatedUs !== null && b.updatedUs !== null && a.updatedUs !== b.updatedUs) return b.updatedUs - a.updatedUs;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}
/** What the store hands the panel for that row: `salon.at_ts` (ms ISO), `NULLIF(x, '')`, nulls stripped. */
function projectRow(r: DbRow) {
  const iso = (us: number | null) => (us === null ? undefined : new Date(truncMs(us)).toISOString());
  const row: { id: string; last_alert_class?: string; last_alert_at?: string; last_updated?: string } = { id: r.id };
  if (r.cls !== null && r.cls !== '') row.last_alert_class = r.cls;
  if (iso(r.alertUs)) row.last_alert_at = iso(r.alertUs);
  if (iso(r.updatedUs)) row.last_updated = iso(r.updatedUs);
  return row;
}

const T = Date.UTC(2026, 9, 24, 12) * 1000;   // µs
const MIN = 60_000_000;                        // µs
let seq = 0;
const row = (cls: string | null, alertUs: number | null, updatedUs: number | null): DbRow =>
  ({ id: `rec${String(++seq).padStart(14, '0')}`, cls, alertUs, updatedUs });
const F12_ROWS: DbRow[] = [
  row(null, null, T),                                     // never notified
  row('', T - MIN, T - 2 * MIN),                          // '' is NULLIF'd away: unconfirmed
  row(' \t ', T - MIN, T + 5 * MIN),                      // whitespace-only class: unconfirmed in both
  row('booking_handoff', null, T - 3 * MIN),              // a class with no delivery time
  row('booking_handoff', T - 30 * MIN, T),                // exactly 30:00.000 behind: stale
  row('booking_handoff', T - 30 * MIN + 999, T),          // 29:59.999001 raw, 30:00.000 after truncation: stale
  row('booking_handoff', T - 30 * MIN + 1000, T + 999),   // 29:59.999 after truncation: notified
  row('booking_handoff', T - 120 * MIN, T - 10 * MIN),    // well behind: stale
  row('booking_handoff', T + MIN, T),                     // alert NEWER than the conversation: notified
  row('booking_handoff', T - 5 * MIN, null),              // no last_updated (NOT NULL today): notified, sinks
  row('jailbreak', T - 5 * MIN, T - MIN),                 // notified
  row('jailbreak', T - 5 * MIN, T - MIN + 400),           // same millisecond, later microsecond: SQL puts it first
  row('jailbreak', T - 5 * MIN, T - MIN + 400),           // identical time: the id decides
  row(null, null, null),                                  // unconfirmed with no time: last of its group
  row(null, null, T - 50 * MIN),
];

test('F12: SQL.handoff orders by the triage CASE before its LIMIT, exactly as transliterated here', () => {
  const q = squash(store.SQL.handoff);
  assert.ok(q.includes(squash(`${ORDER_BY} LIMIT ${store.PAGE_ROWS + 1}`)),
    'SQL.handoff\'s ORDER BY is not the text sqlRank/sqlOrder transliterate: change both together, deliberately');
  assert.match(q, /WHERE stage = 'handoff' ORDER BY/, 'the stage filter stays in WHERE; only the projection dropped it');
});

test('F12: on boundary rows the SQL rank equals triageRank(alertState(...)) of what the panel receives', () => {
  const ranks = new Set<number>();
  for (const r of F12_ROWS) {
    const p = projectRow(r);
    const js = triageRank(alertState(p.last_alert_class, p.last_alert_at, p.last_updated));
    assert.equal(sqlRank(r), js, `${r.id}: SQL ranks ${sqlRank(r)}, the panel ${js} (${JSON.stringify(p)})`);
    ranks.add(js);
  }
  assert.deepEqual([...ranks].sort(), [0, 1, 2], 'the fixtures must cover all three ranks');
});

test('F12: rows in the SQL order come out of the panel\'s sort unchanged, and the old newest-first order would not', () => {
  const ordered = sqlOrder(F12_ROWS).map(projectRow);
  assert.deepEqual([...ordered].sort(triageCompare), ordered, 'the panel re-sorted rows the SQL had already ordered');
  // Non-vacuity: the order this replaced (last_updated DESC, id) is NOT already the triage order on these rows.
  const old = [...F12_ROWS].sort((a, b) => (b.updatedUs ?? -Infinity) - (a.updatedUs ?? -Infinity) || (a.id < b.id ? -1 : 1)).map(projectRow);
  assert.notDeepEqual(old, ordered);
  // And what that costs at the LIMIT: 150 notified rows newer than one unconfirmed row. Newest-first fetches
  // 101 notified rows and the unconfirmed one never reaches the panel; the triage order fetches it first.
  const many = [row(null, null, T - 999 * MIN), ...Array.from({ length: 150 }, (_, i) => row('booking_handoff', T - i * MIN - MIN, T - i * MIN))];
  const top = (rs: DbRow[]) => rs.slice(0, store.PAGE_ROWS + 1).map((r) => r.id);
  const byNewest = [...many].sort((a, b) => b.updatedUs! - a.updatedUs!);
  assert.ok(!top(byNewest).includes(many[0].id), 'control: newest-first must cut the unconfirmed row');
  assert.equal(top(sqlOrder(many))[0], many[0].id, 'the triage order must fetch the unconfirmed row first');
});

// LAST on purpose: it builds the module's one pool (and ends it), so nothing after it may read.
test('F3: an idle-connection error is logged as a CLASS only, does not escape, and the next read reconnects', async () => {
  // Ported from Codex CRT #10's idle-error probe. The pool is the REAL pg pool, built BY store.ts; only the
  // connection is fake, so what runs is pg's own idle-client handling: it drops the failed client and emits
  // 'error' on the pool, where an absent listener is an unhandled error event that ends the process.
  const RealPool = pg.Pool;
  const clients: FakeClient[] = [];
  const built: { pool: InstanceType<typeof RealPool> | null } = { pool: null };
  class FakeClient extends EventEmitter {
    // The two flags pg-pool reads on release to decide whether a client may go back to the idle list.
    _queryable = true;
    _ending = false;
    n: number;
    constructor() { super(); clients.push(this); this.n = clients.length; }
    connect(cb: (e?: Error) => void) { process.nextTick(cb); }
    query(text: string, _values: unknown, cb: (e: Error | null, r?: unknown) => void) {
      const rows = text.includes('current_user AS role')
        ? [{ role: 'fake_ro', writable: 0 }]
        : [{ id: `rec-fake-${this.n}`, fields: { period_key: '2026-10' } }];
      process.nextTick(() => cb(null, { rows }));
    }
    end(cb?: () => void) { this._ending = true; this.emit('end'); if (cb) process.nextTick(cb); }
  }
  class StubPool extends RealPool {
    constructor(opts: object) { super({ ...opts, Client: FakeClient }); built.pool = this; }
  }

  const PG = ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD'];
  const savedEnv = Object.fromEntries(PG.map((k) => [k, process.env[k]]));
  const savedConsole = { error: console.error, warn: console.warn, log: console.log, info: console.info };
  const logged: string[] = [];
  // Every argument is inspected, so a logged error OBJECT would expose its message (and stack) here too.
  const capture = (...a: unknown[]) => { logged.push(a.map((x) => (typeof x === 'string' ? x : inspect(x))).join(' ')); };
  const MARKER = 'F3-MARKER host=db.example user=salon_ro dbname=salon';

  (pg as { Pool: unknown }).Pool = StubPool;
  for (const k of PG) process.env[k] = 'f3-synthetic';
  Object.assign(console, { error: capture, warn: capture, log: capture, info: capture });
  try {
    store.resetBudget();
    assert.equal((await store.readSpend()).rows[0].id, 'rec-fake-1');
    assert.ok(built.pool, 'store.ts did not build its pool through pg.Pool; the probe would test nothing');

    // A SQLSTATE and an errno code are logged as themselves; a code that is not one, or none, is 'unknown'.
    for (const [code, cls] of [['57P01', '57P01'], ['ECONNRESET', 'ECONNRESET'], ['host=db.example', 'unknown'], [undefined, 'unknown']]) {
      const idle = clients.at(-1)!;
      const before = clients.length;
      logged.length = 0;
      const err = Object.assign(new Error(MARKER), code === undefined ? {} : { code });
      assert.doesNotThrow(() => idle.emit('error', err), 'the idle error escaped the pool: an unhandled error event ends the process');
      assert.equal(logged.length, 1, `expected one log line, got ${logged.length}`);
      assert.ok(logged[0].includes(`(${cls})`), `the line must carry the class ${cls}: ${logged[0]}`);
      assert.ok(!logged[0].includes('F3-MARKER') && !logged[0].includes('db.example'), `the line leaks the message or the code text: ${logged[0]}`);
      store.resetBudget();
      const next = await store.readSpend();
      assert.equal(clients.length, before + 1, 'the next read must open a FRESH connection, not reuse the failed one');
      assert.equal(next.rows[0].id, `rec-fake-${before + 1}`, 'the next read must be served by that fresh connection');
    }
    // After five reads: one listener, so it is attached at construction and not on every getPool().
    assert.equal(built.pool.listenerCount('error'), 1, 'expected exactly one pool error listener');
  } finally {
    Object.assign(console, savedConsole);
    (pg as { Pool: unknown }).Pool = RealPool;
    for (const k of PG) { if (savedEnv[k] === undefined) delete process.env[k]; else process.env[k] = savedEnv[k]; }
    await built.pool?.end();
  }
});
