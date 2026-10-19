/**
 * Proves the contract checker (tests/contract/shape.cjs) BEFORE it is pointed at the real database in D2b-3.
 *
 * 1. The checker's rules are the D0 FIXTURES' rules: the recorded Airtable outputs (keys, types and format
 *    flags only, no values) must say exactly what the checker enforces. If Airtable's recorded shape
 *    disagreed with the checker, this test, not D3, is where that shows.
 * 2. A record built to the contract passes; each way a Postgres query could get the shape wrong fails.
 *
 * Run: node tests/contract/airtable-shape.test.cjs
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { checkRecord, checkEmpty } = require('./shape.cjs');

const FIX = JSON.parse(readFileSync(join(__dirname, 'fixtures', 'airtable-shapes.json'), 'utf8'));

test('the D0 fixtures carry the contract the checker enforces', () => {
  const withRecords = Object.entries(FIX.nodes).filter(([, n]) => n.record_items > 0);
  assert.ok(withRecords.length > 0, 'no recorded Airtable record in the fixtures: nothing to compare against');
  for (const [name, n] of withRecords) {
    assert.deepEqual(Object.keys(n.record_top_level_key_sets), ['createdTime,fields,id'], `${name}: top-level keys`);
    assert.equal(n.record_id_matches_rec14, n.record_items, `${name}: every id is rec+14`);
    assert.equal(n.record_createdTime_iso_ms_z, n.record_items, `${name}: every createdTime is ISO-ms-Z`);
    for (const [k, types] of Object.entries(n.field_types)) {
      assert.ok(!('NoneType' in types), `${name}.${k}: a null was recorded in fields`);
    }
  }
  const empties = Object.values(FIX.nodes).reduce((s, n) => s + n.empty_items, 0);
  assert.ok(empties > 0, 'no recorded 0-row item: the {} rule has no evidence');
  for (const [name, n] of Object.entries(FIX.nodes)) {
    const ek = Object.keys(n.error_item_keys);
    if (ek.length) assert.deepEqual(ek.sort(), ['error', 'message'], `${name}: error item keys`);
  }
});

const GOOD = {
  id: 'recAAAAAAAAAAAAAA', createdTime: '2026-10-19T00:00:00.000Z',
  fields: { sender_key: 'widget:w-mig-1', stage: 'handoff', turn_count: 3, reminded: true,
            last_updated: '2026-10-19T00:00:01.000Z' },
};
const SPEC = { timestampFields: ['last_updated'], numberFields: ['turn_count'] };
const mut = (f) => { const r = JSON.parse(JSON.stringify(GOOD)); f(r); return r; };

test('a record built to the contract passes', () => {
  assert.deepEqual(checkRecord(GOOD, SPEC), []);
  assert.deepEqual(checkEmpty({}), []);
});

test('every way a query could get the shape wrong is caught', () => {
  const cases = {
    'null field (no jsonb_strip_nulls)':      (r) => { r.fields.slot_date = null; },
    'empty-string field (no NULLIF)':         (r) => { r.fields.last_intent = ''; },
    'false checkbox (no CASE WHEN … true)':   (r) => { r.fields.reminded = false; },
    'missing createdTime':                    (r) => { delete r.createdTime; },
    'extra top-level column':                 (r) => { r.sender_key = r.fields.sender_key; },
    'flat row (no fields object)':            (r) => { Object.assign(r, r.fields); delete r.fields; },
    'id not rec+14':                          (r) => { r.id = '42'; },
    'timestamp without ms/Z (raw timestamptz)': (r) => { r.fields.last_updated = '2026-10-19 00:00:01+00'; },
    'createdTime without ms':                 (r) => { r.createdTime = '2026-10-19T00:00:00Z'; },
    'number as string (numeric → text)':      (r) => { r.fields.turn_count = '3'; },
  };
  for (const [label, f] of Object.entries(cases)) {
    assert.ok(checkRecord(mut(f), SPEC).length > 0, `not caught: ${label}`);
  }
  assert.ok(checkEmpty({ success: true }).length > 0, 'not caught: a 0-row read that is not {}');
  assert.ok(checkRecord(null).length > 0, 'not caught: a null item');
  assert.ok(checkRecord([GOOD]).length > 0, 'not caught: an array instead of an item');
  assert.ok(checkRecord(mut((r) => { r.fields = ['x']; })).length > 0, 'not caught: fields as an array');
});
