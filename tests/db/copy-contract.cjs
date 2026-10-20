/**
 * A copy's READ nodes, run against the real database as salon_ro and checked by tests/contract/shape.cjs
 * (MIGRATION-PLAN §4.2, §3r). contract-run.cjs proves the shape PATTERN per table; this proves each copy
 * node's OWN query: its WHERE clause, its parameters and its projection, exactly as the generated copy
 * holds them.
 *
 * Input: the generated copy (scripts/build-workflow-copy.py output) and a bindings file:
 *   { "<node name>": [ { "params": [...], "rows": <expected row count> }, ... ], ... }
 * Bindings carry real ids, so they live outside the repo and nothing here prints them: the output is node
 * names, row counts and rule violations only (Q16's interim rule). Only SELECT nodes are run; a write node
 * is refused (salon_ro could not run it anyway, and this tool must not pretend it checked one).
 *
 * Run:  set -a; . <the read-only env file>; set +a; node tests/db/copy-contract.cjs <copy.json> <bindings.json>
 */
const path = require('node:path');
const { readFileSync } = require('node:fs');
const { Client } = require(path.join(__dirname, '..', '..', 'web', 'node_modules', 'pg'));
const { checkRecord } = require(path.join(__dirname, '..', 'contract', 'shape.cjs'));
const SPEC = require(path.join(__dirname, '..', '..', 'db', 'shape-spec.json'));

function specFor(table, query) {
  const cols = SPEC.tables[table];
  const only = query.match(/jsonb_build_object\((.*?)\)\) AS fields/s);
  const named = only ? new Set([...only[1].matchAll(/'(\w+)',/g)].map((m) => m[1])) : null;
  const use = cols.filter(([name]) => !named || named.has(name));
  return { timestampFields: use.filter(([, k]) => k === 'ts').map(([n]) => n), numberFields: use.filter(([, k]) => k === 'num').map(([n]) => n) };
}

(async () => {
  if (process.env.PGUSER !== 'salon_ro') { console.error('copy-contract: refused — PGUSER is not salon_ro'); process.exit(2); }
  const [copyPath, bindPath] = process.argv.slice(2);
  if (!copyPath || !bindPath) { console.error('usage: copy-contract.cjs <copy.json> <bindings.json>'); process.exit(2); }
  const copy = JSON.parse(readFileSync(copyPath, 'utf8'));
  const binds = JSON.parse(readFileSync(bindPath, 'utf8'));
  const c = new Client();
  c.on('error', (e) => { console.error('copy-contract: connection error —', e.code || 'no SQLSTATE'); process.exit(2); });
  await c.connect();
  // The env says salon_ro; the SERVER decides. Check the session's role before running anything.
  if ((await c.query('select current_user as u')).rows[0].u !== 'salon_ro') { console.error('copy-contract: refused — the session is not salon_ro'); process.exit(2); }
  let ok = true, cases = 0;
  for (const [name, list] of Object.entries(binds)) {
    const node = copy.nodes.find((n) => n.name === name);
    const q = node && node.type === 'n8n-nodes-base.postgres' ? node.parameters.query : null;
    if (!q || !/^\s*SELECT\b/i.test(q)) { console.log(`✗ ${name}: not a SELECT Postgres node in the copy — refused`); ok = false; continue; }
    const table = (q.match(/FROM salon\.(\w+)/) || [])[1];
    for (const b of list) {
      cases += 1;
      let rows, err = null;
      try { rows = (await c.query(q, b.params)).rows; } catch (e) { err = e.code || 'ERR'; }
      const v = rows ? rows.flatMap((r) => checkRecord(r, specFor(table, q))) : [];
      const pass = !err && rows.length === b.rows && v.length === 0;
      ok = ok && pass;
      console.log(`${pass ? '✓' : '✗'} ${name.padEnd(30)} expected ${b.rows} row(s), got ${err ? 'ERROR ' + err : rows.length}` +
        ` · violations ${v.length}${v.length ? ': ' + [...new Set(v)].join(' | ') : ''}`);
    }
  }
  await c.end();
  console.log(`copy-contract: ${ok && cases > 0 ? 'OK' : 'FAILED'} — ${cases} case(s)`);
  process.exit(ok && cases > 0 ? 0 : 1);
})().catch((e) => { console.error('copy-contract: aborted —', e.code || 'no SQLSTATE'); process.exit(2); });   // code only: a connect error's message carries the host
