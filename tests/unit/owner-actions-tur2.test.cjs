/**
 * The single Owner Actions edit of Phase 7-2 Tur 2 (Codex 7-2 CRT 11: O1 the delayed duplicate, O3 the lookup error,
 * O4 the failure texts, and the DEAD post-write marker chain). Offline: the changed Code nodes and expressions run from
 * the STAGED export with fake inputs; the graph claims are read from it.
 * WHICH FILE: n8n/staged/workflow.owner-actions.copy.sanitized.json; argv[2] overrides it, for mutants.
 * What it does NOT prove: the statement's behaviour on Postgres under concurrency — tests/db/claim-race.test.sh runs
 * that SQL verbatim, in two sessions, as salon_app.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');

const EXPORT = process.argv[2] || join(__dirname, '..', '..', 'n8n', 'staged', 'workflow.owner-actions.copy.sanitized.json');
const wf = JSON.parse(readFileSync(EXPORT, 'utf8'));
const node = (name) => wf.nodes.find((n) => n.name === name);
const stub = (refs) => (name) => {
  if (!(name in refs)) throw new Error(`Referenced node is unexecuted: ${name}`);
  return { first: () => ({ json: refs[name] }) };
};
const expr = (v) => String(v).replace(/^=\{\{/, '').replace(/\}\}$/, '');
const evalExpr = (v, $json, refs = {}) => new Function('$', '$json', `return (${expr(v)});`)(stub(refs), $json);
const CTX = { action: 'release_handoff', record_id: 'recAAAAAAAAAAAAAA', messageId: 'd11-1-abc', ts: 1 };

test('O1: one statement — claim, then release only if claimed AND still the same handoff, else one sentinel row', () => {
  const p = node('Release Handoff Lock').parameters;
  assert.match(p.query, /^WITH claim AS \(INSERT INTO salon\.processed_messages \(message_id, sender_key, channel\) VALUES \(\$3, 'owner:dashboard', 'owner'\) ON CONFLICT \(message_id\) DO NOTHING RETURNING 1\)/);
  assert.match(p.query, /UPDATE salon\.conversations SET stage = 'new', last_intent = '' WHERE id = \$1 AND stage = 'handoff' AND salon\.at_ts\(last_updated\) = \$2 AND EXISTS \(SELECT 1 FROM claim\)/);
  assert.match(p.query, /UNION ALL SELECT NULL::text AS id, NULL::text AS "createdTime", jsonb_build_object\('released', false, 'conflict', CASE WHEN EXISTS \(SELECT 1 FROM claim\) THEN 'state_changed' ELSE 'replay' END\) AS fields WHERE NOT EXISTS \(SELECT 1 FROM upd\)$/);
  assert.doesNotMatch(p.query, /SET[^W]*last_updated\s*=/, 'no last_updated bump: the purge 30-day clock reads it');
  assert.equal(p.options.queryReplacement, '={{ [$json.target_record, $json.target_last_updated, $json.messageId] }}');
});
test('O1: the sentinel row does NOT satisfy Release Wrote?; a released row does; an error item does not', () => {
  const cond = node('Release Wrote?').parameters.conditions.conditions[0].leftValue;
  assert.equal(evalExpr(cond, { id: null, createdTime: null, fields: { released: false, conflict: 'replay' } }), false);
  assert.equal(evalExpr(cond, { id: null, createdTime: null, fields: { released: false, conflict: 'state_changed' } }), false);
  assert.equal(evalExpr(cond, { id: 'recAAAAAAAAAAAAAA', fields: { stage: 'new' } }), true);
  assert.equal(evalExpr(cond, { error: { message: 'x' } }), false);
});
const vrt = (items) => new Function('$', '$input', node('Validate Release Target').parameters.jsCode)(
  stub({ 'Validate Owner Action': CTX }), { all: () => items.map((json) => ({ json })) })[0].json;
test('O1/O3: Validate Release Target carries the version token it read, and a lookup ERROR as store_error', () => {
  const now = new Date().toISOString();
  const row = vrt([{ id: 'recAAAAAAAAAAAAAA', fields: { stage: 'handoff', last_updated: now } }]);
  assert.equal(row.target_last_updated, now);
  assert.equal(row.store_error, false);
  assert.equal(row.target_locked, true);
  const err = vrt([{ error: { message: 'connection terminated' } }]);
  assert.equal(err.store_error, true);
  assert.equal(err.target_found, false);
  assert.equal(err.target_last_updated, '');
  const none = vrt([{}]);
  assert.equal(none.store_error, false, 'an empty read is not a store error');
});
test('O3: Reject Missing Target answers 503 store_unavailable on a lookup error, 404 not_found otherwise', () => {
  const p = node('Reject Missing Target').parameters;
  assert.equal(evalExpr(p.options.responseCode, { store_error: true }), 503);
  assert.deepEqual(evalExpr(p.responseBody, { store_error: true }), { ok: false, error: 'store_unavailable' });
  assert.equal(evalExpr(p.options.responseCode, { store_error: false }), 404);
  assert.deepEqual(evalExpr(p.responseBody, { store_error: false }), { ok: false, error: 'not_found' });
});
const failText = ($json, refs) => new Function('$', '$json', node('Build Release Failure Alert').parameters.jsCode)(
  stub({ 'Owner Replay Seen?': { target_record: 'recAAAAAAAAAAAAAA' }, ...refs }), $json)[0].json.owner_alert_text;
test('O4: three honest texts — written-but-unverified, nothing-written (replay / changed), write failed', () => {
  assert.match(failText({ error: { message: 'read failed' } }, { 'Re-read Released Conversation': {} }), /WRITTEN but could not be verified/);
  assert.match(failText({ id: null, fields: { released: false, conflict: 'replay' } }, {}), /duplicate of a request already handled/);
  assert.match(failText({ id: null, fields: { released: false, conflict: 'state_changed' } }, {}), /changed after the dashboard read it/);
  assert.match(failText({ error: { message: 'permission denied' } }, {}), /write FAILED — the lock was NOT opened/);
});
test('DEAD: the post-write marker chain is gone; a verified release goes straight to the success alert', () => {
  for (const n of ['Record Owner Action Processed', 'Marker Written?', 'Build Marker Failure Alert',
    'Send Marker Failure Alert (Telegram)', 'Respond Owner OK (Marker Unwritten)']) {
    assert.equal(node(n), undefined, n);
    assert.ok(!JSON.stringify(wf).includes(n), `${n} is still named somewhere`);
  }
  assert.ok(!JSON.stringify(wf).includes('marker_unwritten'));
  assert.deepEqual(wf.connections['Write Verified?'].main[0].map((e) => e.node), ['Build Owner Alert (Release)']);
  assert.deepEqual(wf.connections['Write Verified?'].main[1].map((e) => e.node), ['Build Release Failure Alert']);
});
test('DEAD: no note still calls the release safe because the write is idempotent', () => {
  const s4 = node('Sticky — 4').parameters.content;
  assert.ok(!/IDEMPOTENT/.test(s4) && /ONE statement/.test(s4));
  assert.ok(!/What makes it safe is that\s*\n?\/\/ the write is idempotent/.test(node('Owner Replay Seen?').parameters.jsCode));
});
