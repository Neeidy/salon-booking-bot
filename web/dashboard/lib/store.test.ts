/**
 * CRT #10's offline half for the Postgres read path (D5, MIGRATION-PLAN §3t). What these check WITHOUT a
 * database: the not-a-proxy rule, by reading `store.ts`'s own text (a text check catches the spellings it looks
 * for and is not a proof: Codex CRT #10 F4 kept all of them green with twelve proxy mutants; a behaviour-based
 * test is a named Phase 7 item); that no statement selects the columns E2 keeps out; that every panel's column
 * list equals its hand-named DISPLAYED list below (which carries five non-PII context columns no panel draws, so
 * it agrees with the module rather than with the rendering: Codex F7, Phase 7); that truncation and configuration
 * faults surface; and, through the REAL
 * pg pool with a fake connection, that an idle-connection error neither kills the process nor leaks its message.
 * The live half (the queries on seeded rows, the read-only role refusing a write) is round 2's.
 *
 * Run: node --test lib/store.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { EventEmitter } from 'node:events';
import { inspect } from 'node:util';
import pg from 'pg';
import * as store from './store.ts';

const SRC = readFileSync(new URL('./store.ts', import.meta.url), 'utf8');
// The source without comments, so a word in a comment cannot satisfy or trip a check.
const CODE = SRC.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

const FORBIDDEN = ['sender_key', 'gcal_event_id', 'computed_reply', 'cancel_target_id', 'calendar_id', 'confirm_turn'];
const DISPLAYED = {
  appointments: ['start_utc', 'end_utc', 'service', 'channel', 'status', 'reminded', 'reminder_sent', 'created_at', 'customer_name'],
  leads: ['name', 'phone', 'source', 'status', 'created_at'],
  handoff: ['sender_masked', 'stage', 'last_alert_class', 'last_alert_at', 'last_intent', 'turn_count', 'last_updated', 'recent_messages'],
  spend: ['period_key', 'cost_usd', 'updated_at'],
};

test('not a proxy: the exported API is exactly the known set, and every read takes NO argument', () => {
  const fns = Object.entries(store).filter(([, v]) => typeof v === 'function' && !/^class\s/.test(String(v)));
  const arity = Object.fromEntries(fns.map(([k, v]) => [k, (v as (...a: unknown[]) => unknown).length]));
  // A new export, or a read that grows a parameter, fails here and has to be argued for.
  assert.deepEqual(arity, { budgetUsed: 0, readAppointments: 0, readHandoffQueue: 0, readLeads: 0, readSpend: 0, resetBudget: 0, toPage: 1 });
});

test('not a proxy: no exported function declares a parameter, except the pure toPage, and each read names ONE fixed table', () => {
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

test('not a proxy: every query the module sends is one of its own constants, with no bound parameter', () => {
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

test('E2: each panel selects exactly its displayed columns', () => {
  for (const [k, q] of Object.entries(store.SQL)) {
    const keys = [...q.matchAll(/'([a-z_]+)',\s/g)].map((m) => m[1]).sort();
    assert.deepEqual(keys, [...DISPLAYED[k as keyof typeof DISPLAYED]].sort(), `${k}'s column list drifted`);
  }
});

test('shape: the Airtable rules the panels were written against (no null, no "", no false; ISO-ms; a NUMBER for cost)', () => {
  for (const [k, q] of Object.entries(store.SQL)) assert.match(q, /jsonb_strip_nulls\(jsonb_build_object\(/, k);
  assert.match(store.SQL.appointments, /'reminded', CASE WHEN reminded THEN true END/);
  assert.match(store.SQL.spend, /'cost_usd', cost_usd::float8/, 'the cast guards SystemHealth\'s typeof check against a raw numeric, which arrives as a STRING');
  for (const ts of ['start_utc', 'end_utc', 'reminder_sent', 'created_at', 'last_alert_at', 'last_updated', 'updated_at']) {
    const q = Object.values(store.SQL).find((s) => s.includes(`'${ts}'`))!;
    assert.match(q, new RegExp(`'${ts}', salon\\.at_ts\\(${ts}\\)`), `${ts} must go through salon.at_ts`);
  }
});

test('toPage: 101 rows → the first 100 and truncated; 100 → not truncated; empty fields → just the id', () => {
  const rows = Array.from({ length: 101 }, (_, i) => ({ id: `rec${String(i).padStart(14, '0')}`, fields: { stage: 'handoff' } }));
  const p = store.toPage<{ id: string; stage: string }>(rows);
  assert.equal(p.rows.length, 100); assert.equal(p.truncated, true); assert.equal(p.rows[0].stage, 'handoff');
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
