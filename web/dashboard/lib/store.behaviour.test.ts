/**
 * CRT #10 F4 — the not-a-proxy rule, checked by BEHAVIOUR rather than by reading `store.ts`'s text.
 *
 * WHAT THIS DOES: before `store.ts` is loaded, `pg.Pool` and `pg.Client` are replaced with recording fakes, so
 * every statement the module sends through the `pg` driver lands in `sent` with its bound values. Then EVERY
 * export is called with every argument set in `HOSTILE` (nothing, a table name aimed at the wrong read, a raw
 * statement, objects carrying `table`/`sql`/`text`/`values` keys, a second argument after a valid first one, a
 * function, an object whose `toString` is a statement). After each call it asserts:
 *   - every statement sent is a member of `store.SQL` (snapshotted at import) or the privilege check, and no
 *     bound value is passed with it, not even an empty list;
 *   - each read sends EXACTLY its own statement whatever it was given (`readSpend('leads')` must still send
 *     `SQL.spend`), and every other export sends nothing;
 *   - an export this file does not classify fails, so a new export has to be argued for here.
 * Codex CRT #10 F4's twelve proxy mutants (each one kept the source-text tests in `store.test.ts` green) were run
 * against this file; the table and the commands are in the Phase 7 F2 report.
 *
 * WHAT IT CANNOT SEE, stated so a green run is not read as more than it is:
 *   - a statement sent by any route OTHER than the `pg` module's Pool or Client (another driver, a raw socket,
 *     `pg-pool` or `pg/lib/client` imported directly). The last test narrows that with a check of the module's
 *     import list, which is a text check and has the limits of one;
 *   - WHICH columns a member of `SQL` selects: a mutant that adds `sender_key` to `SQL.appointments` passes here,
 *     because the statement it sends is still a member of `SQL`. That is the E2 tests' job, in `store.test.ts`;
 *   - a branch that fires only on a condition `HOSTILE` does not produce (a date, an env value, a call count).
 *     It is a strong sample of inputs, not an exhaustive one.
 *
 * Its own file because the fakes must be installed BEFORE the first `import 'pg'` anywhere in the process: pg's
 * ESM wrapper copies `Pool` and `Client` when it is first evaluated, so a module that wrote
 * `import { Pool } from 'pg'` would otherwise keep the real driver. `node --test` runs each file in its own
 * process, which is what makes that ordering hold.
 *
 * Run: node --test lib/store.behaviour.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { EventEmitter } from 'node:events';
import { readFileSync } from 'node:fs';

/** The privilege check `store.ts` keeps private. Compared with whitespace collapsed. A change to it must be
 *  made here too, on purpose: a different statement on that path is exactly what this file exists to notice. */
const WRITE_CHECK = `SELECT current_user AS role, count(*)::int AS writable
    FROM unnest(ARRAY['appointments', 'bot_metrics', 'conversations', 'leads', 'processed_messages']) t,
         unnest(ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) p
    WHERE has_table_privilege(current_user, 'salon.' || t, p)`;
const norm = (s: string) => s.replace(/\s+/g, ' ').trim();

interface Sent { via: string; text: unknown; values: unknown; configKeys: string[] | null }
const sent: Sent[] = [];

function record(via: string, config: unknown, values: unknown, cb: unknown): unknown {
  if (typeof values === 'function') { cb = values; values = undefined; }
  let text = config;
  let bound = values;
  let configKeys: string[] | null = null;
  if (config !== null && typeof config === 'object') {
    const c = config as { text?: unknown; values?: unknown };
    configKeys = Object.keys(c).sort();
    text = c.text;
    bound = c.values ?? values;
  }
  sent.push({ via, text, values: bound, configKeys });
  const rows = typeof text === 'string' && norm(text) === norm(WRITE_CHECK) ? [{ role: 'f4_ro', writable: 0 }] : [];
  const result = { rows, rowCount: rows.length };
  if (typeof cb === 'function') { process.nextTick(cb as (e: null, r: unknown) => void, null, result); return undefined; }
  return Promise.resolve(result);
}

class FakeClient extends EventEmitter {
  constructor(_opts?: unknown) { super(); }
  connect(cb?: (e?: Error) => void) { if (cb) { process.nextTick(cb); return undefined; } return Promise.resolve(); }
  query(config: unknown, values?: unknown, cb?: unknown) { return record('client.query', config, values, cb); }
  release() {}
  end(cb?: () => void) { if (cb) { process.nextTick(cb); return undefined; } return Promise.resolve(); }
}
class FakePool extends EventEmitter {
  constructor(_opts?: unknown) { super(); }
  query(config: unknown, values?: unknown, cb?: unknown) { return record('pool.query', config, values, cb); }
  connect(cb?: (e: Error | null, c?: FakeClient, done?: () => void) => void) {
    const c = new FakeClient();
    if (cb) { process.nextTick(cb, null, c, () => {}); return undefined; }
    return Promise.resolve(c);
  }
  end(cb?: () => void) { if (cb) { process.nextTick(cb); return undefined; } return Promise.resolve(); }
}

// Installed through CommonJS, before anything evaluates pg's ESM wrapper (see the header).
const pgCjs = createRequire(import.meta.url)('pg');
pgCjs.Pool = FakePool;
pgCjs.Client = FakeClient;
Object.defineProperty(pgCjs, 'native', { configurable: true, enumerable: false, value: { Pool: FakePool, Client: FakeClient } });
for (const k of ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD']) process.env[k] = 'f4-synthetic';

const store = await import('./store.ts');
const sentAtImport = sent.length;
const SQL_AT_IMPORT: Record<string, string> = { ...store.SQL };
const ALLOWED = new Set([...Object.values(SQL_AT_IMPORT), WRITE_CHECK]);
const isWriteCheck = (t: unknown) => typeof t === 'string' && norm(t) === norm(WRITE_CHECK);

/** Every function export, and what it may send. `null` = nothing at all. */
const EXPECT: Record<string, string | null> = {
  readAppointments: 'appointments',
  readLeads: 'leads',
  readHandoffQueue: 'handoff',
  readSpend: 'spend',
  resetBudget: null,
  budgetUsed: null,
  toPage: null,
};

const RAW = 'SELECT sender_key, gcal_event_id FROM salon.conversations';
const HOSTILE: unknown[][] = [
  [],
  ['appointments'], ['leads'], ['handoff'], ['spend'], ['bot_metrics'], ['conversations'],
  [RAW],
  [`${RAW} WHERE id = $1`, ['rec1']],
  [{ table: 'conversations', sql: RAW, text: RAW, values: ['x'], columns: ['sender_key'], where: '1=1', orderBy: 'id', id: 'rec1' }],
  [{ text: RAW }],
  ['spend', RAW],
  [[{ id: 'recF4', fields: {} }], RAW],
  [[{ id: 'recF4', fields: {} }], { sql: RAW }],
  [undefined, RAW],
  [undefined, undefined, RAW],
  [null], [0], [42], [true], [['appointments']],
  [() => RAW],
  [{ toString() { return RAW; } }],
];

const flush = () => new Promise((r) => setImmediate(r));
const isClass = (v: unknown) => typeof v === 'function' && /^class\s/.test(Function.prototype.toString.call(v));

test('F4 recorder: nothing is sent at import, and the recorder intercepts what the reads send', async () => {
  assert.equal(sentAtImport, 0, 'store.ts sent a statement while it was being imported');
  store.resetBudget();
  await store.readSpend();
  assert.ok(sent.some((s) => s.text === SQL_AT_IMPORT.spend), 'the fake did not see SQL.spend: every later check would be vacuous');
  assert.ok(sent.some((s) => isWriteCheck(s.text)), 'the fake did not see the privilege check');
});

test('F4: every export, called with hostile arguments, sends only its own constant statement and no bound value', async () => {
  const fns = Object.entries(store).filter(([, v]) => typeof v === 'function');
  assert.ok(fns.length >= Object.keys(EXPECT).length, `found ${fns.length} function exports; the loop would be vacuous`);
  for (const [name, fn] of fns) {
    if (isClass(fn)) continue;   // the error classes, below
    assert.ok(name in EXPECT, `${name} is an export this test does not classify: say what it may send, in EXPECT`);
    for (const args of HOSTILE) {
      store.resetBudget();
      const from = sent.length;
      let threw: unknown = null;
      try { await (fn as (...a: unknown[]) => unknown)(...args); } catch (e) { threw = e; }
      await flush();
      const mine = sent.slice(from);
      const label = `${name}(${args.map((a) => (typeof a === 'function' ? 'fn' : JSON.stringify(a))).join(', ')})`;
      for (const s of mine) {
        assert.equal(typeof s.text, 'string', `${label} sent a non-string statement via ${s.via}`);
        assert.ok(ALLOWED.has(s.text as string) || isWriteCheck(s.text), `${label} sent a statement that is not a module constant via ${s.via}: ${String(s.text).slice(0, 120)}`);
        assert.equal(s.values, undefined, `${label} passed bound values via ${s.via}`);
        if (s.configKeys) assert.deepEqual(s.configKeys, ['text'], `${label} passed a query config with ${s.configKeys.join(',')}`);
      }
      const reads = mine.filter((s) => !isWriteCheck(s.text)).map((s) => s.text);
      const want = EXPECT[name];
      assert.deepEqual(reads, want ? [SQL_AT_IMPORT[want]] : [], `${label} must send ${want ? `exactly SQL.${want}` : 'nothing'}`);
      // A read ignores its arguments, so it must succeed whatever it was handed.
      if (want) assert.equal(threw, null, `${label} threw: ${threw instanceof Error ? threw.message : String(threw)}`);
    }
  }
});

test('F4: constructing the error classes with hostile arguments sends nothing', async () => {
  const classes = Object.entries(store).filter(([, v]) => isClass(v));
  assert.deepEqual(classes.map(([k]) => k).sort(), ['ConfigError', 'StoreError']);
  const from = sent.length;
  for (const [, C] of classes) {
    for (const args of HOSTILE) { try { Reflect.construct(C as new (...a: unknown[]) => unknown, args); } catch { /* a refusal is fine */ } }
  }
  await flush();
  assert.equal(sent.length, from);
});

test('F4: across the whole run, the privilege check went once and first, and SQL could not be swapped', () => {
  const checks = sent.map((s, i) => (isWriteCheck(s.text) ? i : -1)).filter((i) => i >= 0);
  assert.equal(checks.length, 1, `the privilege check ran ${checks.length} times; a pass is cached per process`);
  assert.equal(checks[0], 0, 'the privilege check must precede the first read');
  assert.throws(() => { (store.SQL as Record<string, string>).spend = RAW; }, TypeError);
  assert.deepEqual({ ...store.SQL }, SQL_AT_IMPORT);
  for (const k of Object.keys(SQL_AT_IMPORT)) assert.ok(sent.some((s) => s.text === SQL_AT_IMPORT[k]), `SQL.${k} was never sent: its read was not exercised`);
});

test('F4 boundary (a TEXT check): store.ts imports nothing but pg and its own pure siblings', () => {
  // The recorder only sees `pg`. A module that reached the database some other way would pass every test above,
  // so the import list is pinned. Spelling-based, with the limits store.test.ts's text checks state.
  const src = readFileSync(new URL('./store.ts', import.meta.url), 'utf8');
  const specs = [...src.matchAll(/^\s*(?:import|export)\b[^;'"`]*?\bfrom\s*['"]([^'"]+)['"]/gm)].map((m) => m[1]);
  const bare = [...src.matchAll(/^\s*import\s*['"]([^'"]+)['"]/gm)].map((m) => m[1]);
  assert.ok(specs.includes('pg'), 'the import scan found no `pg` import: it would be vacuous');
  for (const s of [...specs, ...bare]) assert.ok(['pg', './types.ts', './alertState.ts'].includes(s), `store.ts imports ${s}`);
  assert.doesNotMatch(src, /\bimport\s*\(|\brequire\s*\(|createRequire/, 'store.ts loads a module dynamically');
});
