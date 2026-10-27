/**
 * The reschedule-orphan owner alert names the OLD slot — and nothing that identifies the customer or the event
 * (7-F1, from D2's triage).
 *
 * WHY IT EXISTS: when a reschedule moved the booking but deleting the OLD calendar event failed, `Build Reschedule
 * Orphan State` handed off with `reschedule_orphan` and the owner was asked to remove the stray OLD event by hand —
 * while the alert's only slot line was the NEW slot. The owner had to go and find which event to delete. The state
 * now carries the old date, time (shop timezone) and service, and `Build Owner Alert` prints one `old:` line for that
 * class only.
 * ⚠ NEVER the old event id: a full `gcal_event_id` is hex(sender_key|date|time|service), a UTF-8 encoding and not a
 * hash, so it reverses to the sender_key — a bearer credential (.claude/rules/security-secrets.md). Every case below
 * checks that neither event id, nor the record id, reaches the alert.
 *
 * HOW: runs BOTH Code bodies from the export — the orphan state builder, then the alert composer on its output —
 * with the real Luxon (the node converts UTC to the shop timezone, so a winter and a summer date are both checked).
 * Fake data only.
 *
 * WHICH FILE: the STAGED Main export (n8n/staged/, 7-F1 Round A). ⚠ Round B promotes it and repoints EXPORT below at
 * `n8n/workflow.main.sanitized.json`. argv[2] overrides it, for mutants.
 *
 * ⚠ Same accepted security note as validate-intent.test.cjs: this runs `jsCode` from an export via `new Function`.
 *
 * Run: node tests/unit/reschedule-orphan-alert.test.cjs [main-export]
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { DateTime } = require(join(__dirname, '../../scripts/node_modules/luxon'));

const EXPORT = process.argv[2] || join(__dirname, '..', '..', 'n8n', 'workflow.main.sanitized.json');
const wf = JSON.parse(readFileSync(EXPORT, 'utf8'));
const body = (name) => wf.nodes.find((n) => n.name === name).parameters.jsCode;
const orphanState = new Function('$', 'DateTime', body('Build Reschedule Orphan State'));
const ownerAlert = new Function('$', '$json', '$getWorkflowStaticData', body('Build Owner Alert'));

const hex = (s) => Buffer.from(s, 'utf8').toString('hex');
const SENDER = 'widget:w-fake-orphan';
const OLD_EID = hex(SENDER + '|2026-11-03|14:00|cut');   // the shape of a real id, built from fake parts
const NEW_EID = hex(SENDER + '|2026-11-05|15:00|cut');
const RECORD = 'recAAAAAAAAAAAAAA';
const CFG = {
  business: { timezone: 'Europe/Vienna' },
  messageTemplates: { rescheduleDone: 'Moved — your {service} is now {when}.' },
  ownerAlert: { enabled: true, throttleMinutes: 30 },
  bot: { killSwitch: false },
};

function vi() {
  return { sender_key: SENDER, channel: 'widget', state: {
    sender_key: SENDER, channel: 'widget', stage: 'reschedule_confirming', last_intent: 'reschedule',
    slots: { serviceId: 'cut', service: 'Testcut', date: '2026-11-05', time: '15:00' },
    cancel_target_id: RECORD, confirm_turn: '3', recent_messages: '' } };
}

function buildOrphan(startUtc, target) {
  const v = vi();
  const be = { ...v, booking: { eventId: NEW_EID, dateStr: 'Thursday 5 Nov', timeStr: '15:00', serviceName: 'Testcut' },
    _reschedule_target: target === undefined
      ? { recordId: RECORD, gcal_event_id: OLD_EID, calendar_id: 'REPLACE_WITH_CALENDAR_ID', service: 'Testcut', start_utc: startUtc }
      : target };
  const $ = (name) => ({ first: () => ({ json: {
    'Load Config': { config: CFG }, 'Build Reschedule Event Request': be, 'Validate Intent': v }[name] }) });
  return orphanState($, DateTime)[0].json;
}

function alertOf(j) {
  const $ = (name) => {
    if (name !== 'Load Config') throw new Error('unexpected reference ' + name);
    return { first: () => ({ json: { config: CFG } }) };
  };
  const out = ownerAlert($, j, () => ({}));
  return out.length ? out[0].json.owner_alert_text : null;
}
const oldLines = (text) => text.split('\n').filter((l) => l.startsWith('old: '));

test('the orphan state carries the OLD date, time (shop timezone) and service — and only those three', () => {
  const s = buildOrphan('2026-11-03T13:00:00.000Z');          // CET, UTC+1
  assert.deepEqual(s.reschedule_old, { date: '2026-11-03', time: '14:00', service: 'Testcut' });
  assert.ok(!JSON.stringify(s.reschedule_old).includes(OLD_EID), 'the old event id reached reschedule_old');
  assert.equal(s.state.reschedule_old, undefined, 'it must not sit inside `state`, which Save State persists');
  const summer = buildOrphan('2026-07-10T08:00:00.000Z');     // CEST, UTC+2
  assert.equal(summer.reschedule_old.time, '10:00');
});

test('the rest of the orphan state is as it was: handoff, the NEW event id for the row, the customer reply', () => {
  const s = buildOrphan('2026-11-03T13:00:00.000Z');
  assert.equal(s.reschedule_orphan, true);
  assert.equal(s.state.stage, 'handoff');
  assert.equal(s.gcal_event_id, NEW_EID);
  assert.equal(s.computed_reply, 'Moved — your Testcut is now Thursday 5 Nov 15:00.');
});

test('the alert prints exactly one old: line, and no event id or record id', () => {
  const text = alertOf(buildOrphan('2026-11-03T13:00:00.000Z'));
  assert.deepEqual(oldLines(text), ['old: 2026-11-03 14:00 Testcut']);
  for (const needle of [OLD_EID, NEW_EID, RECORD, OLD_EID.slice(0, 16)]) {
    assert.ok(!text.includes(needle), `the alert carries "${needle}"`);
  }
});

test('the old: line is the ONLY difference from the same orphan alert without the reschedule flag', () => {
  const s = buildOrphan('2026-11-03T13:00:00.000Z');
  const withLine = alertOf(s);
  const without = alertOf({ ...s, reschedule_orphan: undefined, orphan_event: true });   // same class: orphan_event
  assert.equal(withLine.split('\n').filter((l) => !l.startsWith('old: ')).join('\n'), without);
});

test('no other class prints it, even when a stray reschedule_old is present', () => {
  const stray = { reschedule_old: { date: '2026-11-03', time: '14:00', service: 'Testcut' } };
  const raceOrphan = { ...vi(), state: { ...vi().state, stage: 'handoff' }, orphan_event: true, gcal_event_id: NEW_EID, ...stray };
  assert.deepEqual(oldLines(alertOf(raceOrphan)), []);
  const handoff = { ...vi(), state: { ...vi().state, stage: 'handoff' }, ...stray };
  assert.deepEqual(oldLines(alertOf(handoff)), []);
});

test('a missing old target still prints the line, visibly unknown — never a silent drop', () => {
  const text = alertOf(buildOrphan(null, null));
  assert.deepEqual(oldLines(text), ['old: unknown unknown unknown']);
});
