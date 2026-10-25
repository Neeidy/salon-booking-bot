/**
 * The leads branch of Purge must not report "no candidates" when the store READ failed (7-F1 item 2).
 *
 * WHY IT EXISTS: `Count Leads Total`, `Find Old Leads` and `Count Leads After` ran with `alwaysOutputData` +
 * `continueErrorOutput`. On a read error each sent the error item to output 1 AND an empty item to output 0, so the
 * branch carried on and `Leads Purge Sane?` added a `no_candidates` refusal next to the real error: during a store
 * outage the owner read "no candidates" (MIGRATION-PLAN §3r, D3d R1, finding 2 — measured live). The fix makes each
 * read an aggregate that returns exactly ONE row on success (`count(*)`, `coalesce(jsonb_agg(id), '[]')`), drops
 * `alwaysOutputData` on the three, and lets the Code nodes unpack the one row.
 *
 * HOW: a small offline model of the branch, driven by the export itself — its connections, each node's `onError` and
 * `alwaysOutputData`, its SQL text and parameter expressions, its Code bodies and its IF expressions. The store is an
 * in-memory list of fake leads, and the model answers only the SQL shapes it knows; any other query is a hard failure,
 * so a changed query cannot be silently answered with a guess. What it models of n8n, and where that comes from:
 *   · a data node runs once per incoming item, and a node with no incoming items does not run;
 *   · under continueErrorOutput a read error goes to output 1 as `{error, message}` (the `single` shape, M7/T3);
 *   · `alwaysOutputData` puts one empty item on output 0 when output 0 would be empty — on an error too, which is
 *     exactly finding 2 (measured live on the copy, D3d R1);
 *   · `$('Node')` reads that node's output 0.
 * It is a model: the claim "a read error no longer reaches output 0 once alwaysOutputData is gone" is n8n behaviour
 * and is re-measured live in Round B (the R1 stage), not proven here.
 *
 * NEGATIVE CONTROL: pointed at the pre-fix committed export, the read-error cases go RED (the spurious refusal comes
 * back) while the happy, empty, capped and unconfigured cases stay GREEN — so the model reproduces the live finding,
 * and the fix leaves the other paths' outcomes as they were.
 *
 * WHICH FILE: the Purge copy's COMMITTED export, the live reference (promoted from n8n/staged/ by 7-F1 Round B's E1,
 * which put it live and read it back). argv[2] overrides it, for mutants.
 *
 * ⚠ Same accepted security note as validate-intent.test.cjs: this runs `jsCode` from an export via `new Function`.
 *
 * Run: node tests/unit/leads-purge-read-error.test.cjs [purge-export]
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { DateTime } = require(join(__dirname, '../../scripts/node_modules/luxon'));

const EXPORT = process.argv[2] || join(__dirname, '..', '..', 'n8n', 'workflow.purge.copy.sanitized.json');
const wf = JSON.parse(readFileSync(EXPORT, 'utf8'));
const byName = Object.fromEntries(wf.nodes.map((n) => [n.name, n]));
const NOW = DateTime.fromISO('2026-06-15T10:00:00.000Z', { zone: 'utc' });
const COLLECTOR = 'Purge Error (leads)';
const READS = ['Count Leads Total', 'Find Old Leads', 'Count Leads After'];

// ── the fake store: answers ONLY the query shapes below ─────────────────────────────────────────────────
function runSql(store, query, params) {
  const q = query.replace(/\s+/g, ' ').trim();
  const del = q.match(/^DELETE FROM salon\.leads WHERE id = \$1 RETURNING id, true AS deleted$/);
  if (del) {
    const i = store.leads.findIndex((l) => l.id === params[0]);
    if (i < 0) return [];
    store.leads.splice(i, 1);
    store.deleted.push(params[0]);
    return [{ id: params[0], deleted: true }];
  }
  const sel = q.match(/^SELECT (.+?) FROM salon\.leads( WHERE created_at < \$1::timestamptz)?$/);
  if (!sel) throw new Error('the model does not know this query — teach it before trusting a result: ' + q);
  const rows = sel[2] ? store.leads.filter((l) => Date.parse(l.created_at) < Date.parse(params[0])) : store.leads.slice();
  let m;
  if ((m = sel[1].match(/^count\(\*\)::int AS (\w+)$/))) return [{ [m[1]]: rows.length }];
  if ((m = sel[1].match(/^coalesce\(jsonb_agg\(id\), '\[\]'::jsonb\) AS (\w+)$/))) return [{ [m[1]]: rows.map((l) => l.id) }];
  if (/^id, /.test(sel[1])) {   // the pre-fix row-per-lead projection, kept so the negative control can run
    return rows.map((l) => ({ id: l.id, createdTime: l.created_at, fields: { created_at: l.created_at } }));
  }
  throw new Error('the model does not know this projection: ' + sel[1]);
}

const expr = (raw, $, $json) => {
  const m = String(raw).match(/^=\{\{([\s\S]+)\}\}$/);
  if (!m) throw new Error('not an ={{ }} expression: ' + raw);
  return new Function('$', '$json', 'return (' + m[1] + ');')($, $json);
};

function simulate({ leads, retentionDays = 30, failing = [] }) {
  const store = { leads: leads.map((l) => ({ ...l })), deleted: [] };
  const out0 = {};
  const collected = [];
  const $ = (name) => {
    if (name === 'Load Config (Purge)') return { first: () => ({ json: { config: { leadsRetentionDays: retentionDays } } }) };
    if (!(name in out0)) throw new Error(`$('${name}') read before it ran`);
    return { first: () => out0[name][0], all: () => out0[name] };
  };
  let steps = 0;

  function exec(name, items) {
    if (++steps > 50) throw new Error('runaway: the branch did not terminate');
    if (name === COLLECTOR) { collected.push(...items.map((i) => i.json)); return; }
    if (items.length === 0) return;
    const n = byName[name];
    if (!n) throw new Error('unknown node ' + name);
    let outs;
    if (n.type === 'n8n-nodes-base.postgres') {
      if (n.onError !== 'continueErrorOutput') throw new Error(name + ': the model only knows continueErrorOutput');
      const ok = [], err = [];
      for (const it of items) {
        if (failing.includes(name)) {
          err.push({ json: { error: { description: 'fake store failure' }, message: 'permission denied for database "salon"' } });
          continue;
        }
        const qr = n.parameters.options && n.parameters.options.queryReplacement;
        const params = qr ? expr(qr, $, it.json) : [];
        ok.push(...runSql(store, n.parameters.query, params).map((json) => ({ json })));
      }
      if (ok.length === 0 && n.alwaysOutputData === true) ok.push({ json: {} });
      outs = [ok, err];
    } else if (n.type === 'n8n-nodes-base.code') {
      if (n.parameters.mode) throw new Error(name + ': the model only runs "once for all items"');
      const r = new Function('$', '$input', '$json', '$now', 'DateTime', n.parameters.jsCode)(
        $, { all: () => items, first: () => items[0] }, items[0].json, NOW, DateTime);
      outs = [Array.isArray(r) ? r : [r]];
    } else if (n.type === 'n8n-nodes-base.if') {
      const conds = n.parameters.conditions.conditions;
      const op = conds[0].operator;
      if (conds.length !== 1 || op.type !== 'boolean' || op.operation !== 'true') throw new Error(name + ': IF shape unknown');
      const t = [], f = [];
      for (const it of items) (expr(conds[0].leftValue, $, it.json) === true ? t : f).push(it);
      outs = [t, f];
    } else {
      throw new Error(name + ': node type not modelled: ' + n.type);
    }
    out0[name] = outs[0];
    const targets = (wf.connections[name] || {}).main || [];
    targets.forEach((list, idx) => (list || []).forEach((c) => exec(c.node, outs[idx] || [])));
  }

  exec('Compute Leads Cutoff', [{ json: {} }]);
  return { collected, left: store.leads.length, deleted: store.deleted };
}

// Fake leads: ids are placeholders, `created_at` is either 60 days old (past a 30-day cutoff) or 1 day old.
function leads(total, old) {
  return Array.from({ length: total }, (_, i) => ({
    id: 'mig-lead-' + String(i + 1).padStart(2, '0'),
    created_at: NOW.minus({ days: i < old ? 60 : 1 }).toUTC().toISO(),
  }));
}
const refusals = (r) => r.collected.filter((j) => j._leads_refused).map((j) => j._leads_refused);
const errors = (r) => r.collected.filter((j) => j.error !== undefined);

test('the three reads carry no alwaysOutputData, and each still routes its error to output 1', () => {
  for (const name of READS) {
    assert.notEqual(byName[name].alwaysOutputData, true, name + ' still has alwaysOutputData');
    assert.equal(byName[name].onError, 'continueErrorOutput', name + ': its error branch must stay');
    assert.deepEqual(wf.connections[name].main[1].map((c) => c.node), [COLLECTOR], name + ': output 1 must reach the collector');
  }
});

// ── read errors: the bug ────────────────────────────────────────────────────────────────────────────────
test('Count Leads Total fails → ONE error reaches the collector, and no refusal is invented', () => {
  const r = simulate({ leads: leads(10, 1), failing: ['Count Leads Total'] });
  assert.deepEqual(refusals(r), []);
  assert.equal(errors(r).length, 1);
  assert.equal(r.collected.length, 1);
  assert.equal(r.left, 10, 'nothing may be deleted when the total is unknown');
});

test('Find Old Leads fails → ONE error, no "no_candidates" refusal', () => {
  const r = simulate({ leads: leads(10, 1), failing: ['Find Old Leads'] });
  assert.deepEqual(refusals(r), []);
  assert.equal(errors(r).length, 1);
  assert.equal(r.collected.length, 1);
  assert.equal(r.left, 10);
});

test('the store is down (every read fails) → one error item, no refusal, nothing deleted', () => {
  const r = simulate({ leads: leads(10, 1), failing: READS });
  assert.deepEqual(refusals(r), []);
  assert.equal(r.collected.length, 1);
  assert.equal(r.left, 10);
});

test('Count Leads After fails → the error alone; the delete it follows has already happened, as before', () => {
  const r = simulate({ leads: leads(10, 1), failing: ['Count Leads After'] });
  assert.deepEqual(refusals(r), []);
  assert.equal(errors(r).length, 1);
  assert.deepEqual(r.deleted, ['mig-lead-01']);
});

// ── the paths that must not change ──────────────────────────────────────────────────────────────────────
test('happy path: one aged lead in ten is deleted, Verify stays silent', () => {
  const r = simulate({ leads: leads(10, 1) });
  assert.deepEqual(r.collected, []);
  assert.deepEqual(r.deleted, ['mig-lead-01']);
  assert.equal(r.left, 9);
});

test('happy path, several: two aged leads in ten (the cap is exactly 2) are both deleted', () => {
  const r = simulate({ leads: leads(10, 2) });
  assert.deepEqual(r.collected, []);
  assert.deepEqual(r.deleted.sort(), ['mig-lead-01', 'mig-lead-02']);
});

test('empty case: no aged lead still produces ONE no_candidates refusal (today\'s behaviour, kept)', () => {
  const r = simulate({ leads: leads(10, 0) });
  assert.deepEqual(refusals(r), ['no_candidates']);
  assert.equal(r.collected.length, 1);
  assert.equal(r.collected[0].candidates, 0);
  assert.equal(r.collected[0].total, 10);
  assert.equal(r.left, 10);
});

test('empty table: no_candidates, total 0, nothing deleted', () => {
  const r = simulate({ leads: [] });
  assert.deepEqual(refusals(r), ['no_candidates']);
  assert.equal(r.collected[0].total, 0);
});

test('over the cap: five aged in ten (cap 2) is refused as leads_purge_capped, nothing deleted', () => {
  const r = simulate({ leads: leads(10, 5) });
  assert.deepEqual(refusals(r), ['leads_purge_capped']);
  assert.equal(r.collected[0].candidates, 5);
  assert.equal(r.collected[0].cap, 2);
  assert.equal(r.left, 10);
});

test('no retention configured: refused before any read, nothing deleted', () => {
  const r = simulate({ leads: leads(10, 1), retentionDays: null });   // null, not undefined: undefined takes the default
  assert.deepEqual(refusals(r), ['no_retention_configured']);
  assert.equal(r.left, 10);
});
