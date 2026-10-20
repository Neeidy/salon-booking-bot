/**
 * The contract run against the REAL database (MIGRATION-PLAN §3b, §3n, D2b-3): each table's Airtable-shape
 * SQL, read as salon_ro, checked by tests/contract/shape.cjs.
 *
 * Reads only the `mig-` seed rows (prefix-guarded), and refuses to pass on an empty table, because a check
 * over zero rows measures nothing. Prints counts, rule names and field NAMES only, never a value (Q16's
 * interim rule: salon_ro can read every column, so nothing it reads is echoed).
 *
 * Positive control, on the same rows: each table is also read through a deliberately MIS-SHAPED query (no
 * NULLIF, no jsonb_strip_nulls, raw booleans and raw timestamps), and the checker must catch, on that
 * table, EVERY rule class the seed can trigger there (`expect`). Requiring only "some violation" was not
 * enough: the raw createdTime alone always tripped one, so the field rules could have been deleted from
 * shape.cjs with this run still green (pre-push audit, 2026-10-20).
 *
 * Run:  set -a; . <the read-only env file>; set +a; node tests/db/contract-run.cjs
 */
const path = require('node:path');
const { Client } = require(path.join(__dirname, '..', '..', 'web', 'node_modules', 'pg'));
const { checkRecord } = require(path.join(__dirname, '..', 'contract', 'shape.cjs'));

// Airtable field name → column and kind. The names are DATA-MODEL's; `leads.id` is the autonumber (§3b).
const TABLES = {
  conversations: {
    guard: "sender_key LIKE 'widget:w-mig-%'",
    expect: ['null', 'empty', 'ts', 'createdTime'],
    cols: [['sender_key', 'text'], ['stage', 'text'], ['slot_service', 'text'], ['slot_date', 'text'], ['slot_time', 'text'],
      ['last_updated', 'ts'], ['turn_count', 'num'], ['last_intent', 'text'], ['recent_messages', 'text'],
      ['gcal_event_id', 'text'], ['cancel_target_id', 'text'], ['confirm_turn', 'text'], ['computed_reply', 'text'],
      ['last_alert_class', 'text'], ['last_alert_at', 'ts'], ['sender_masked', 'text']],
  },
  appointments: {
    guard: "gcal_event_id LIKE 'mig-%'",
    expect: ['null', 'empty', 'false', 'ts', 'createdTime'],
    cols: [['sender_key', 'text'], ['service', 'text'], ['start_utc', 'ts'], ['end_utc', 'ts'], ['gcal_event_id', 'text'],
      ['calendar_id', 'text'], ['channel', 'text'], ['customer_name', 'text'], ['status', 'text'], ['reminded', 'bool'],
      ['reminder_sent', 'ts'], ['created_at', 'ts']],
  },
  leads: {
    guard: "name LIKE 'mig-%'",
    expect: ['null', 'empty', 'ts', 'createdTime'],
    cols: [['id', 'num', 'lead_no'], ['name', 'text'], ['phone', 'text'], ['source', 'text'], ['message', 'text'],
      ['status', 'text'], ['created_at', 'ts']],
  },
  processed_messages: {
    guard: "message_id LIKE 'mig-%'",
    expect: ['null', 'empty', 'ts', 'createdTime'],
    cols: [['message_id', 'text'], ['sender_key', 'text'], ['channel', 'text'], ['created_at', 'ts']],
  },
  bot_metrics: {
    guard: "period_key LIKE 'mig-%'",
    expect: ['null', 'ts', 'createdTime'],
    cols: [['period_key', 'text'], ['cost_usd', 'num'], ['updated_at', 'ts']],
  },
};

const SHAPED = { text: (c) => `NULLIF(${c}, '')`, ts: (c) => `salon.at_ts(${c})`, num: (c) => c, bool: (c) => `CASE WHEN ${c} THEN true END` };
const BROKEN = { text: (c) => c, ts: (c) => c, num: (c) => c, bool: (c) => c };

function sql(table, spec, broken) {
  const k = broken ? BROKEN : SHAPED;
  const pairs = spec.cols.map(([name, kind, col]) => `'${name}', ${k[kind](col || name)}`).join(', ');
  const fields = broken ? `jsonb_build_object(${pairs})` : `jsonb_strip_nulls(jsonb_build_object(${pairs}))`;
  const created = broken ? 'created_at' : 'salon.at_ts(created_at)';
  return `SELECT id, ${created} AS "createdTime", ${fields} AS fields FROM salon.${table} WHERE ${spec.guard} ORDER BY id`;
}

// A violation message → its rule class (the classes the seed's sparse and full rows can trigger).
function ruleClass(m) {
  if (m.startsWith('createdTime')) return 'createdTime';
  if (/^fields\.\w+ is null/.test(m)) return 'null';
  if (/^fields\.\w+ is ""/.test(m)) return 'empty';
  if (/^fields\.\w+ is false/.test(m)) return 'false';
  if (/^fields\.\w+ is not ISO-ms-Z/.test(m)) return 'ts';
  return 'other';
}

function specFor(spec) {
  return {
    timestampFields: spec.cols.filter(([, kind]) => kind === 'ts').map(([name]) => name),
    numberFields: spec.cols.filter(([, kind]) => kind === 'num').map(([name]) => name),
  };
}

(async () => {
  if (process.env.PGUSER !== 'salon_ro') { console.error('contract-run: refused — PGUSER is not salon_ro'); process.exit(2); }
  const c = new Client();
  c.on('error', (e) => { console.error('contract-run: connection error —', e.code || 'no SQLSTATE'); process.exit(2); });
  await c.connect();
  let ok = true;
  for (const [table, spec] of Object.entries(TABLES)) {
    const shaped = (await c.query(sql(table, spec, false))).rows;
    const broken = (await c.query(sql(table, spec, true))).rows;
    const v = shaped.flatMap((r) => checkRecord(r, specFor(spec)));
    const bv = broken.flatMap((r) => checkRecord(r, specFor(spec)));
    const keys = new Set(shaped.flatMap((r) => Object.keys(r.fields || {})));
    const caught = new Set(bv.map(ruleClass));
    const missed = spec.expect.filter((k) => !caught.has(k));
    const pass = shaped.length > 0 && v.length === 0 && missed.length === 0;
    ok = ok && pass;
    console.log(`${pass ? '✓' : '✗'} ${table.padEnd(19)} rows ${shaped.length} · shaped violations ${v.length}` +
      ` · field keys seen ${keys.size}/${spec.cols.length} · CONTROL (mis-shaped) ${bv.length} violations, classes caught` +
      ` [${[...caught].sort()}]${missed.length ? ` · MISSED [${missed}]` : ''}`);
    if (v.length) console.log(`    shaped violations: ${[...new Set(v)].join(' | ')}`);
    if (shaped.length === 0) console.log('    EMPTY: no mig- rows, so this table measured nothing');
  }
  await c.end();
  console.log(`contract-run: ${ok ? 'OK' : 'FAILED'}`);
  process.exit(ok ? 0 : 1);
})().catch((e) => { console.error('contract-run: aborted —', e.code || 'no SQLSTATE'); process.exit(2); });   // code only: a connect error's message carries the host
