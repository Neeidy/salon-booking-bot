/**
 * CRT #10's offline half for the Postgres read path (D5, MIGRATION-PLAN §3t). What these prove WITHOUT a
 * database: that `store.ts` is not a proxy, that it never selects the columns E2 keeps out, that every panel's
 * column list is exactly the displayed set, and that truncation and configuration faults surface. The live half
 * (the queries on seeded rows, the read-only role refusing a write) is round 2's.
 *
 * Run: node --test lib/store.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
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

test('the read-only check: it asks about every salon table and every write privilege', () => {
  const m = CODE.match(/const WRITE_CHECK = `([\s\S]*?)`;/);
  assert.ok(m, 'WRITE_CHECK not found');
  for (const t of ['appointments', 'bot_metrics', 'conversations', 'leads', 'processed_messages']) assert.ok(m[1].includes(`'${t}'`), t);
  for (const p of ['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) assert.ok(m[1].includes(`'${p}'`), p);
  assert.match(CODE, /if \(writable !== 0\)/, 'the check must refuse on ANY writable privilege');
});
