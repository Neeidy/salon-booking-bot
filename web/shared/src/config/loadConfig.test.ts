/**
 * loadConfig contract tests.
 *
 * The point is NOT "does it read a file" — it is that a config which violates the committed contract
 * CANNOT get through. Each rejection case below is a real failure mode: a missing required block, a
 * typo'd key (the class of bug root-level additionalProperties:false was closed for in FIX-2), and a
 * wrong type. A guard that has never been shown to fail is not a guard.
 *
 * Run: npm test -w @salon/shared
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, mkdirSync, mkdtempSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadConfig, loadConfigDetailed, resolveConfigPath, isDemoMode, ConfigContractError } from './loadConfig.ts';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
const EXAMPLE = join(REPO_ROOT, 'config/client.config.example.json');
const SCHEMA = join(REPO_ROOT, 'schemas/client.config.schema.json');

/** Write a mutated copy of the example to a temp file and return its path. */
function sabotage(mutate: (c: Record<string, unknown>) => void): string {
  const cfg = JSON.parse(readFileSync(EXAMPLE, 'utf8'));
  mutate(cfg);
  const file = join(mkdtempSync(join(tmpdir(), 'cfg-')), 'client.config.json');
  writeFileSync(file, JSON.stringify(cfg, null, 2));
  return file;
}

test('accepts the committed example and returns real values', () => {
  const cfg = loadConfig({ configPath: EXAMPLE });
  assert.equal(cfg.business.name, 'Demo Barber Co.');
  assert.equal(cfg.business.timezone, 'Europe/Vienna');
  assert.ok(cfg.services.length >= 1);
});

test('demoMode: the committed example is a DEMO, so the ribbon stays on', () => {
  assert.equal(isDemoMode(loadConfig({ configPath: EXAMPLE })), true);
});

test('demoMode: absent means false — a real client install shows no mock ribbon', () => {
  const cfg = loadConfig({ configPath: sabotage((c) => { delete c.demoMode; }) });
  assert.equal(isDemoMode(cfg), false);
});

test('demoMode: explicit false is honoured', () => {
  assert.equal(isDemoMode(loadConfig({ configPath: sabotage((c) => { c.demoMode = false; }) })), false);
});

test('REJECTS a missing required block (bot)', () => {
  const file = sabotage((c) => { delete c.bot; });
  assert.throws(() => loadConfig({ configPath: file }), (e: unknown) => {
    assert.ok(e instanceof ConfigContractError);
    assert.match(e.message, /must have required property 'bot'/);
    return true;
  });
});

// NOTE: this closure is enforced at RUNTIME only. The generated ClientConfig type carries an index
// signature (the schema's ^\$comment patternProperties force one), so TypeScript will NOT flag a
// typo'd root key at compile time — this test is the only thing that catches it.
test('REJECTS a typo\'d root key — the FIX-2 closure must hold for the frontend too', () => {
  const file = sabotage((c) => { delete c.demoMode; c.demoMod = true; });
  assert.throws(() => loadConfig({ configPath: file }), (e: unknown) => {
    assert.ok(e instanceof ConfigContractError);
    assert.match(e.message, /additionalProperties/);
    return true;
  });
});

test('REJECTS a wrong type (demoMode as a string)', () => {
  const file = sabotage((c) => { c.demoMode = 'true'; });
  assert.throws(() => loadConfig({ configPath: file }), (e: unknown) => {
    assert.ok(e instanceof ConfigContractError);
    // Pinned to the TYPE error specifically. A bare /demoMode/ match would still pass if the key were
    // dropped from the schema entirely (it would then fail as an unknown root key, whose message also
    // contains "demoMode") — i.e. the test would go green while proving nothing about type checking.
    assert.match(e.message, /\/demoMode type .* must be boolean/);
    return true;
  });
});

test('REJECTS unparseable JSON instead of half-loading it', () => {
  const file = join(mkdtempSync(join(tmpdir(), 'cfg-')), 'client.config.json');
  writeFileSync(file, '{ "business": ');
  assert.throws(() => loadConfig({ configPath: file }), ConfigContractError);
});

test('REJECTS a missing file loudly', () => {
  assert.throws(() => loadConfig({ configPath: '/nonexistent/client.config.json' }), ConfigContractError);
});

test('REFUSES to trust a config it cannot validate (schema missing)', () => {
  assert.throws(
    () => loadConfig({ configPath: EXAMPLE, schemaPath: '/nonexistent/schema.json' }),
    (e: unknown) => {
      assert.ok(e instanceof ConfigContractError);
      assert.match(e.message, /will not be trusted/);
      return true;
    },
  );
});

test('falls back to the committed mock example when no client config is on disk', () => {
  const r = resolveConfigPath({ repoRoot: mkdtempSync(join(tmpdir(), 'emptyroot-')) });
  assert.equal(r.usedFallback, true);
  assert.match(r.path, /client\.config\.example\.json$/);
});

test('prefers the real client config when it exists', () => {
  const root = mkdtempSync(join(tmpdir(), 'root-'));
  mkdirSync(join(root, 'config'), { recursive: true });
  writeFileSync(join(root, 'config/client.config.json'), '{}');
  const r = resolveConfigPath({ repoRoot: root });
  assert.equal(r.usedFallback, false);
  assert.match(r.path, /config\/client\.config\.json$/);
});

test('REJECTS an unusable schema as a ConfigContractError, not a raw SyntaxError', () => {
  // Regression: the schema read + ajv.compile used to sit outside the try/catch, so a corrupt schema
  // escaped as a bare SyntaxError — breaking the documented contract that every failure here is a
  // ConfigContractError carrying the config path.
  const badSchema = join(mkdtempSync(join(tmpdir(), 'schema-')), 'client.config.schema.json');
  writeFileSync(badSchema, '{ "type": "object"');
  assert.throws(() => loadConfig({ configPath: EXAMPLE, schemaPath: badSchema }), (e: unknown) => {
    assert.ok(e instanceof ConfigContractError, `expected ConfigContractError, got ${(e as Error).name}`);
    assert.match(e.message, /not a usable JSON Schema/);
    assert.equal(e.configPath, EXAMPLE);
    return true;
  });
});

test('smoke: loadConfig() with NO arguments works — the call shape the README documents', () => {
  // Guards DEFAULT_REPO_ROOT's directory depth: every other test passes an explicit path, so a wrong
  // depth would otherwise pass the whole suite and only break at build time. NOTE: which FILE this
  // resolves to depends on the environment — with a real config/client.config.json present it validates
  // that file instead of the example. That is fine; the depth is what is under test here.
  const cfg = loadConfig();
  assert.equal(typeof cfg.business.name, 'string');
  assert.ok(cfg.business.name.length > 0);
});

test('reports WHICH file it used — a silently-missing client config must not look like success', () => {
  // Built on a SYNTHETIC root, never on the real repo: asserting "usedFallback is true here" against the
  // real tree would make this test depend on the ABSENCE of gitignored config/client.config.json — so it
  // would fail on every real client install, and this suite is a pre-push gate.
  const root = mkdtempSync(join(tmpdir(), 'root-'));
  mkdirSync(join(root, 'config'), { recursive: true });
  copyFileSync(EXAMPLE, join(root, 'config/client.config.example.json'));

  const fell = loadConfigDetailed({ repoRoot: root, schemaPath: SCHEMA });
  assert.equal(fell.usedFallback, true, 'no client.config.json in this synthetic root → fallback');
  assert.match(fell.configPath, /client\.config\.example\.json$/);

  copyFileSync(EXAMPLE, join(root, 'config/client.config.json'));
  const real = loadConfigDetailed({ repoRoot: root, schemaPath: SCHEMA });
  assert.equal(real.usedFallback, false, 'a real client config is present → NOT a fallback');
  assert.match(real.configPath, /config\/client\.config\.json$/);

  const explicit = loadConfigDetailed({ configPath: EXAMPLE });
  assert.equal(explicit.usedFallback, false, 'passing the example explicitly is a choice, not a fallback');
});

test('logoUrl: the ^(https://|/) pattern is a REAL constraint, not decoration', () => {
  // The old "format":"uri" enforced nothing. This value is rendered on the PUBLIC site.
  for (const bad of ['http://insecure.example.com/logo.png', 'javascript:alert(1)', '//cdn.example.com/l.png']) {
    assert.throws(() => loadConfig({ configPath: sabotage((c) => { (c.branding as Record<string, unknown>).logoUrl = bad; }) }),
      (e: unknown) => {
        assert.ok(e instanceof ConfigContractError);
        assert.match(e.message, /\/branding\/logoUrl pattern/);
        return true;
      }, `expected ${bad} to be rejected`);
  }
  for (const good of ['https://example.com/logo.png', '/logo.svg']) {
    const cfg = loadConfig({ configPath: sabotage((c) => { (c.branding as Record<string, unknown>).logoUrl = good; }) });
    assert.equal(cfg.branding?.logoUrl, good, `expected ${good} to be accepted`);
  }
});
