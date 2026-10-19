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
