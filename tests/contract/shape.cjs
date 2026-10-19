/**
 * The Airtable record contract, as the downstream nodes were written against it (MIGRATION-PLAN §3b, §4.2).
 *
 * A data-layer node on Postgres must hand its consumers exactly what an Airtable node handed them:
 *   · a record is `{ id, createdTime, fields }` and NOTHING else at the top level;
 *   · `id` is 'rec' + 14 [A-Za-z0-9] (ruling Q3);
 *   · `createdTime`, and every timestamp inside `fields`, is ISO with milliseconds and a Z;
 *   · inside `fields`: no null, no "" and no false. Airtable omits empty fields, so the SQL builds the
 *     object with jsonb_strip_nulls + NULLIF + "CASE WHEN flag THEN true END";
 *   · numbers are JSON numbers, never numeric strings;
 *   · a 0-row read on an alwaysOutputData node is `{}`.
 * `checkRecord` returns a list of violations (empty = conforms). The D2b-3 runner calls it on rows the
 * real database returns; tests/contract/airtable-shape.test.cjs proves it against the D0 fixtures and
 * against mutants first.
 */
const ID = /^rec[A-Za-z0-9]{14}$/;
const TS = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/;
const TOP = ['createdTime', 'fields', 'id'];

/** @param {object} item   one output item's json
 *  @param {{timestampFields?: string[], numberFields?: string[]}} spec */
function checkRecord(item, spec = {}) {
  const v = [];
  if (item === null || typeof item !== 'object' || Array.isArray(item)) return ['not an object'];
  const keys = Object.keys(item).sort();
  if (keys.join(',') !== TOP.join(',')) v.push(`top-level keys are [${keys}], expected [${TOP}]`);
  if (typeof item.id !== 'string' || !ID.test(item.id)) v.push('id is not rec + 14 alphanumerics');
  if (typeof item.createdTime !== 'string' || !TS.test(item.createdTime)) v.push('createdTime is not ISO-ms-Z');
  const f = item.fields;
  if (f === null || typeof f !== 'object' || Array.isArray(f)) return v.concat('fields is not an object');
  for (const [k, val] of Object.entries(f)) {
    if (val === null) v.push(`fields.${k} is null (Airtable omits it)`);
    else if (val === '') v.push(`fields.${k} is "" (Airtable omits it)`);
    else if (val === false) v.push(`fields.${k} is false (Airtable omits a false checkbox)`);
  }
  for (const k of spec.timestampFields || []) {
    if (k in f && !(typeof f[k] === 'string' && TS.test(f[k]))) v.push(`fields.${k} is not ISO-ms-Z`);
  }
  for (const k of spec.numberFields || []) {
    if (k in f && typeof f[k] !== 'number') v.push(`fields.${k} is ${typeof f[k]}, not a JSON number`);
  }
  return v;
}

/** A 0-row read on an alwaysOutputData node. */
function checkEmpty(item) {
  return item && typeof item === 'object' && !Array.isArray(item) && Object.keys(item).length === 0
    ? [] : ['a 0-row read must be {}'];
}

module.exports = { checkRecord, checkEmpty, ID, TS, TOP };
