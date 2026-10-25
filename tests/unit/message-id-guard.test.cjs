/**
 * THE DRIFT GUARD FOR MAIN'S message_id CHARACTER CLASS (migration ruling Q10, 2026-10-19).
 *
 * `Validate Payload` on Main's public path rejects a client-supplied `message_id` that carries any
 * character outside a strict class, so the identifier cannot break out of the string it is placed in
 * further down. This test reads the condition FROM THE COMMITTED MAIN COPY EXPORT
 * (`n8n/workflow.main.copy.sanitized.json`) — since the D6b cutover the live Main is the Postgres copy, and the
 * parked original is only the rollback path until D6c — and drives its regex over two fixed lists:
 *   - ACCEPT: every id shape this system emits or receives (widget `m-<uuid>`, the regression suite's
 *     `reg-…-<run>` ids, and a WhatsApp `wamid.` shape, which is ASSUMED base64; no real Zernio id was
 *     available, see the ship gate);
 *   - REJECT: the characters that end or escape a string or a formula argument.
 *
 * Proven by mutation in the round it was written, each mutant on its own copy of the export, each RED on
 * the assertion meant for it (clean export: 2/2 pass):
 *   weakened class (`^\S{1,128}$`) → "accepted a hostile id" · unanchored → "must be anchored" ·
 *   condition removed → "no regex condition" · combinator "or" → "combinator and" ·
 *   over-tight class (`^[A-Za-z0-9._-]{1,64}$`) → "rejected a legitimate id" ·
 *   leftValue replaced by a constant → "no regex condition" · a different field (`message_id_raw`) →
 *   "no regex condition" · node disabled → "is disabled" · true/false outputs swapped → "true-output does
 *   not reach Check Processed" · a bypass edge from an upstream node into Check Processed → "has another
 *   feeder".
 *   *(The last five were added after the pre-push audits showed earlier versions passing them.)*
 *
 * Run: node tests/unit/message-id-guard.test.cjs   (optional argv[2]: another export, for mutation runs)
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');

const EXPORT = process.argv[2] || join(__dirname, '..', '..', 'n8n', 'workflow.main.copy.sanitized.json');

const LEFT = "={{ ($json.message_id ?? '').toString() }}";

function guardRegex() {
  const wf = JSON.parse(readFileSync(EXPORT, 'utf8'));
  const vp = wf.nodes.find((n) => n.name === 'Validate Payload');
  assert.ok(vp, 'Validate Payload node is missing');
  assert.notEqual(vp.disabled, true, 'Validate Payload is disabled');
  // The gate only guards Check Processed if its TRUE output (index 0) is what reaches it.
  const outs = (wf.connections['Validate Payload'] || {}).main || [];
  assert.ok((outs[0] || []).some((c) => c.node === 'Check Processed'), 'Validate Payload true-output does not reach Check Processed');
  assert.ok(!(outs[1] || []).some((c) => c.node === 'Check Processed'), 'Check Processed hangs off the FALSE output');
  // ...and nothing else may feed it: a direct edge from any other node would bypass the gate.
  const feeders = Object.entries(wf.connections).filter(([, v]) =>
    ((v || {}).main || []).some((o) => (o || []).some((c) => c.node === 'Check Processed'))).map(([k]) => k);
  assert.deepEqual(feeders, ['Validate Payload'], `Check Processed has another feeder: ${feeders}`);
  const conds = vp.parameters.conditions;
  assert.equal(conds.combinator, 'and', 'the conditions must all hold (combinator "and")');
  // Exact leftValue: a constant, or a different field whose name merely contains "message_id", must not pass.
  const c = conds.conditions.find((x) => x.leftValue === LEFT && x.operator && x.operator.operation === 'regex');
  assert.ok(c, 'no regex condition on message_id in Validate Payload');
  assert.match(c.rightValue, /^\^.*\$$/, 'the class must be anchored at both ends');
  return new RegExp(c.rightValue);
}

const ACCEPT = [
  'm-3f2a1c9e-8b7d-4e6f-9a0b-1c2d3e4f5a6b',
  'reg-idem-1792354460-dup', 'reg-book-1792354460-1', 'reg-abort-1792354460-c1',
  // Synthetic wamid-SHAPED strings (prefix + base64 alphabet). They encode no number and no real message.
  'wamid.SYNTHETICq10TESTONLYabcdef0123=', 'wamid.ABC+def/ghi=',
  'x'.repeat(128),
];
const REJECT = [
  'a"b', "a'b", 'a,b', 'a(b', 'a)b', 'a b', 'a\\b', 'a&b', 'a{b}', 'a\nb', '', 'x'.repeat(129), 'ä',
];

test('every id shape the system uses is accepted', () => {
  const re = guardRegex();
  for (const id of ACCEPT) assert.ok(re.test(id), `rejected a legitimate id: ${JSON.stringify(id)}`);
});

test('every string-terminating or escaping character is rejected', () => {
  const re = guardRegex();
  for (const id of REJECT) assert.ok(!re.test(id), `accepted a hostile id: ${JSON.stringify(id)}`);
});
