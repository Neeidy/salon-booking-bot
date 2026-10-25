/**
 * The owner CSV export (Phase 7 item (a)). Two halves:
 *   - the REAL route handlers, `app/api/export/{appointments,leads}/route.ts`, end to end through the real
 *     `store.ts`, with only the `pg` Pool replaced by a fake that serves fixture rows (installed before anything
 *     imports pg, for the reason `store.behaviour.test.ts` gives). This is where masking, the forbidden columns
 *     and the flag are checked, because it is the path a download actually takes;
 *   - the pure helpers in `lib/exportCsv.ts`: quoting, the formula neutraliser, truncation, the error path.
 * What it does not check: the JSX that draws the links (Node cannot load .tsx; `exportLinks` is what the page
 * maps over, and it is tested here), and Cloudflare Access, which these routes do not implement.
 *
 * Run: node --test lib/exportCsv.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { EventEmitter } from 'node:events';
import { readFileSync } from 'node:fs';

// ── the fake driver ─────────────────────────────────────────────────────────────────────────────────────────
const sent: string[] = [];
let served: Record<string, Array<{ id: string; fields: Record<string, unknown> }>> = {};
let sqlOf: Record<string, string> = {};
class FakePool extends EventEmitter {
  constructor(_o?: unknown) { super(); }
  query(text: string) {
    sent.push(text);
    if (text.includes('current_user AS role')) return Promise.resolve({ rows: [{ role: 'export_ro', writable: 0 }] });
    const table = Object.keys(sqlOf).find((k) => sqlOf[k] === text);
    return Promise.resolve({ rows: table ? (served[table] ?? []) : [] });
  }
  end() { return Promise.resolve(); }
}
const pgCjs = createRequire(import.meta.url)('pg');
pgCjs.Pool = FakePool;
for (const k of ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD']) process.env[k] = 'export-synthetic';
process.env.CLIENT_CONFIG_JSON = JSON.stringify({ business: { timezone: 'Europe/Vienna', name: 'Test' } });

const store = await import('./store.ts');
sqlOf = { ...store.SQL };
const appointmentsRoute = await import('../app/api/export/appointments/route.ts');
const leadsRoute = await import('../app/api/export/leads/route.ts');
const ex = await import('./exportCsv.ts');

// ── fixtures: synthetic, and shaped to be caught if they leak ─────────────────────────────────────────────────
const DAY = 86_400_000;
const iso = (ms: number) => new Date(ms).toISOString();
const NOW = Date.now();
// Values that must NEVER appear raw in a file, and the forbidden columns' values, smuggled into `fields` as if
// a mutated SELECT had returned them: the file's columns are explicit, so they must not come through.
const RAW = ['Schmidt', 'Maria', '1234567', '660 123', 'anna.schmidt', 'SECRET-SENDER-KEY', 'SECRET-GCAL-ID', 'SECRET-REPLY', 'SECRET-TARGET'];
const FORBIDDEN = ['sender_key', 'gcal_event_id', 'computed_reply', 'cancel_target_id'];
const smuggled = { sender_key: 'widget:w-SECRET-SENDER-KEY', gcal_event_id: 'SECRET-GCAL-ID', computed_reply: 'SECRET-REPLY', cancel_target_id: 'SECRET-TARGET' };
const APPOINTMENTS = [
  { id: 'recA1', fields: { start_utc: iso(NOW + 2 * DAY), service: 'Cut, "deluxe"\nwash', channel: 'widget', status: 'booked', reminded: true, customer_name: 'Anna Maria Schmidt', ...smuggled } },
  { id: 'recA2', fields: { start_utc: iso(NOW + 3 * DAY), service: '=1+1', channel: '@channel', status: 'booked', customer_name: '=HYPERLINK("http://example.invalid","click")' } },
  { id: 'recA3', fields: { start_utc: iso(NOW + 4 * DAY), service: 'Beard', channel: 'whatsapp', status: 'booked', customer_name: '+43 660 1234567' } },
  { id: 'recA4', fields: { start_utc: iso(NOW + 5 * DAY), service: 'Cancelled one', channel: 'widget', status: 'cancelled', customer_name: 'Zed Cancelled' } },
  { id: 'recA5', fields: { start_utc: iso(NOW - 1.5 * DAY), service: 'Yesterday one', channel: 'widget', status: 'booked', customer_name: 'Yan Yesterday' } },
];
const LEADS = [
  { id: 'recL1', fields: { name: 'Anna Maria Schmidt', phone: '+43 660 1234567', source: 'widget', status: 'new', ...smuggled } },
  { id: 'recL2', fields: { name: 'anna.schmidt@example.com', phone: '0660-123-4567', source: '-2+3', status: 'contacted' } },
  { id: 'recL3', fields: { name: '@SUM(A1:A9)', phone: '\t+43 660 7654321', source: '\rcmd' } },
];

/** A minimal RFC 4180 reader: quoted cells, doubled quotes, CRLF. Enough to prove the writer round-trips. */
function parseCsv(text: string): string[][] {
  assert.ok(text.startsWith('﻿'), 'the file must start with a UTF-8 BOM');
  const s = text.slice(1);
  const rows: string[][] = [];
  let row: string[] = []; let cell = ''; let i = 0; let quoted = false;
  while (i < s.length) {
    const c = s[i];
    if (quoted) {
      if (c === '"' && s[i + 1] === '"') { cell += '"'; i += 2; continue; }
      if (c === '"') { quoted = false; i++; continue; }
      cell += c; i++; continue;
    }
    if (c === '"') { quoted = true; i++; continue; }
    if (c === ',') { row.push(cell); cell = ''; i++; continue; }
    if (c === '\r' && s[i + 1] === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; i += 2; continue; }
    assert.fail(`unquoted character ${JSON.stringify(c)} at ${i}: every cell must be quoted`);
  }
  assert.equal(cell, ''); assert.equal(row.length, 0, 'the file must end with CRLF');
  return rows;
}

/** The body as BYTES: `Response.text()` strips a BOM, so it could not show the BOM is really sent. */
async function bodyOf(r: Response): Promise<string> {
  const bytes = new Uint8Array(await r.arrayBuffer());
  assert.deepEqual([...bytes.slice(0, 3)], [0xef, 0xbb, 0xbf], 'the body must begin with the UTF-8 BOM bytes');
  return new TextDecoder('utf-8', { ignoreBOM: true }).decode(bytes);
}

async function download(route: { GET: () => Promise<Response> }, flag: string | undefined) {
  if (flag === undefined) delete process.env.DASHBOARD_EXPORT_ENABLED; else process.env.DASHBOARD_EXPORT_ENABLED = flag;
  store.resetBudget();
  return route.GET();
}

// ── the real routes ───────────────────────────────────────────────────────────────────────────────────────────
test('flag OFF (unset, 0, true, yes, " 1", ""): both routes answer 404, read NOTHING, and the page gets no link', async () => {
  served = { appointments: APPOINTMENTS, leads: LEADS };
  for (const flag of [undefined, '0', 'true', 'yes', ' 1', '', 'TRUE']) {
    for (const route of [appointmentsRoute, leadsRoute]) {
      const from = sent.length;
      const r = await download(route, flag);
      assert.equal(r.status, 404, `flag=${JSON.stringify(flag)} answered ${r.status}`);
      assert.equal(sent.length, from, `flag=${JSON.stringify(flag)}: a statement was sent before the gate refused`);
      assert.doesNotMatch(await r.text(), /Schmidt|recA|recL/);
    }
    assert.deepEqual(ex.exportLinks(flag === undefined ? {} : { DASHBOARD_EXPORT_ENABLED: flag }), []);
  }
  assert.equal(ex.exportLinks({ DASHBOARD_EXPORT_ENABLED: '1' }).length, 2, 'control: the flag ON must yield the links');
});

test('flag ON: appointments CSV — the panel\'s rows, masked names, quoted cells, attachment headers', async () => {
  served = { appointments: APPOINTMENTS, leads: LEADS };
  const from = sent.length;
  const r = await download(appointmentsRoute, '1');
  assert.equal(r.status, 200);
  assert.equal(r.headers.get('content-type'), 'text/csv; charset=utf-8');
  assert.match(r.headers.get('content-disposition') ?? '', /^attachment; filename="appointments-\d{4}-\d{2}-\d{2}\.csv"$/);
  assert.equal(r.headers.get('cache-control'), 'no-store');
  // It read through store.ts's own constant: the privilege check (once per process) and SQL.appointments only.
  assert.deepEqual(sent.slice(from).filter((t) => !t.includes('current_user AS role')), [store.SQL.appointments]);
  const text = await bodyOf(r);
  const rows = parseCsv(text);
  assert.deepEqual(rows[0], ['date (Europe/Vienna)', 'time (Europe/Vienna)', 'customer', 'service', 'channel', 'reminded']);
  assert.equal(rows.length, 4, 'header + the three booked future rows; the cancelled and yesterday rows are not on the panel');
  assert.equal(rows[1][2], 'Anna M. S.');
  assert.equal(rows[1][3], 'Cut, "deluxe"\nwash', 'a comma, a quote and a newline must survive quoting intact');
  assert.equal(rows[1][5], 'yes');
  assert.equal(rows[2][2], `'=HYPERLINK("http://example.invalid","click")`, 'a formula in a name must be neutralised');
  assert.equal(rows[2][3], `'=1+1`);
  assert.equal(rows[2][4], `'@channel`);
  assert.equal(rows[3][2], `'+43…67`, 'a phone typed as a name is masked, then neutralised');
  for (const raw of [...RAW, 'Cancelled', 'Yesterday']) assert.ok(!text.includes(raw), `the file carries ${raw}`);
  for (const col of FORBIDDEN) assert.ok(!text.includes(col), `the file names ${col}`);
});

test('flag ON: leads CSV — masked name and phone, formula cells neutralised, forbidden columns absent', async () => {
  served = { appointments: APPOINTMENTS, leads: LEADS };
  const r = await download(leadsRoute, '1');
  assert.equal(r.status, 200);
  assert.match(r.headers.get('content-disposition') ?? '', /^attachment; filename="leads-\d{4}-\d{2}-\d{2}\.csv"$/);
  const text = await bodyOf(r);
  const rows = parseCsv(text);
  assert.deepEqual(rows[0], ['name', 'phone', 'status', 'source']);
  assert.deepEqual(rows[1], ['Anna M. S.', `'+43…67`, 'new', 'widget']);
  assert.equal(rows[2][0], 'a…@example.com');
  assert.equal(rows[2][1], '06…67');
  assert.equal(rows[2][3], `'-2+3`);
  assert.equal(rows[3][0], `'@SUM(A1:A9)`);
  assert.equal(rows[3][1], `'+43…21`, 'a leading tab is neither kept as a formula start nor left unmasked');
  assert.equal(rows[3][2], 'new', 'the panel shows a missing status as new, and so does the file');
  assert.equal(rows[3][3], `'\rcmd`);
  for (const raw of [...RAW, '7654321']) assert.ok(!text.includes(raw), `the file carries ${raw}`);
  for (const col of FORBIDDEN) assert.ok(!text.includes(col), `the file names ${col}`);
});

test('the routes are server-only files that take no input and import the store, not a client module', () => {
  for (const k of ['appointments', 'leads']) {
    const src = readFileSync(new URL(`../app/api/export/${k}/route.ts`, import.meta.url), 'utf8');
    assert.doesNotMatch(src, /^\s*['"]use client['"]/m);
    assert.match(src, /export async function GET\(\): Promise<Response>/, 'GET must declare no request parameter');
    assert.doesNotMatch(src, /export (async )?function (POST|PUT|PATCH|DELETE)\b/);
  }
});

// ── the pure helpers ──────────────────────────────────────────────────────────────────────────────────────────
test('csvCell: every formula start is neutralised, quotes are doubled, ordinary text is only quoted', () => {
  for (const lead of ['=', '+', '-', '@', '\t', '\r']) assert.equal(ex.csvCell(`${lead}x`), `"'${lead}x"`, JSON.stringify(lead));
  assert.equal(ex.csvCell('a "b", c'), '"a ""b"", c"');
  assert.equal(ex.csvCell('Anna M. S.'), '"Anna M. S."');
  assert.equal(ex.csvCell(' =x'), '" =x"', 'a leading space is not a formula start in the OWASP list');
  assert.equal(ex.csvCell(''), '""');
});

test('a truncated page says so inside the file', () => {
  const page = { rows: [{ id: 'recL1', name: 'Bo Li', phone: '+43 660 1234567' }], truncated: true };
  const rows = parseCsv(ex.leadsCsv(page));
  assert.match(rows.at(-1)![0], /^\(truncated: /);
  assert.ok(!parseCsv(ex.leadsCsv({ ...page, truncated: false })).some((r) => r[0].startsWith('(truncated')));
});

test('a value that fails the masking check is withheld, not written', () => {
  // No input makes today's maskers emit a 5-digit run, so the guard is driven with a mask that is broken on
  // purpose: the property is that whatever a mask returns, assertMasked stands between it and the file.
  const broken = () => 'Bo 1234567';
  assert.equal(ex.maskedCell(broken, 'x', 'lead phone'), '— (withheld: it did not pass the masking check)');
  assert.equal(ex.maskedCell(() => 'a.b@example.com', 'x', 'lead name'), '— (withheld: it did not pass the masking check)');
  assert.equal(ex.maskedCell((v) => `ok:${v}`, 'x', 'lead name'), 'ok:x', 'control: a value that passes is written');
});

test('a failed read is a 503 (or 500 for configuration) whose body and log carry no message text', async () => {
  const logged: string[] = [];
  const saved = console.error;
  console.error = (...a: unknown[]) => { logged.push(a.map(String).join(' ')); };
  try {
    const leak = Object.assign(new Error('host=db.example user=salon_ro'), { name: 'StoreError', code: 'ECONNREFUSED' });
    const base = { env: { DASHBOARD_EXPORT_ENABLED: '1' }, resetBudget: () => {}, timezone: () => 'Europe/Vienna', now: () => NOW };
    const r = await ex.exportResponse('leads', { ...base, readAppointments: async () => { throw leak; }, readLeads: async () => { throw leak; } });
    assert.equal(r.status, 503);
    const body = await r.text();
    const cfg = await ex.exportResponse('appointments', { ...base, readLeads: async () => ({ rows: [], truncated: false }),
      readAppointments: async () => { throw Object.assign(new Error('PGHOST must be set'), { name: 'ConfigError' }); } });
    assert.equal(cfg.status, 500);
    for (const s of [body, await cfg.text(), ...logged]) assert.doesNotMatch(s, /db\.example|salon_ro|PGHOST/);
    assert.ok(logged.some((l) => l.includes('StoreError ECONNREFUSED')), `the log must carry the class: ${logged.join(' | ')}`);
  } finally {
    console.error = saved;
  }
});
