/**
 * The single Main edit of Phase 7-2 Tur 2 (rulings R-1a, CLAIM-RETRY, DEAD, QB, R-Q1, R-Q2, and R1b's H1, M1, M2,
 * ITEM13, L8; Codex 7-2 findings for CRT 1a, 1b, 2, 6, 12). Offline: every changed Code node and expression is executed from the STAGED export with fake
 * inputs; the graph claims (what was removed, what feeds the new node, the canvas order) are read from the export.
 *
 * WHICH FILE: the STAGED Main export (n8n/staged/). argv[2] overrides it, for mutants.
 * What it does NOT prove: Postgres' claim semantics under concurrency (tests/db/claim-race.test.sh, two sessions) or
 * n8n's runtime — the live window measures that.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { DateTime } = require(join(__dirname, '../../scripts/node_modules/luxon'));

const EXPORT = process.argv[2] || join(__dirname, '..', '..', 'n8n', 'workflow.main.sanitized.json');
const wf = JSON.parse(readFileSync(EXPORT, 'utf8'));
const node = (name) => wf.nodes.find((n) => n.name === name);
const body = (name) => node(name).parameters.jsCode;
const fn = (name, ...args) => new Function(...args, body(name));

const SENDER = 'widget:w-fake-tur2-abcdef';
const CFG = {
  business: { timezone: 'Europe/Vienna' },
  bot: { killSwitch: false, dryRun: false },
  ownerAlert: { enabled: true, throttleMinutes: 30 },
  services: [{ id: 'cut', name: 'Testcut', durationMin: 30 }],
  workingHours: { mon: ['09:00-18:00'], tue: ['09:00-18:00'], wed: ['09:00-18:00'], thu: ['09:00-18:00'], fri: ['09:00-18:00'], sat: [], sun: [] },
  googleCalendarId: 'REPLACE_WITH_CALENDAR_ID',
  messageTemplates: { handoff: 'A person will follow up.', cancelAborted: 'No problem — your booking stands.', cancelUnavailable: 'Cannot cancel now.' },
};
const cfg = (over = {}) => ({ ...CFG, ...over, bot: { ...CFG.bot, ...(over.bot || {}) } });

// $ stub: `refs` maps a node name to its first item json; a name NOT in refs throws, as n8n does for a node that did
// not run in this execution.
const stub = (refs) => (name) => {
  if (!(name in refs)) throw new Error(`Referenced node is unexecuted: ${name}`);
  return { first: () => ({ json: refs[name] }), all: () => [{ json: refs[name] }] };
};
const expr = (v) => v.replace(/^=\{\{/, '').replace(/\}\}$/, '');
const evalExpr = (v, refs, $json = {}) => new Function('$', '$json', 'DateTime', `return (${expr(v)});`)(stub(refs), $json, DateTime);

let sd;
function alert(j, config = cfg(), ran = {}) {
  const out = fn('Build Owner Alert', '$', '$json', '$getWorkflowStaticData')(stub({ 'Load Config': { config }, ...ran }), j, () => sd);
  return out.length ? out[0].json : null;
}
const fresh = () => { sd = {}; };
const reply = (name) => node('Build Reply Payload').parameters.assignments.assignments.find((a) => a.name === name);

// ── F1 · R-1a: claim-first ───────────────────────────────────────────────────────────────────────────────────
test('F1: Check Processed CLAIMS the id in one statement (INSERT … ON CONFLICT (message_id) DO NOTHING RETURNING), no SELECT', () => {
  const p = node('Check Processed').parameters;
  assert.match(p.query, /^INSERT INTO salon\.processed_messages \(message_id, sender_key, channel\) VALUES \(\$1, \$2, \$3\) ON CONFLICT \(message_id\) DO NOTHING RETURNING id/);
  assert.doesNotMatch(p.query, /\bSELECT\b[^(]*\bFROM salon\.processed_messages\b/, 'a separate read would reopen the race');
  assert.equal(p.options.queryReplacement, '={{ [$json.message_id, $json.sender_key, $json.channel] }}');
  assert.equal(node('Check Processed').alwaysOutputData, true, 'no row must still reach Dedupe Gate');
});
test('F1: Dedupe Gate — a returned row = claimed (not a duplicate); the empty alwaysOutputData item = already claimed', () => {
  const gate = fn('Dedupe Gate', '$', '$json');
  const $ = stub({ 'Normalize Inbound': { message_id: 'm-1', sender_key: SENDER } });
  assert.equal(gate($, { id: 'recAAAAAAAAAAAAAA' })[0].json._duplicate, false);
  assert.equal(gate($, {})[0].json._duplicate, true);
});
test('DEAD: Record Processed, Build Dedupe-Marker Alert and the dedupe_marker_failed class are gone, and nothing names them', () => {
  for (const n of ['Record Processed', 'Build Dedupe-Marker Alert']) assert.equal(node(n), undefined, n);
  const all = JSON.stringify(wf);
  for (const s of ["'Record Processed'", '"Record Processed"', 'Build Dedupe-Marker Alert', 'dedupe_marker_failed']) {
    assert.ok(!all.includes(s), `${s} is still referenced`);
  }
});

// ── CLAIM-RETRY ──────────────────────────────────────────────────────────────────────────────────────────────
function reachable(from) {
  const seen = new Set([from]); const q = [from];
  while (q.length) { const x = q.shift(); for (const lst of (wf.connections[x]?.main || [])) for (const e of lst || []) if (!seen.has(e.node)) { seen.add(e.node); q.push(e.node); } }
  return seen;
}
test('CLAIM-RETRY: no node reachable after the claim answers with a literal 5xx', () => {
  const post = reachable('Dedupe Gate');
  const lit = wf.nodes.filter((n) => post.has(n.name) && /_outbound_status:\s*5\d\d\b/.test(n.parameters.jsCode || '')).map((n) => n.name);
  assert.deepEqual(lit, []);
  const rc = wf.nodes.filter((n) => post.has(n.name) && n.type === 'n8n-nodes-base.respondToWebhook' && /^5/.test(String(n.parameters.options?.responseCode)));
  assert.deepEqual(rc.map((n) => n.name), []);
});
test('CLAIM-RETRY: the four infra replies answer 200 with their error flag and a reply', () => {
  for (const [n, err] of [['LLM Unavailable Reply', 'llm_unavailable'], ['Lead Unavailable Reply', 'lead_unavailable'],
    ['Calendar Unavailable Reply', 'calendar_unavailable'], ['Cancel Delete Unavailable Reply', 'calendar_unavailable']]) {
    const j = fn(n, '$', '$json')(stub({ 'Load Config': { config: cfg() } }), {})[0].json;
    assert.equal(j._outbound_status, 200, n);
    assert.equal(j._outbound_body.error, err, n);
    assert.ok(j._outbound_body.reply, `${n} carries no reply`);
  }
});
test('CLAIM-RETRY: Send Error Response — 200 + reply after the claim; 503 when nothing was claimed (Dedupe Gate did not run)', () => {
  const ser = fn('Send Error Response', '$', '$json');
  const after = ser(stub({ 'Load Config': { config: cfg() }, 'Dedupe Gate': { _duplicate: false } }), {})[0].json;
  assert.equal(after._outbound_status, 200);
  assert.equal(after._outbound_body.reply, 'A person will follow up.');
  const before = ser(stub({ 'Load Config': { config: cfg() } }), {})[0].json;
  assert.equal(before._outbound_status, 503);
  assert.equal(before._outbound_body.reply, undefined);
});
test('CLAIM-RETRY: a mid-flow failure alerts the owner, and the same-messageId retry is a duplicate', () => {
  fresh();
  const first = fn('LLM Unavailable Reply', '$', '$json')(stub({ 'Load Config': { config: cfg() } }), { sender_key: SENDER, channel: 'widget' })[0].json;
  assert.equal(first._outbound_status, 200);
  assert.equal(alert(first)._alert_class, 'llm_unavailable', "the first run's alert must fire");
  // The retry: the claim INSERT returns no row (the id is already claimed) → alwaysOutputData's empty item.
  const retry = fn('Dedupe Gate', '$', '$json')(stub({ 'Normalize Inbound': { message_id: 'm-1', sender_key: SENDER } }), {})[0].json;
  assert.equal(retry._duplicate, true);
  assert.deepEqual(node('Is Duplicate') && wf.connections['Is Duplicate'].main[0].map((e) => e.node), ['Idempotent Replay']);
});

// ── F2: a clean race loss reaches the owner ────────────────────────────────────────────────────────────────────
test('F2: race_lost is true when a race-lost builder ran, false when neither ran (guarded refs)', () => {
  assert.equal(evalExpr(reply('race_lost').value, { 'Build Race-Lost State': {} }), true);
  assert.equal(evalExpr(reply('race_lost').value, { 'Build Reschedule Race-Lost State': {} }), true);
  assert.equal(evalExpr(reply('race_lost').value, {}), false);
});
test('F2: the reply item with race_lost alerts as race_lost', () => {
  fresh();
  assert.equal(alert({ sender_key: SENDER, channel: 'widget', stage: 'handoff', race_lost: true })._alert_class, 'race_lost');
  fresh();
  assert.equal(alert({ sender_key: SENDER, channel: 'widget', stage: 'handoff', race_lost: false }), null, 'without the flag the reply item stays silent');
});

// ── F3: freeBusy errors and empty answers are not availability ─────────────────────────────────────────────────
function avail(calendars) {
  const st = { stage: 'ready', slots: { serviceId: 'cut', date: '2030-01-07', time: '10:00' } };
  const $ = stub({ 'Load Config': { config: cfg() }, 'Slot Gate': { state: st } });
  return fn('Compute Availability', '$', '$json', 'DateTime')($, calendars === undefined ? {} : { calendars }, DateTime)[0].json;
}
test('F3: a calendar-level errors array, a missing or empty calendars object, or no busy list throws calendar_error', () => {
  for (const [label, c] of [['errors', { a: { errors: [{ domain: 'global', reason: 'notFound' }] } }], ['empty object', {}], ['missing', undefined],
    ['no busy list', { a: {} }], ['second calendar errors', { a: { busy: [] }, b: { errors: [{ reason: 'internalError' }] } }],
    ['errors beside an empty busy list', { a: { busy: [], errors: [{ domain: 'global', reason: 'notFound' }] } }]]) {
    assert.throws(() => avail(c), /calendar_error/, label);
  }
});
test('F3: busy is read from EVERY calendar; a clean answer is still available', () => {
  assert.equal(avail({ a: { busy: [] }, b: { busy: [{ start: '2030-01-07T09:00:00Z', end: '2030-01-07T09:30:00Z' }] } }).availability.status, 'busy');
  assert.equal(avail({ a: { busy: [] } }).availability.status, 'available');
});

// ── F4: dry-run writes nothing on cancel / reschedule ─────────────────────────────────────────────────────────
test('F4: Confirm Live? is false in dry-run even when the target is live', () => {
  const left = node('Confirm Live?').parameters.conditions.conditions[0].leftValue;
  assert.equal(evalExpr(left, { 'Load Config': { config: cfg({ bot: { dryRun: true } }) } }, { _confirm_live: true }), false);
  assert.equal(evalExpr(left, { 'Load Config': { config: cfg() } }, { _confirm_live: true }), true);
});
const VI = (over = {}) => ({ sender_key: SENDER, channel: 'widget', intent: 'confirm', slots: {}, state: {
  sender_key: SENDER, channel: 'widget', stage: 'cancel_confirming', cancel_target_id: 'recAAAAAAAAAAAAAA', confirm_turn: '4', turn_count: 4,
  slots: { serviceId: 'cut', service: 'Testcut', date: '2030-01-08', time: '11:00' }, ...over } });
test('F4: a confirmed cancel refused by dry-run says nothing was changed', () => {
  const j = fn('Build Cancel-Aborted State', '$', '$json')(stub({ 'Load Config': { config: cfg({ bot: { dryRun: true } }) }, 'Validate Intent': VI() }), {})[0].json;
  assert.match(j.computed_reply, /Test mode: nothing was changed/);
  assert.equal(j.state.stage, 'new');
});
test('F4: dry-run reschedule builds an empty event id (→ Mark Handoff; no insert, so no delete of the old event)', () => {
  const j = fn('Build Reschedule Event Request', '$', '$json', 'DateTime')(stub({ 'Load Config': { config: cfg({ bot: { dryRun: true } }) },
    'Validate Intent': VI({ stage: 'reschedule_confirming' }) }), { _reschedule_target: {} }, DateTime)[0].json;
  assert.equal(j.booking.eventId, '');
  assert.deepEqual(wf.connections['Reschedule Event ID Valid?'].main[1].map((e) => e.node), ['Mark Handoff']);
});

// ── F5: a lost reschedule insert answer ───────────────────────────────────────────────────────────────────────
test('F5: insert-failed is its own class with the NEW slot, a masked customer, no event id, and the original kept', () => {
  const v = VI({ stage: 'reschedule_confirming' });
  const j = fn('Build Reschedule Insert-Failed State', '$')(stub({ 'Load Config': { config: cfg() }, 'Validate Intent': v }))[0].json;
  assert.equal(j.reschedule_insert_unknown, true);
  assert.equal(j.gcal_event_id, undefined, "the conversation's event reference must keep pointing at the booking that stands");
  fresh();
  const a = alert(j);
  assert.equal(a._alert_class, 'reschedule_insert_unknown');
  assert.match(a.owner_alert_text, /possible extra event at the NEW slot/);
  assert.match(a.owner_alert_text, /slots: Testcut \/ 2030-01-08 \/ 11:00/);
  assert.ok(!a.owner_alert_text.includes(SENDER), 'the customer must be masked');
  assert.match(a.owner_alert_text, /sender: widget:w-fake…\n/);
});

// ── F6: the confirm turn's own date — visible, never vetoed ────────────────────────────────────────────────────
function eventReq(name, said, extra = {}) {
  const refs = { 'Load Config': { config: cfg() }, 'Validate Intent': VI({ stage: 'confirming' }) };
  if (said !== undefined) refs['Resolve Date'] = { slots: { date: said } };
  return fn(name, '$', '$json', 'DateTime')(stub(refs), extra, DateTime)[0].json;
}
test('F6: booking — a different date said on the confirm turn still books the SHOWN slot and carries date_change', () => {
  const j = eventReq('Build Event Request', '2030-01-09');
  assert.ok(j.booking.eventId, 'the shown slot is still booked (no veto, ARCH-DEC 2026-09-09e)');
  assert.deepEqual(j.date_change, { booked: '2030-01-08 11:00 cut', said: '2030-01-09' });
  assert.equal(eventReq('Build Event Request', '2030-01-08').date_change, null, 'the same date is not a change');
  assert.equal(eventReq('Build Event Request', null).date_change, null, 'a plain "yes" says no date');
  assert.equal(eventReq('Build Event Request', undefined).date_change, null, 'Resolve Date not run → nothing said');
});
test('F6: reschedule — "yes, from <the old day>" is not a change; another date is', () => {
  const tgt = { _reschedule_target: { start_utc: '2030-01-07T09:00:00.000Z' } };   // 10:00 Vienna on the 7th
  assert.equal(eventReq('Build Reschedule Event Request', '2030-01-07', tgt).date_change, null);
  assert.deepEqual(eventReq('Build Reschedule Event Request', '2030-01-10', tgt).date_change, { booked: '2030-01-08 11:00 cut', said: '2030-01-10' });
});
test('F6: date_change reaches the reply item (guarded); its own class only after a clean booking (R1b H1)', () => {
  const d = { booked: '2030-01-08 11:00 cut', said: '2030-01-09' };
  assert.deepEqual(evalExpr(reply('date_change').value, { 'Build Event Request': { date_change: d } }), d);
  assert.equal(evalExpr(reply('date_change').value, {}), null, 'neither builder ran');
  for (const clean of ['Build Booked State', 'Build Reschedule-Done State']) {
    fresh();
    const a = alert({ sender_key: SENDER, channel: 'widget', stage: 'booked', date_change: d }, cfg(), { [clean]: {} });
    assert.equal(a._alert_class, 'date_changed_on_confirm', clean);
    assert.match(a.owner_alert_text, /date on confirm: shown slot 2030-01-08 11:00 cut · customer said 2030-01-09/);
  }
  fresh();
  assert.equal(alert({ sender_key: SENDER, channel: 'widget', stage: 'booked', date_change: d }), null,
    'no clean booking (e.g. the mirror failed: Build Mirror-Failed State ran instead) → no date_change class');
});

// ── F7: a failed cancel re-read keeps the pending cancel and alerts ────────────────────────────────────────────
test('F7: the re-read error keeps cancel_confirming, moves confirm_turn to the next turn, flags it', () => {
  const j = fn('Build Cancel-Aborted State', '$', '$json')(stub({ 'Load Config': { config: cfg() }, 'Validate Intent': VI() }),
    { error: { message: 'connection terminated' } })[0].json;
  assert.equal(j.cancel_reread_failed, true);
  assert.equal(j.state.stage, 'cancel_confirming');
  assert.equal(j.state.cancel_target_id, 'recAAAAAAAAAAAAAA');
  assert.equal(j.state.confirm_turn, '5');
  const fresh_ = node('Confirm Fresh?').parameters.conditions.conditions[0].leftValue;
  assert.equal(evalExpr(fresh_, {}, { state: { ...j.state, turn_count: 5 } }), true, 'the next "yes" must pass Confirm Fresh?');
});
test('F7: the flag reaches the reply item (guarded) and alerts as its own class', () => {
  assert.equal(evalExpr(reply('cancel_reread_failed').value, { 'Build Cancel-Aborted State': { cancel_reread_failed: true } }), true);
  assert.equal(evalExpr(reply('cancel_reread_failed').value, { 'Build Cancel-Aborted State': {} }), false);
  assert.equal(evalExpr(reply('cancel_reread_failed').value, {}), false, 'Build Cancel-Aborted State not run');
  fresh();
  assert.equal(alert({ sender_key: SENDER, channel: 'widget', stage: 'cancel_confirming', cancel_reread_failed: true })._alert_class, 'cancel_reread_failed');
});

// ── F8: the failure's own message, masked ──────────────────────────────────────────────────────────────────────
test('F8: detail line — stringified, cut at 200, sender_key and long digit runs masked; none for Turnstile', () => {
  fresh();
  const msg = 'permission denied for widget:w-secret-session-xyz near 06601234567 ' + 'x'.repeat(400);
  const a = alert({ _outbound_kind: 'Send Error Response', sender_key: SENDER, error: { message: msg } });
  const line = a.owner_alert_text.split('\n').find((l) => l.startsWith('detail: '));
  assert.ok(line, 'no detail line');
  assert.ok(!line.includes('secret-session') && !line.includes('06601234567'), line);
  assert.ok(line.length <= 'detail: '.length + 200);
  fresh();
  const t = alert({ alert_class: 'turnstile_unavailable', sender_key: SENDER, error: { message: msg } });
  assert.ok(!t.owner_alert_text.includes('detail: '));
});

// ── R-Q1: verify_unavailable names the possible overlap ───────────────────────────────────────────────────────
test('R-Q1: the verify_unavailable alert carries the slot, a masked customer and the possible-overlap line, no event id', () => {
  fresh();
  const eid = Buffer.from(SENDER + '|2030-01-08|11:00|cut').toString('hex');
  const a = alert({ verify_unavailable: true, gcal_event_id: eid, state: { sender_key: SENDER, channel: 'widget', stage: 'handoff',
    slots: { serviceId: 'cut', service: 'Testcut', date: '2030-01-08', time: '11:00' } } });
  assert.equal(a._alert_class, 'verify_unavailable');
  assert.match(a.owner_alert_text, /possible overlap/);
  assert.match(a.owner_alert_text, /slots: Testcut \/ 2030-01-08 \/ 11:00/);
  assert.ok(!a.owner_alert_text.includes(SENDER));
  assert.ok(!a.owner_alert_text.includes(eid.slice(-8)), 'no event id fragment');
});

// ── R-Q2: Tag Turnstile Unavailable ────────────────────────────────────────────────────────────────────────────
const tag = (items, refs = { 'Normalize Inbound': { sender_key: SENDER } }) =>
  fn('Tag Turnstile Unavailable', '$', '$input')(stub(refs), { all: () => items.map((json) => ({ json })) });
test('R-Q2 + R1b M2: fail-closed — silent ONLY when every code is a known bot/client rejection; everything else emits', () => {
  assert.equal(tag([{ error: { message: 'ETIMEDOUT' } }])[0].json.turnstile_reason, 'transport');
  for (const codes of [['invalid-input-response'], ['missing-input-response'], ['timeout-or-duplicate'],
    ['invalid-input-response', 'timeout-or-duplicate']]) {
    assert.deepEqual(tag([{ success: false, 'error-codes': codes }]), [], `silent: ${codes.join()}`);
  }
  for (const codes of [['invalid-input-secret'], ['missing-input-secret'], ['internal-error'], ['bad-request'],
    ['some-code-added-later'], [], ['invalid-input-response', 'internal-error']]) {
    const out = tag([{ success: false, 'error-codes': codes }]);
    assert.equal(out.length, 1, `emits: [${codes.join()}]`);
    assert.equal(out[0].json.alert_class, 'turnstile_unavailable');
    assert.equal(out[0].json.turnstile_reason, 'verifier_answer');
  }
  assert.equal(tag([{ success: false }]).length, 1, 'no error-codes key at all → emits');
  assert.equal(tag([{ unexpected: 'html' }]).length, 1, 'not a siteverify answer → emits');
  assert.equal(tag([{ success: false, 'error-codes': ['timeout-or-duplicate'], error: { message: 'x' } }])[0].json.turnstile_reason, 'transport',
    'an error item is a transport failure even when it echoes a bot code');
  assert.equal(tag([{ error: { message: 'x' } }], {})[0].json.sender_key, 'unknown', 'Normalize Inbound not run');
});
test('R-Q2: wiring — fed by Verify Turnstile[1] and Turnstile Valid?[1], feeds Build Owner Alert', () => {
  const into = (src, i) => wf.connections[src].main[i].map((e) => e.node);
  assert.ok(into('Verify Turnstile', 1).includes('Tag Turnstile Unavailable') && into('Verify Turnstile', 1).includes('Reject Bot Request'));
  assert.ok(into('Turnstile Valid?', 1).includes('Tag Turnstile Unavailable') && into('Turnstile Valid?', 1).includes('Reject Bot Request'));
  assert.deepEqual(wf.connections['Tag Turnstile Unavailable'].main[0].map((e) => e.node), ['Build Owner Alert']);
});
test('R-Q2: the widget is answered first — Reject Bot Request sits ABOVE Tag Turnstile Unavailable (v1 runs siblings by position)', () => {
  assert.equal(wf.settings.executionOrder, 'v1');
  assert.ok(node('Reject Bot Request').position[1] < node('Tag Turnstile Unavailable').position[1]);
});
test('R-Q2: the class is checked first (even with an error field), its throttle key is global, and it has a sticky', () => {
  fresh();
  assert.equal(alert({ alert_class: 'turnstile_unavailable', sender_key: 'widget:w-a', error: 'x' })._alert_class, 'turnstile_unavailable');
  assert.equal(alert({ alert_class: 'turnstile_unavailable', sender_key: 'widget:w-b' }), null, 'a second sender inside the window is the same outage');
  assert.deepEqual(Object.keys(sd.ownerAlerts), ['turnstile_unavailable']);
  assert.ok(node('Sticky — Tag Turnstile Unavailable'));
});

// ── DEAD: the falsified notes are rewritten ────────────────────────────────────────────────────────────────────
test('DEAD: no note still says a post-claim infra failure answers 503, that a retry is safe, or that Record Processed writes', () => {
  const notes = wf.nodes.filter((n) => n.type === 'n8n-nodes-base.stickyNote').map((n) => n.parameters.content).join('\n');
  for (const s of ['(503 `calendar_unavailable`)', 'Calendar Unavailable Reply **503** (retry safe)', 'LLM Unavailable Reply 503',
    '**Record Processed** writes', 'covers those repeats', 'infra-unavailable (503)', '-> 503 ONLY']) {
    assert.ok(!notes.includes(s), `a note still says: ${s}`);
  }
  for (const n of ['LLM Unavailable Reply', 'Lead Unavailable Reply', 'Calendar Unavailable Reply', 'Cancel Delete Unavailable Reply', 'Send Error Response']) {
    assert.ok(!body(n).includes('widget stays bit-identical'), `${n}: the bit-identical comment is false now`);
  }
  assert.ok(!body('Classify Reconcile Failure').includes('retry-safe 503'));
});

// ── R1b H1: an integrity class carrying date_change keeps its own class, lines and throttle key ────────────────
const DC = { booked: '2030-01-08 11:00 cut', said: '2030-01-09' };
const ST = (stage) => ({ sender_key: SENDER, channel: 'widget', stage, slots: { serviceId: 'cut', service: 'Testcut', date: '2030-01-08', time: '11:00' } });
const INTEGRITY = [
  ['orphan_event', { orphan_event: true }],
  ['orphan_event', { reschedule_orphan: true, reschedule_old: { date: '2030-01-07', time: '10:00', service: 'Testcut' } }],
  ['mirror_failed', { mirror_failed: true }],
  ['mirror_failed', { reschedule_mirror_failed: true }],
  ['verify_unavailable', { verify_unavailable: true }, /possible overlap/],
  ['reconcile_unresolved', { reconcile_unresolved: true }],
  ['reconcile_conflict', { reconcile_conflict: true }],
  ['race_lost', { race_lost: true }],
  ['reschedule_insert_unknown', { reschedule_insert_unknown: true }, /possible extra event at the NEW slot/],
  ['event_build_failed', { error: 'event_build_failed', message: 'event build failed: x' }],
  ['state_unsaved', { _outbound_kind: 'Booking State-Unsaved Reply' }],
];
test('R1b H1: every integrity class carrying date_change keeps its class, a masked sender, its own lines, and the date line', () => {
  for (const [cls, flags, line] of INTEGRITY) {
    for (const ran of [{}, { 'Build Booked State': {} }]) {   // even beside a clean-booking marker the incident wins
      fresh();
      const a = alert({ ...flags, date_change: DC, state: ST('handoff') }, cfg(), ran);
      assert.ok(a, `${cls}: no alert`);
      assert.equal(a._alert_class, cls, JSON.stringify(flags));
      assert.ok(!a.owner_alert_text.includes(SENDER), `${cls}: sender not masked`);
      assert.match(a.owner_alert_text, /date on confirm: shown slot 2030-01-08 11:00 cut · customer said 2030-01-09/, cls);
      if (line) assert.match(a.owner_alert_text, line, cls);
    }
  }
});
test('R1b H1: a date_change alert already sent does not throttle the integrity alert that follows', () => {
  for (const [cls, flags] of INTEGRITY) {
    fresh();
    sd.ownerAlerts = { [`date_changed_on_confirm:${SENDER}`]: Date.now() };
    const a = alert({ ...flags, date_change: DC, state: ST('handoff') });
    assert.ok(a, `${cls} was swallowed by the date_change throttle`);
    assert.ok(Object.keys(sd.ownerAlerts).includes(`${cls}:${SENDER}`), cls);
  }
});

// ── R1b ITEM13 (final-pass #13): the sender_key is masked in EVERY alert ────────────────────────────────────────
test('ITEM13: no alert class prints a full sender_key; the shape matches the dashboard; _alert_sender stays full', () => {
  const senders = [[SENDER, 'widget:w-fake…'], ['whatsapp:+43 660 1234567', 'whatsapp:+43…67'],
    ['whatsapp:06601234567', 'whatsapp:06…67'], ['whatsapp:12345', 'whatsapp:•••••'], ['widget:w-fake…', 'widget:w-fake…']];
  const items = [
    { state: { stage: 'handoff' } }, { _outbound_kind: 'LLM Unavailable Reply' }, { _outbound_kind: 'Send Error Response' },
    { spend_cap_tripped: true }, { normalize_drift: true }, { extraction_invalid: true }, { race_lost: true },
    { orphan_event: true }, { verify_unavailable: true }, { reply_fallback: true }, { alert_class: 'turnstile_unavailable' },
  ];
  for (const [s, shown] of senders) {
    for (const it of items) {
      fresh();
      const a = alert({ ...it, sender_key: s, state: { ...(it.state || {}), sender_key: s } });
      assert.ok(a, JSON.stringify(it));
      const line = a.owner_alert_text.split('\n').find((l) => l.startsWith('sender: '));
      assert.equal(line, `sender: ${shown}`, `${s} · ${JSON.stringify(it)}`);
      assert.equal(a._alert_sender, s, 'Record Alert Class needs the full key');
    }
  }
  fresh();
  assert.match(alert({ state: { stage: 'handoff' } }).owner_alert_text, /\nsender: unknown\n/);
});

// ── R1b L8: a throwing builder or an invalid start is a handoff with an alert, never an n8n 500 ─────────────────
function build(name, { config = cfg(), vi = VI({ stage: name === 'Build Event Request' ? 'confirming' : 'reschedule_confirming' }), json = {} } = {}) {
  return fn(name, '$', '$json', 'DateTime')(stub({ 'Load Config': { config }, 'Validate Intent': vi }), json, DateTime)[0].json;
}
const BUILDERS = [['Build Event Request', 'Event ID Valid?'], ['Build Reschedule Event Request', 'Reschedule Event ID Valid?']];
test('L8: an unknown service, an invalid start, or a non-ASCII key → empty eventId + event_build_failed (no throw)', () => {
  for (const [b] of BUILDERS) {
    const stage = b === 'Build Event Request' ? 'confirming' : 'reschedule_confirming';
    const cases = [
      ['unknown service', { config: cfg({ services: [] }) }, /serviceId/],
      ['invalid start', { vi: VI({ stage, slots: { serviceId: 'cut', date: '2030-02-30', time: '11:00' } }) }, /invalid start 2030-02-30 11:00/],
      ['non-ASCII key', { vi: { ...VI({ stage }), sender_key: 'widget:w-ü' } }, /non-ASCII/],
    ];
    for (const [label, opts, why] of cases) {
      let j;
      assert.doesNotThrow(() => { j = build(b, opts); }, `${b} · ${label}`);
      assert.equal(j.booking.eventId, '', `${b} · ${label}`);
      assert.equal(j.error, 'event_build_failed', `${b} · ${label}`);
      assert.match(j.message, why, `${b} · ${label}`);
      assert.equal(j.booking.startISO, undefined, 'nothing half-built reaches the insert');
    }
    assert.match(build(b).booking.eventId, /^[0-9a-v]{5,1024}$/, `${b}: a valid build still yields its event id`);
  }
});
test('L8: the failed build routes through the existing gate to Mark Handoff, and alerts as event_build_failed with a masked reason', () => {
  for (const [b, gate] of BUILDERS) {
    const j = build(b, { config: cfg({ services: [] }), json: { _reschedule_target: {} } });
    const cond = node(gate).parameters.conditions.conditions[0];
    assert.equal(new RegExp(cond.rightValue).test(evalExpr(cond.leftValue, {}, j)), false, `${gate} must be false`);
    assert.deepEqual(wf.connections[gate].main[1].map((e) => e.node), ['Mark Handoff']);
    const mh = fn('Mark Handoff', '$', '$json')(stub({ 'Load Config': { config: cfg() } }), j)[0].json;
    assert.equal(mh.state.stage, 'handoff');
    assert.equal(mh.computed_reply, 'A person will follow up.');
    assert.ok(wf.connections['Mark Handoff'].main[0].some((e) => e.node === 'Save State') &&
      wf.connections['Mark Handoff'].main[0].some((e) => e.node === 'Build Owner Alert'));
    fresh();
    const a = alert(mh);
    assert.equal(a._alert_class, 'event_build_failed', b);
    assert.match(a.owner_alert_text, /\ndetail: event build failed: /);
    assert.ok(!a.owner_alert_text.includes(SENDER));
  }
});

// ── R1b M1: Compute Reschedule Availability reads freeBusy like Compute Availability (F3) ───────────────────────
function ravail(calendars) {
  const gate = { state: { turn_count: 3, slots: { serviceId: 'cut', date: '2030-01-07', time: '10:00' } },
    _reschedule_target: { start_utc: '2030-01-06T09:00:00.000Z', service: 'Testcut', recordId: 'recAAAAAAAAAAAAAA' } };
  const $ = stub({ 'Load Config': { config: cfg() }, 'Reschedule Lookup': gate });
  return fn('Compute Reschedule Availability', '$', '$json', 'DateTime')($, calendars === undefined ? {} : { calendars }, DateTime)[0].json;
}
test('M1: a calendar-level errors array, a missing or empty calendars object, or no busy list throws calendar_error', () => {
  for (const [label, c] of [['errors', { a: { errors: [{ domain: 'global', reason: 'notFound' }] } }], ['empty object', {}], ['missing', undefined],
    ['no busy list', { a: {} }], ['second calendar errors', { a: { busy: [] }, b: { errors: [{ reason: 'internalError' }] } }],
    ['errors beside an empty busy list', { a: { busy: [], errors: [{ domain: 'global', reason: 'notFound' }] } }]]) {
    assert.throws(() => ravail(c), /calendar_error/, label);
  }
  assert.deepEqual(wf.connections['Compute Reschedule Availability'].main[1].map((e) => e.node), ['Calendar Unavailable Reply']);
  assert.equal(node('Compute Reschedule Availability').onError, 'continueErrorOutput');
});
test('M1: busy is read from EVERY calendar; a clean answer is still available', () => {
  assert.equal(ravail({ a: { busy: [] }, b: { busy: [{ start: '2030-01-07T09:00:00Z', end: '2030-01-07T09:30:00Z' }] } }).resched_availability, 'busy');
  assert.equal(ravail({ a: { busy: [] } }).resched_availability, 'available');
});

// ── R1c RACE: an unreadable verify read is verify_incomplete (yield), never a throw ──────────────────────────────
const RACE = [['Check Race', 'Build Event Request', 'Race Gate'], ['Check Race (Reschedule)', 'Build Reschedule Event Request', 'Race Gate (Reschedule)']];
const OUR = { startUTC: '2030-01-08T10:00:00.000Z', endUTC: '2030-01-08T10:30:00.000Z', eventId: 'abcdef12345' };
const race = (name, builder, body) => fn(name, '$', '$json', 'DateTime')(stub({ 'Load Config': { config: cfg() },
  [builder]: { sender_key: SENDER, booking: OUR } }), body, DateTime)[0].json;
test('R1c RACE: items not an array, a non-object item, or an unparseable start/end → verify_incomplete (no throw)', () => {
  for (const [name, builder, gate] of RACE) {
    for (const [label, body] of [['items a string', { items: 'x' }], ['items an object', { items: {} }], ['items null-element', { items: [null] }],
      ['items number-element', { items: [1] }], ['items array-element', { items: [[]] }], ['item without times', { items: [{ id: 'o' }] }],
      ['item with garbage times', { items: [{ id: 'o', start: { dateTime: 'nope' }, end: { dateTime: 'nope' } }] }],
      ['times as objects without toString', { items: [{ id: 'o', start: { dateTime: { toString: 0, valueOf: 0 } }, end: { date: { toString: 0, valueOf: 0 } } }] }],
      ['start given as a string', { items: [{ id: 'o', start: '2030-01-08T10:00:00Z', end: '2030-01-08T10:30:00Z' }] }]]) {
      let j;
      assert.doesNotThrow(() => { j = race(name, builder, body); }, `${name} · ${label}`);
      assert.equal(j.verify_incomplete, true, `${name} · ${label}`);
      assert.equal(j.race_lost, true, `${name} · ${label}: an uncertain read must never enter the happy path`);
      assert.equal(j.race_other_count, -1);
    }
    assert.deepEqual(wf.connections[gate].main[0].map((e) => e.node).length, 1, `${gate}: race_lost has one yield route`);
  }
});
test('R1c RACE: clean reads keep their meaning — empty / only ours → won; another overlapping event → lost; cancelled ignored', () => {
  for (const [name, builder] of RACE) {
    assert.equal(race(name, builder, { items: [] }).race_lost, false);
    assert.equal(race(name, builder, {}).race_lost, false, 'no items key: unchanged (empty)');
    const ours = { id: OUR.eventId, start: { dateTime: OUR.startUTC }, end: { dateTime: OUR.endUTC } };
    assert.equal(race(name, builder, { items: [ours] }).race_lost, false);
    const other = race(name, builder, { items: [ours, { id: 'x', start: { dateTime: OUR.startUTC }, end: { dateTime: OUR.endUTC } }] });
    assert.equal(other.race_lost, true);
    assert.equal(other.verify_incomplete, undefined, 'a clean loss is not an incomplete read');
    assert.equal(race(name, builder, { items: [ours, { id: 'c', status: 'cancelled' }] }).race_lost, false, 'a cancelled item needs no times');
  }
});

// ── R1c ALERT-ORDER: no text claims the alert branch never touches the reply; the graph fact it states is true ──
test('R1c ALERT-ORDER: the false "never touches the reply" texts are gone, and the corrected text matches the graph', () => {
  const all = wf.nodes.map((n) => n.parameters.jsCode || n.parameters.content || '').join('\n');
  for (const s of ['never touches the customer reply', 'never the reply path', 'OFF the reply path (D-c)',
    'separate branch and is unaffected', 'only the OS TCP stack']) assert.ok(!all.includes(s), s);
  assert.match(body('Build Owner Alert'), /NOT off the reply path in TIME/);
  assert.match(body('Build Owner Alert'), /no node, request-helper or workflow timeout/);
  assert.match(body('Build Owner Alert'), /instance-wide execution timeout was NOT measured/);
  assert.match(body('Alert Record Failed'), /NOT off the reply path in time/);
  assert.match(body('Owner Alert Failed'), /alert-first paths/);
  assert.match(node('Sticky — Alert class stamp').parameters.content, /runs it FIRST/);
  const y = (n) => node(n).position[1];
  for (const src of ['Build Orphan State', 'Build Verify-Unavailable State', 'Build Normalize Reject']) {
    const sib = wf.connections[src].main[0].map((e) => e.node).filter((n) => n !== 'Build Owner Alert');
    assert.ok(sib.every((n) => y('Build Owner Alert') < y(n)), `${src}: the alert branch is stated to run first`);
  }
  assert.ok(y('Finalize Outbound') < y('Build Owner Alert'), 'and the infra replies answer first (the text does not claim otherwise)');
});

// ── R1c FLOW L1 / L4 ────────────────────────────────────────────────────────────────────────────────────────────
test('R1c FLOW: the H1 comment is narrowed; the reschedule builder names itself and its own gate', () => {
  assert.match(body('Build Owner Alert'), /reschedule builders that spread Validate Intent/);
  const r = body('Build Reschedule Event Request');
  assert.match(r, /Reschedule Event ID Valid\? false → Mark Handoff/);
  assert.ok(!/throw new Error\('Build Event Request:/.test(r), 'the reschedule builder must not name the booking builder');
  const j = build('Build Reschedule Event Request', { config: cfg({ services: [] }), json: { _reschedule_target: {} } });
  assert.match(j.message, /Build Reschedule Event Request: serviceId/);
});
