/**
 * `Eval Spend` must let the LLM run only on a spend reading it can trust (public demo Ruling (d), 2026-10-29).
 *
 * WHY IT EXISTS: K-SPEND ruled the spend brake fail-OPEN — a missing row or a read error counted as "nothing spent".
 * For a public endpoint that is a brake that releases exactly when it cannot see. The fix (staged in
 * n8n/staged/workflow.main.sanitized.json until it is live) keeps the two trusted readings — a row with a finite,
 * non-negative cost, and the empty item that stands for "no row this month yet" — and closes on everything else.
 *
 * HOW: Eval Spend's code and Spend Gate's IF expression, both taken from the export, run against the outputs Read
 * Spend can produce. What it models of n8n, and where that comes from (the engine and workflow packages matching the
 * live instance, read offline — PUBLIC-DEMO-PLAN "Ruling (d)"):
 *   · a query error under continueErrorOutput is split onto output 1, and `alwaysOutputData` then puts ONE empty item on
 *     output 0, because it looks at output 0 only and runs after the split — so Eval Spend runs on `{}` (the same
 *     behaviour on Purge's reads was measured live, MIGRATION-PLAN §3r D3d R1 finding 2);
 *   · a zero-row SELECT on this Postgres node version returns no item, so "no row" also reaches Eval Spend as `{}`;
 *   · a THROWN error under continueErrorOutput passes the node's input items through on output 0 and stores no
 *     output 1, so `$('Read Spend').all(1)` throws "has no branch with index 1".
 * It is a model: the live behaviour on Read Spend is measured on a scratch workflow in R2 before the put.
 *
 * NEGATIVE CONTROL: the pre-fix Main export (read from git at a pinned commit) runs the same cases, and the
 * read-error and thrown-error cases must come out OPEN there — so the model reproduces the defect it was written for.
 *
 * WHICH FILE: argv[2] if given (mutants), else the staged export when one exists, else the committed export.
 *
 * ⚠ Same accepted security note as validate-intent.test.cjs: this runs `jsCode` from an export via `new Function`.
 *
 * Run: node tests/unit/eval-spend-fail-closed.test.cjs [main-export]
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { existsSync, readFileSync } = require('node:fs');
const { join } = require('node:path');

const ROOT = join(__dirname, '..', '..');
const STAGED = join(ROOT, 'n8n', 'staged', 'workflow.main.sanitized.json');
const EXPORT = process.argv[2] || (existsSync(STAGED) ? STAGED : join(ROOT, 'n8n', 'workflow.main.sanitized.json'));
const PRE_FIX_REV = 'a175bfb';   // the last commit that changed the committed Main export before this fix

const load = (text) => {
  const wf = JSON.parse(text);
  return { wf, byName: Object.fromEntries(wf.nodes.map((n) => [n.name, n])) };
};
const CUR = load(readFileSync(EXPORT, 'utf8'));
const PRE = load(execFileSync('git', ['-C', ROOT, 'show', `${PRE_FIX_REV}:n8n/workflow.main.sanitized.json`], { encoding: 'utf8' }));

const CTX = { channel: 'widget', senderId: 'w-test', sender_key: 'widget:w-test', text: 'hi', state: {} };
const GUARD_ITEM = { json: { ...CTX, _guards: 'passed' } };   // what Read Spend receives (and passes through on a throw)

// Read Spend's possible outputs, as main = [output 0, output 1]; `thrown` stores output 0 only.
const ROW = (cost) => ({ main: [[{ json: { id: 'rec0', createdTime: 'x', fields: { period_key: '2026-10', cost_usd: cost } } }], []] });
const NO_ROW = { main: [[{ json: {} }], []] };
const QUERY_ERROR = { main: [[{ json: {} }], [{ json: { message: 'connection refused', error: { message: 'connection refused' } } }]] };
const THROWN = { main: [[GUARD_ITEM]] };

function evalSpend(m, read, cap = 10) {
  const $ = (name) => {
    if (name === 'Merge State') return { first: () => ({ json: CTX }) };
    if (name === 'Load Config') return { first: () => ({ json: { config: { bot: { llmCostCapUsd: cap } } } }) };
    if (name === 'Read Spend') {
      return {
        all: (branch = 0) => {
          if (branch >= read.main.length) throw new Error(`Node "Read Spend" has no branch with index ${branch}.`);
          return read.main[branch];
        },
      };
    }
    throw new Error(`the model does not know $('${name}')`);
  };
  const items = read.main[0];
  const out = new Function('$', '$input', '$json', m.byName['Eval Spend'].parameters.jsCode)(
    $, { all: () => items, first: () => items[0] }, items[0] && items[0].json);
  assert.equal(out.length, 1, 'Eval Spend returns one item');
  return out[0].json;
}

// Spend Gate's own IF, from the export: its single boolean condition, then the output it routes to.
function gate(m, json) {
  const conds = m.byName['Spend Gate'].parameters.conditions.conditions;
  assert.equal(conds.length, 1);
  assert.equal(conds[0].operator.operation, 'true');
  const expr = conds[0].leftValue.match(/^=\{\{([\s\S]+)\}\}$/)[1];
  const branch = new Function('$json', `return (${expr});`)(json) === true ? 0 : 1;
  return m.wf.connections['Spend Gate'].main[branch].map((c) => c.node);
}
const LLM = ['Build LLM Request'];
const CLOSED = ['Build Spend-Cap Reply'];
const route = (m, read, cap) => gate(m, evalSpend(m, read, cap));

test('premise: Read Spend still carries alwaysOutputData + continueErrorOutput, and Spend Gate still routes 0 → LLM, 1 → the cap reply', () => {
  const rs = CUR.byName['Read Spend'];
  assert.equal(rs.alwaysOutputData, true);
  assert.equal(rs.onError, 'continueErrorOutput');
  assert.deepEqual(CUR.wf.connections['Read Spend'].main[0].map((c) => c.node), ['Eval Spend']);
  assert.deepEqual(CUR.wf.connections['Spend Gate'].main.map((o) => o.map((c) => c.node)), [LLM, CLOSED]);
});

test('the edit changes Eval Spend\'s code and only TEXT elsewhere: the meter alert\'s comment lines and the sticky', () => {
  const differs = CUR.wf.nodes.filter((n) => JSON.stringify(n) !== JSON.stringify(PRE.byName[n.name])).map((n) => n.name).sort();
  if (EXPORT === STAGED) assert.deepEqual(differs, ['Build Spend-Meter Alert', 'Eval Spend', 'Spend-cap note']);
  const code = (m) => m.byName['Build Spend-Meter Alert'].parameters.jsCode.split('\n').filter((l) => !/^\s*\/\//.test(l)).join('\n');
  assert.equal(code(CUR), code(PRE), 'Build Spend-Meter Alert: everything but its comment lines is unchanged');
  assert.equal(CUR.byName['Spend-cap note'].type, 'n8n-nodes-base.stickyNote');
  assert.doesNotMatch(CUR.byName['Spend-cap note'].parameters.content, /Fail-OPEN/, 'the sticky no longer says fail-open');
});

test('trusted readings run the LLM: a row under the cap, a numeric-text cost, and no row this month', () => {
  assert.deepEqual(route(CUR, ROW(3.25)), LLM);
  assert.deepEqual(route(CUR, ROW('4.5')), LLM);
  assert.deepEqual(route(CUR, NO_ROW), LLM);
  assert.deepEqual(evalSpend(CUR, ROW('4.5'))._spend, { prev: 4.5, cap: 10, under: true, meter: 'row' });
  assert.deepEqual(evalSpend(CUR, NO_ROW)._spend, { prev: 0, cap: 10, under: true, meter: 'no_row' });
  assert.equal(evalSpend(CUR, NO_ROW).sender_key, CTX.sender_key, 'the message item is restored from Merge State');
});

test('at or over the cap: closed (the cap itself is not under)', () => {
  assert.deepEqual(route(CUR, ROW(10)), CLOSED);
  assert.deepEqual(route(CUR, ROW(12.5)), CLOSED);
});

test('a query error (empty item on output 0 + the error on output 1): closed, not read as "no row"', () => {
  assert.deepEqual(route(CUR, QUERY_ERROR), CLOSED);
  assert.deepEqual(evalSpend(CUR, QUERY_ERROR)._spend, { prev: null, cap: 10, under: false, meter: 'unreadable' });
});

test('a thrown error (the input passed through, no output 1): closed — whatever item was passed through', () => {
  assert.deepEqual(route(CUR, THROWN), CLOSED);
  // The missing output 1 alone must close it: an empty pass-through item would otherwise read as "no row".
  assert.deepEqual(route(CUR, { main: [[{ json: {} }]] }), CLOSED);
  assert.deepEqual(route(CUR, { main: [ROW(1).main[0]] }), CLOSED);
});

test('a row the meter cannot trust: closed', () => {
  for (const bad of [undefined, null, '', 'abc', '1e2', -1, '-1', Number.NaN, true, [], {}]) {
    assert.deepEqual(route(CUR, ROW(bad)), CLOSED, `cost_usd ${JSON.stringify(bad)}`);
  }
  const noFields = { main: [[{ json: { id: 'rec0', createdTime: 'x' } }], []] };
  assert.deepEqual(route(CUR, noFields), CLOSED, 'a row without fields');
  const odd = { main: [[{ json: { message: 'something else' } }], []] };
  assert.deepEqual(route(CUR, odd), CLOSED, 'an unknown non-empty item with no error output');
  const two = { main: [[ROW(1).main[0][0], ROW(1).main[0][0]], []] };
  assert.deepEqual(route(CUR, two), CLOSED, 'two items where one is expected');
});

test('no cap configured: never blocks (unchanged behaviour, not part of the meter)', () => {
  assert.deepEqual(route(CUR, QUERY_ERROR, 'not-a-number'), LLM);
});

test('NEGATIVE CONTROL: the pre-fix export is fail-OPEN on the read-error and thrown cases, and agrees on the trusted ones', () => {
  assert.deepEqual(route(PRE, QUERY_ERROR), LLM, 'the model must reproduce the fail-open defect on a query error');
  assert.deepEqual(route(PRE, THROWN), LLM, 'the model must reproduce the fail-open defect on a thrown error');
  assert.deepEqual(route(PRE, ROW(3.25)), LLM);
  assert.deepEqual(route(PRE, NO_ROW), LLM);
  assert.deepEqual(route(PRE, ROW(10)), CLOSED);
});
