/**
 * Q18 — the `detail:` line of the Purge and Reminders owner alerts must never read "-object Object-", and must never
 * print what the failed item carries. Offline-proven, error shape measured live (S10, M7).
 *
 * WHY IT EXISTS: under `independently` batching a Postgres error item carries the input's OWN keys plus an `error`
 * OBJECT and no `message` (S10, MIGRATION-PLAN §3r; reproduced on the real copies in D3d W1 and D4c T1). The builders
 * read `(e.error && e.error.message) || e.message || e.error`, so the object itself was printed: `[object Object]`,
 * rendered `-object Object-` by the Markdown escape. The owner learned that something failed and nothing about what.
 * The fix uses a value only when it is a non-empty STRING, and otherwise says what is known: the store failed and
 * the item carried no message.
 *
 * WHAT THE FIXTURES ARE: the error shapes MEASURED live, with fake values —
 *   S10 (`independently` + continueErrorOutput): the input's keys + `error: {}`, no `message`, no SQL text anywhere;
 *   M7 / D4c C1 (`single` + continueErrorOutput): `{error, message}`, `message` = `permission denied for database
 *   "salon"`, `error.description` = "User does not have CONNECT privilege.";
 *   a PII item: the S10 shape whose input keys and error object hold a fake phone and name. The input of `Stamp
 *   Reminded` really does carry the recipient (`would_post.body.participantId`), which is why the builders must
 *   never serialise the item. The inner structure of S10's `error` object was not compared live (§3r), so the PII
 *   fixture puts the fake data in BOTH places.
 *
 * WHICH FILE: the Purge and Reminders COMMITTED copy exports, the live references (promoted from n8n/staged/ by 7-F1
 * Round B's E1 and E2, each put live and read back). argv[2] / argv[3] override them (Purge / Reminders), so a mutant
 * export can be pointed at.
 *
 * ⚠ Same accepted security note as validate-intent.test.cjs: this runs `jsCode` from an export via `new Function`. A
 * PR touching the workflow JSON is a CODE change and must be read as one.
 *
 * Run: node tests/unit/owner-alert-detail.test.cjs [purge-export] [reminders-export]
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');

const N8N = join(__dirname, '..', '..', 'n8n');
const PURGE = process.argv[2] || join(N8N, 'workflow.purge.sanitized.json');
const REMINDERS = process.argv[3] || join(N8N, 'workflow.reminders.sanitized.json');

function builder(exportPath, nodeName, configNode) {
  const wf = JSON.parse(readFileSync(exportPath, 'utf8'));
  const src = wf.nodes.find((n) => n.name === nodeName).parameters.jsCode;
  const fn = new Function('$', '$input', '$getWorkflowStaticData', src);
  // One run = one alert: fresh static data each time, so the throttle never hides a case.
  return (items) => {
    const $ = (name) => {
      if (name !== configNode) throw new Error('unexpected node reference: ' + name);
      return { first: () => ({ json: { config: { ownerAlert: { enabled: true, throttleMinutes: 30 } } } }) };
    };
    const out = fn($, { all: () => items, first: () => items[0] }, () => ({}));
    assert.equal(out.length, 1, 'the builder must produce exactly one alert');
    return out[0].json.owner_alert_text;
  };
}
const detailOf = (text) => (text.split('\n').find((l) => l.startsWith('detail: ')) || '').slice('detail: '.length);

const FAKE_PHONE = '+43 000 0000000';
const FAKE_NAME = 'Testname';
const STORE_ERROR = 'store error (item carried no message)';

// S10: the input's own keys + an `error` object, no `message`. For Purge the input is a `Find Old Processed` row.
const s10Purge = (extra = {}) => ({ json: {
  id: 'recAAAAAAAAAAAAAA', createdTime: '2026-01-01T00:00:00.000Z', fields: { message_id: 'mig-fake-1' },
  error: {}, _purge_branch: 'processed_messages', ...extra } });
// S10 for Reminders `stamp`: the input is the send step's output, which carries the recipient.
const s10Stamp = (extra = {}) => ({ json: {
  recordId: 'recAAAAAAAAAAAAAA', _dry_run: true,
  would_post: { body: { participantId: FAKE_PHONE, templateParams: ['Testservice', 'Monday 1 Jan 10:00'] } },
  error: {}, _reminder_branch: 'stamp', ...extra } });
// M7 / D4c C1: `{error, message}` only.
const m7 = (branchKey, branch) => ({ json: {
  error: { description: 'User does not have CONNECT privilege.' },
  message: 'permission denied for database "salon"', [branchKey]: branch } });
const pii = (base) => ({ json: { ...base.json,
  customer_name: FAKE_NAME, fields: { customer_name: FAKE_NAME, phone: FAKE_PHONE },
  error: { description: 'Key (phone)=(' + FAKE_PHONE + ') rejected', detail: FAKE_NAME, row: { phone: FAKE_PHONE } } } });

const CASES = [
  ['Purge', builder(PURGE, 'Build Owner Alert (Purge)', 'Load Config (Purge)'),
    { s10: s10Purge, m7: () => m7('_purge_branch', 'leads') }],
  ['Reminders', builder(REMINDERS, 'Build Owner Alert (Reminders)', 'Load Config (Reminders)'),
    { s10: s10Stamp, m7: () => m7('_reminder_branch', 'lookup') }],
];

for (const [label, run, fx] of CASES) {
  test(`${label}: the S10 shape (error object, no message) names a store error, never "-object Object-"`, () => {
    const d = detailOf(run([fx.s10()]));
    assert.equal(d, STORE_ERROR);
    assert.doesNotMatch(run([fx.s10()]), /object Object/);
  });

  test(`${label}: the M7 shape ({error, message}) shows the store's own reason`, () => {
    assert.equal(detailOf(run([fx.m7()])), 'permission denied for database "salon"');
  });

  test(`${label}: a fake phone and name in the item (input keys AND error object) never reach the alert`, () => {
    const text = run([pii(fx.s10())]);
    assert.equal(detailOf(text), STORE_ERROR);
    for (const needle of [FAKE_PHONE, '0000000', FAKE_NAME, 'Testservice', 'participantId', 'description']) {
      assert.ok(!text.includes(needle), `the alert carries "${needle}":\n${text}`);
    }
  });

  test(`${label}: only a non-empty STRING is used — error.message first, then message, then a string error`, () => {
    assert.equal(detailOf(run([fx.s10({ error: { message: 'boom from error.message' } })])), 'boom from error.message');
    assert.equal(detailOf(run([fx.s10({ error: { message: '   ' }, message: 'top-level message' })])), 'top-level message');
    assert.equal(detailOf(run([fx.s10({ error: 'plain string error' })])), 'plain string error');
    assert.equal(detailOf(run([fx.s10({ error: { message: 42 }, message: { nested: 'object' } })])), STORE_ERROR);
  });

  test(`${label}: a long message is cut to 300 characters`, () => {
    const d = detailOf(run([fx.s10({ message: 'x'.repeat(1000) })]));
    assert.equal(d.length, 300);
  });
}

// The negative control on the other side: an item with NO `error` key is a refusal (the leads branch's
// `_leads_refused`), not a store failure. It kept the 'unknown' it always had, and must not be relabelled.
test('Purge: a refusal item (no error key) still reads "unknown", not a store error', () => {
  const run = CASES[0][1];
  const text = run([{ json: { _purge_branch: 'leads', _leads_refused: 'no_candidates', candidates: 0, cap: 1, total: 5 } }]);
  assert.equal(detailOf(text), 'unknown');
});
