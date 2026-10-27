/**
 * `Shape Drill State` MUST NOT CALL A FAILED READ "NOT FOUND" (migration ruling Q11, 2026-10-19).
 *
 * The drill-state endpoint is run-d11's state oracle. Its two store reads run with
 * onError=continueRegularOutput, so a failed read reaches this node as an ERROR item ({error, message}, no
 * id). The first version filtered by `id` and answered "NOT-FOUND|0" with 200, so two identical error
 * readings made run-d11's "unchanged" checks pass for the wrong reason (measured live 2026-10-19 while the
 * store was down, OPS-5).
 *
 * This runs the node's `jsCode` FROM THE COMMITTED DRILL-STATE COPY EXPORT
 * (`n8n/workflow.drill-state.sanitized.json`; since the D6b cutover the live workflow is the Postgres copy,
 * and the parked original is only the rollback path until D6c) against three kinds of input:
 * an error item → STORE-ERROR · a successful empty read → NOT-FOUND · a record → its state.
 * The "found" path cannot run live while the store is down; this test is its evidence until D3 runs it
 * against Postgres.
 *
 * ⚠ Same accepted security note as validate-intent.test.cjs: this executes `jsCode` from the committed
 * export via `new Function`. A PR touching the workflow JSON is a CODE change and must be read as one.
 *
 * Run: node tests/unit/drill-state-shape.test.cjs   (optional argv[2]: another export, for mutation runs)
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');

const EXPORT = process.argv[2] || join(__dirname, '..', '..', 'n8n', 'workflow.drill-state.sanitized.json');
const wf = JSON.parse(readFileSync(EXPORT, 'utf8'));
const src = wf.nodes.find((n) => n.name === 'Shape Drill State').parameters.jsCode;
const shape = new Function('$', '$input', src);

// The exact item shapes the store nodes emit, as measured in the execution history (keys only). On the copy the
// two Postgres reads build the same `{id, createdTime, fields}` shape in their SELECT (jsonb_build_object), so
// `rec()` is still the shape the node receives — read from the copy's queries, not measured live here.
const ERR = { json: { error: { message: 'store unavailable' }, message: 'store unavailable' } };
const EMPTY = { json: {} };                                   // alwaysOutputData on a 0-row read
const rec = (fields) => ({ json: { id: 'recAAAAAAAAAAAAAA', createdTime: '2026-10-19T00:00:00.000Z', fields } });

function run(convItems, markItems) {
  const $ = (name) => ({
    'Verify Drill Signature': { first: () => ({ json: {} }), all: () => [{ json: {} }] },
    'Read Conversation': { first: () => convItems[0], all: () => convItems },
  }[name]);
  const out = shape($, { all: () => markItems, first: () => markItems[0] });
  return out[0].json.line;
}

test('a failed read is a STORE-ERROR, never NOT-FOUND', () => {
  assert.equal(run([ERR], [ERR]), 'STORE-ERROR|read-conversation+count-markers');
  assert.equal(run([ERR], [EMPTY]), 'STORE-ERROR|read-conversation');
  assert.equal(run([rec({ stage: 'handoff' })], [ERR]), 'STORE-ERROR|count-markers');
});

test('a successful empty read is NOT-FOUND', () => {
  assert.equal(run([EMPTY], [EMPTY]), 'NOT-FOUND|0');
});

test('a record is reported with its state and marker count', () => {
  assert.equal(run([rec({ stage: 'handoff', last_intent: 'handoff' })], [rec({}), rec({})]), 'handoff|handoff|2');
  assert.equal(run([rec({ stage: 'new' })], [EMPTY]), 'new||0');
});
