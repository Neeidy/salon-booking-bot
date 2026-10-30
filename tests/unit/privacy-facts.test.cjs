/**
 * The /privacy page and the widget notice state facts about the running engine — this test holds each one to the
 * committed workflows and the config, so the page cannot claim what the engine does not do (public demo gate #14 and
 * its honesty additions, 2026-10-29; memory rule "approval is not accuracy").
 *
 * Each claim → what it is checked against:
 *   · message text erased after MESSAGE_TEXT_DAYS (lib/retention.ts, re-exported by lib/privacy.ts), message ids deleted after the same → Purge's `Compute PII Cutoff`
 *     and `Compute Purge Cutoff` (both the committed export and a staged one, if any);
 *   · leads deleted after LEAD_DAYS → lib/privacy.ts reads `config.leadsRetentionDays`, the key Purge's
 *     `Compute Leads Cutoff` reads from `Load Config (Purge)` (the KEY only: that the example config's VALUE equals the
 *     committed Purge literal is held by render-client.test.py case 1, not here);
 *   · the leads safety limit the page states (a fifth, 200, fewer than five → none) → `Leads Purge Sane?`'s constants
 *     and its `within` rule; a lead stores the visitor's message → `Capture Lead` inserts `message`;
 *   · backups kept BACKUP_DAYS → db/ops/pg-backup.sh's KEEP_DAYS default (in force on the server: measured in R2, 2026-10-30);
 *   · run records kept RUN_RECORD_DAYS → NOT checkable here (a server setting); the constant must carry its measurement;
 *   · the privacy contact → a visible placeholder while it is null (Yigitcan's answer pending, a go-live blocker);
 *   · "bookings are not deleted automatically" → no Purge statement touches salon.appointments;
 *   · the services list → every outside host a workflow calls maps to a listed service (comment-only hosts allowlisted);
 *   · "nothing is sent over WhatsApp" → Main's `Should Send?` (the gate in front of `Send WhatsApp (Zernio)`) is fed only
 *     by the WhatsApp ACK responder, and Reminders' literal holds `whatsappSendDisabled: true`;
 *   · the page, the notice and the footer say it → text anchors, the notice shown on demo builds only.
 *
 * Run: node tests/unit/privacy-facts.test.cjs
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { existsSync, readFileSync } = require('node:fs');
const { join } = require('node:path');

const ROOT = join(__dirname, '..', '..');
const read = (...p) => readFileSync(join(ROOT, ...p), 'utf8');
const wf = (key, staged = false) => JSON.parse(read('n8n', ...(staged ? ['staged'] : []), `workflow.${key}.sanitized.json`));
const code = (w, name) => {
  const n = w.nodes.find((x) => x.name === name);
  assert.ok(n, `node ${name} exists`);
  return n.parameters.jsCode || '';
};
const PRIVACY = read('web', 'site', 'lib', 'privacy.ts');
const RETENTION = read('web', 'site', 'lib', 'retention.ts');
const PAGE = read('web', 'site', 'app', 'privacy', 'page.tsx');
const PANEL = read('web', 'site', 'components', 'site', 'LiveChatPanel.tsx');
const FOOTER = read('web', 'site', 'components', 'site', 'SiteFooter.tsx');
const MESSAGE_TEXT_DAYS = Number(RETENTION.match(/export const MESSAGE_TEXT_DAYS = (\d+);/)[1]);

const purges = [wf('purge')];
if (existsSync(join(ROOT, 'n8n', 'staged', 'workflow.purge.sanitized.json'))) purges.push(wf('purge', true));

test('message text and message ids: the page\'s number is the one both Purge cutoffs use', () => {
  for (const p of purges) {
    for (const node of ['Compute PII Cutoff', 'Compute Purge Cutoff']) {   // (the leads rule is the next test)
      const m = code(p, node).match(/\$now\.minus\(\{ days: (\d+) \}\)/);
      assert.ok(m, `${node} computes a fixed day count`);
      assert.equal(Number(m[1]), MESSAGE_TEXT_DAYS, `${node} vs MESSAGE_TEXT_DAYS`);
    }
  }
});

test('leads: the site reads the same config key Purge reads, never a number of its own', () => {
  assert.match(PRIVACY, /const days = config\.leadsRetentionDays;/);
  assert.match(PRIVACY, /Number\.isInteger\(days\) && \(days as number\) >= 1 \? \(days as number\) : null;/);
  for (const p of purges) {
    assert.match(code(p, 'Compute Leads Cutoff'), /\.leadsRetentionDays;/);
    assert.match(code(p, 'Compute Leads Cutoff'), /if \(!Number\.isInteger\(days\) \|\| days < 1\)/, 'the same rule as the site');
    assert.match(code(p, 'Compute Leads Cutoff'), /\$\('Load Config \(Purge\)'\)/);
  }
});

test('leads: the page states the Purge\'s safety limit exactly as the code applies it, and that a lead holds the message', () => {
  for (const p of purges) {
    const c = code(p, 'Leads Purge Sane?');
    assert.match(c, /const CAP_ABS = 200, CAP_PCT = 0\.20;/);
    assert.match(c, /const cap = Math\.min\(CAP_ABS, Math\.floor\(total \* CAP_PCT\)\);/);
    assert.match(c, /const within = rows\.length > 0 && rows\.length <= cap;/);
  }
  for (const anchor of ['more than a fifth of all callback requests, or more than 200, at once', 'deleting nothing that night',
    'it can keep stopping the job, night after night',
    'with fewer than five', 'your contact details and your message']) assert.ok(PAGE.includes(anchor), `page: ${anchor}`);
  const cap = wf('main').nodes.find((n) => n.name === 'Capture Lead').parameters.query;
  assert.match(cap, /^INSERT INTO salon\.leads \(name, phone, source, message,/);
});

test('backups: the page\'s number is the backup script\'s default retention', () => {
  const keep = Number(read('db', 'ops', 'pg-backup.sh').match(/KEEP_DAYS="\$\{PG_BACKUP_KEEP_DAYS:-(\d+)\}"/)[1]);
  assert.equal(Number(PRIVACY.match(/export const BACKUP_DAYS = (\d+);/)[1]), keep);
  for (const anchor of ['Copies outside the database', 'more than {BACKUP_DAYS} full days old', 'keeps a record of each run',
    'for about {RUN_RECORD_DAYS} days', 'its backups are removed']) {
    assert.ok(PAGE.includes(anchor), `page: ${anchor}`);
  }
  // RUN_RECORD_DAYS is a server measurement, not a repo fact: the constant must say so, so it is not read as tested.
  assert.match(PRIVACY, /Measured by behaviour \(R2 measurement 4[^)]*\)[\s\S]*export const RUN_RECORD_DAYS = 14;/);
});

test('the privacy contact: until Yigitcan names one, the page shows a visible PLACEHOLDER, never an invented address', () => {
  const m = PRIVACY.match(/export const PRIVACY_CONTACT: string \| null = (null|'[^']+');/);
  assert.ok(m, 'PRIVACY_CONTACT is declared');
  // Pinned to null until Yigitcan names the contact: the value is his to give, so a change here must come with his answer.
  assert.equal(m[1], 'null', 'no contact has been given — the constant stays null');
  assert.ok(PAGE.includes("{PRIVACY_CONTACT === null\n            ? 'PLACEHOLDER — the contact for privacy requests has not been published yet"),
    'null renders the placeholder');
});

test('bookings: no Purge statement touches salon.appointments (so "not deleted automatically" is true)', () => {
  for (const p of purges) {
    const sql = p.nodes.filter((n) => n.type === 'n8n-nodes-base.postgres').map((n) => n.parameters.query);
    assert.ok(sql.length >= 5, 'the Purge statements were found (a zero would prove nothing)');
    assert.ok(!sql.some((q) => /salon\.appointments/.test(q)));
  }
});

test('cancelling: the calendar event is deleted and the booking row is kept, marked cancelled (as the page says)', () => {
  const main = wf('main');
  const node = (name) => main.nodes.find((n) => n.name === name);
  assert.match(JSON.stringify(node('Delete Booking Event').parameters), /DELETE/);
  assert.match(node('Update Appointment Cancelled').parameters.query, /^UPDATE salon\.appointments SET status = 'cancelled' WHERE id = \$1/);
  assert.ok(!main.nodes.some((n) => /DELETE FROM salon\.appointments/.test(n.parameters.query || '')), 'Main never deletes a booking row');
  assert.ok(PAGE.includes('marked cancelled'));
});

test('services: every outside host a workflow calls is a listed service', () => {
  const SERVICE_OF = {
    'api.anthropic.com': 'Anthropic', 'challenges.cloudflare.com': 'Cloudflare', 'www.googleapis.com': 'Google Calendar',
    'zernio.com': null,   // WhatsApp — never reached by this demo (next test)
  };
  const COMMENT_ONLY = new Set(['example.com', 'json-schema.org', 'salon-booking-bot']);   // in code comments / ids
  const seen = new Set();
  for (const key of ['main', 'purge', 'reminders', 'owner-actions', 'drill-state']) {
    for (const n of wf(key).nodes) {
      const s = JSON.stringify(n.parameters);
      for (const m of s.matchAll(/https?:\/\/([a-zA-Z0-9.-]+)/g)) seen.add(m[1]);
      if (n.type === 'n8n-nodes-base.telegram') seen.add('telegram');
    }
  }
  assert.ok(seen.size >= 5, `hosts found: ${[...seen]}`);
  for (const h of seen) {
    if (COMMENT_ONLY.has(h)) continue;
    const svc = h === 'telegram' ? 'Telegram' : SERVICE_OF[h];
    assert.ok(svc !== undefined, `a host the page does not account for: ${h}`);
    if (svc) assert.ok(PRIVACY.includes(`name: '${svc}`), `${h} → '${svc}' is listed in PROCESSORS`);
  }
});

test('WhatsApp: a widget message never reaches the Zernio send, and the Reminders send brake is on', () => {
  const main = wf('main');
  const into = (target) => Object.entries(main.connections).flatMap(([src, v]) =>
    (v.main || []).flatMap((outs) => (outs || []).filter((e) => e.node === target).map(() => src)));
  assert.deepEqual(into('Send WhatsApp (Zernio)'), ['Live Send?']);
  assert.deepEqual(into('Live Send?'), ['Should Send?']);
  assert.deepEqual(into('Should Send?'), ['Respond ACK 200 (whatsapp)']);
  assert.match(code(wf('reminders'), 'Load Config (Reminders)'), /whatsappSendDisabled: true/);
});

test('the page, the notice and the footer say it', () => {
  for (const anchor of ['Bookings are real', 'real Google Calendar', 'Telegram', 'outside the automatic deletion',
    '{MESSAGE_TEXT_DAYS}', 'LEAD_DAYS', 'TURNSTILE_PRIVACY_URL', 'Nothing is sent over', 'if (!isDemo) notFound();']) {
    assert.ok(PAGE.includes(anchor), `page: ${anchor}`);
  }
  assert.match(PANEL, /\{config\.demoMode === true && \(/, 'the notice is shown on demo builds only');
  assert.match(PANEL, /from '\.\.\/\.\.\/lib\/retention'/, 'the panel takes the number from retention.ts');
  assert.match(PRIVACY, /export \{ MESSAGE_TEXT_DAYS \} from '\.\/retention';/, 'privacy.ts re-exports the same number');
  for (const anchor of ['real personal details', 'AI model', "from the demo&apos;s database after {MESSAGE_TEXT_DAYS} days",
    'while backups, the engine&apos;s run', 'owner alerts (Telegram) can keep copies longer', 'real demo calendar', 'href="/privacy"']) {
    assert.ok(PANEL.includes(anchor), `notice: ${anchor}`);
  }
  assert.match(FOOTER, /\{isDemo && <span>[^\n]*<a href="\/privacy">Privacy<\/a><\/span>\}/);
});
