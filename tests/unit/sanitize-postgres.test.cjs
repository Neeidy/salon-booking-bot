/**
 * The sanitizer covers a POSTGRES credential (MIGRATION-PLAN D2b-1).
 *
 * scripts/check-content-parity.py's committed-side check walks every node's `credentials` map and fails on
 * any credential id that is not a placeholder, of ANY credential type. That generic walk is what is
 * supposed to cover the new type; this test proves it on a fake Postgres block instead of assuming it:
 *   · a Postgres node carrying a real-looking credential id → SANITISE FAILURE (exit 1);
 *   · the same node carrying the placeholder → no sanitise failure (exit 2: without credentials the
 *     script refuses the live PARITY half and says so, which is the documented no-network behaviour).
 * The sanitise half runs on the committed file alone, with the environment stripped.
 *
 * Run: node tests/unit/sanitize-postgres.test.cjs
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync, writeFileSync, mkdtempSync, rmSync } = require('node:fs');
const { join } = require('node:path');
const { tmpdir } = require('node:os');
const { spawnSync } = require('node:child_process');

const ROOT = join(__dirname, '..', '..');
const base = JSON.parse(readFileSync(join(ROOT, 'n8n', 'workflow.drill-state.sanitized.json'), 'utf8'));

function run(credId) {
  const wf = JSON.parse(JSON.stringify(base));
  wf.nodes.push({ name: 'PG Probe', type: 'n8n-nodes-base.postgres', typeVersion: 2.6,
    parameters: { operation: 'executeQuery', query: 'SELECT 1', options: {} },
    credentials: { postgres: { id: credId, name: 'Salon Postgres' } } });
  const dir = mkdtempSync(join(tmpdir(), 'sanitize-pg-'));
  const f = join(dir, 'export.json');
  writeFileSync(f, JSON.stringify(wf));
  const r = spawnSync('python3', [join(ROOT, 'scripts', 'check-content-parity.py'), f],
    { env: { PATH: process.env.PATH }, encoding: 'utf8' });
  rmSync(dir, { recursive: true, force: true });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
}

test('a real-looking Postgres credential id is a SANITISE FAILURE', () => {
  const r = run('Xq7Lm2Pz9Rt4Wv1K');
  assert.equal(r.code, 1, r.out);
  assert.match(r.out, /SANITISE FAILURE/);
  assert.match(r.out, /credential id .*PG Probe/);
});

test('the placeholder passes the sanitise half', () => {
  const r = run('REPLACE_WITH_POSTGRES_CREDENTIAL_ID');
  assert.doesNotMatch(r.out, /SANITISE FAILURE/, r.out);
  assert.equal(r.code, 2, r.out);
});

// D5 (MIGRATION-PLAN §3t): the same property on a REAL copy export, not a planted node. The Main copy carries 17
// Postgres nodes, all on the placeholder; swapping ONE of them for a real-looking id must be caught, by name.
function runCopy(mutate) {
  const wf = JSON.parse(readFileSync(join(ROOT, 'n8n', 'workflow.main.copy.sanitized.json'), 'utf8'));
  mutate(wf);
  const dir = mkdtempSync(join(tmpdir(), 'sanitize-pg-copy-'));
  const f = join(dir, 'export.json');
  writeFileSync(f, JSON.stringify(wf));
  const r = spawnSync('python3', [join(ROOT, 'scripts', 'check-content-parity.py'), f],
    { env: { PATH: process.env.PATH }, encoding: 'utf8' });
  rmSync(dir, { recursive: true, force: true });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
}

test('the Main copy export as committed passes the sanitise half', () => {
  const pg = JSON.parse(readFileSync(join(ROOT, 'n8n', 'workflow.main.copy.sanitized.json'), 'utf8'))
    .nodes.filter((n) => n.type === 'n8n-nodes-base.postgres');
  assert.equal(pg.length, 17, 'the Main copy should carry 17 Postgres nodes');
  const r = runCopy(() => {});
  assert.doesNotMatch(r.out, /SANITISE FAILURE/, r.out);
});

test('ONE Postgres node of the Main copy with a real-looking credential id is a SANITISE FAILURE, named', () => {
  const r = runCopy((wf) => {
    const n = wf.nodes.find((x) => x.name === 'Record Alert Class');
    n.credentials.postgres.id = 'Xq7Lm2Pz9Rt4Wv1K';
  });
  assert.equal(r.code, 1, r.out);
  assert.match(r.out, /SANITISE FAILURE/);
  assert.match(r.out, /credential id .*Record Alert Class/);
});
