#!/usr/bin/env node
/**
 * The golden set's expected outputs against the COMMITTED intent contract (7-3, 2026-10-27).
 *
 * tests/golden-set.md holds one expected model output per case in a ```json golden block. Each is validated with ajv
 * against schemas/intent.schema.json itself (contract-integrity.md: never a hand-written copy), and the table and the
 * JSON must name the same cases. A case's confidence must sit on the side of bot.confidenceThreshold its table row
 * says (high = at or above, low = below), read from the example config. The paid model run is a 7-4 item; this test
 * only proves the expectations are well-formed and consistent.
 *
 * Negative controls run first: a missing `dateExpr` key, an intent outside the enum, an intent the table row does not
 * say, and a confidence on the wrong side of the threshold in either direction must each turn a case red, or this
 * test cannot see the defect it exists for.
 * Run: node tests/unit/golden-set.test.cjs   (GOLDEN=<path> reads another copy of the set)
 */
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const Ajv = require(path.join(ROOT, 'scripts', 'node_modules', 'ajv'));

const md = fs.readFileSync(process.env.GOLDEN || path.join(ROOT, 'tests', 'golden-set.md'), 'utf8');
const schema = JSON.parse(fs.readFileSync(path.join(ROOT, 'schemas', 'intent.schema.json'), 'utf8'));
const config = JSON.parse(fs.readFileSync(path.join(ROOT, 'config', 'client.config.example.json'), 'utf8'));
const threshold = config.bot.confidenceThreshold;
const validate = new Ajv({ allErrors: true }).compile(schema);

const block = md.match(/```json golden\n([\s\S]*?)\n```/);
if (!block) { console.error('golden-set: no ```json golden block'); process.exit(1); }
const cases = JSON.parse(block[1]);
const rows = {};
for (const m of md.matchAll(/^\| (G\d+) \| [^|]+ \| [^|]+ \| `([a-z_]+)` · (high|low) \|/gm)) rows[m[1]] = { intent: m[2], cls: m[3] };

function errs(id, out, row) {
  const e = [];
  if (!validate(out)) e.push(...validate.errors.map((x) => `${x.instancePath || '/'} ${x.message}`));
  if (!row) e.push('no table row');
  else {
    if (out.intent !== row.intent) e.push(`intent ${out.intent} ≠ the table's ${row.intent}`);
    const high = typeof out.confidence === 'number' && out.confidence >= threshold;
    if ((row.cls === 'high') !== high) e.push(`confidence ${out.confidence} is not ${row.cls} against ${threshold}`);
  }
  return e;
}

let ok = true;
const g1 = cases.G1;
const { dateExpr, ...noDateExpr } = g1.slots;
for (const [label, mutant] of [
  ['the required dateExpr key absent', { ...g1, slots: noDateExpr }],
  ['an intent outside the enum', { ...g1, intent: 'refund' }],
  ['a "high" case below the threshold', { ...g1, confidence: threshold - 0.01 }],
  ['an intent other than the table row says', { ...g1, intent: 'cancel' }],
]) {
  if (errs('G1', mutant, rows.G1).length === 0) { console.log(`✗ negative control stayed green: ${label}`); ok = false; }
}
if (errs('G7', { ...cases.G7, confidence: threshold }, rows.G7).length === 0) {   // the "low" side: at the threshold is not low
  console.log('✗ negative control stayed green: a "low" case at the threshold'); ok = false;
}
if (ok) console.log('✓ 5 negative controls red (missing dateExpr, intent outside the enum, an intent the table does not say, a high case below and a low case at the threshold)');

const ids = Object.keys(cases);
const missing = Object.keys(rows).filter((id) => !(id in cases)).concat(ids.filter((id) => !(id in rows)));
if (ids.length !== 15 || missing.length) { console.log(`✗ ${ids.length} JSON cases, ${Object.keys(rows).length} table rows; unmatched ${missing}`); ok = false; }
for (const id of ids) {
  const e = errs(id, cases[id], rows[id]);
  if (e.length) { console.log(`✗ ${id}: ${e.join('; ')}`); ok = false; }
}
const covered = new Set(ids.map((id) => cases[id].intent));
const absent = schema.properties.intent.enum.filter((i) => !covered.has(i));
console.log(`${ok ? '✓' : '✗'} golden-set: ${ids.length} cases valid against schemas/intent.schema.json · intents not covered: ${absent.length ? absent.join(', ') : 'none'}`);
process.exit(ok ? 0 : 1);
