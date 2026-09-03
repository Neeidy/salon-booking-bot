#!/usr/bin/env node
/**
 * Build-time config bridge (Phase 6, decision approved 2026-09-03).
 *
 * WHY: the app must never read the filesystem. Measured on the first real `next build` — a dynamic
 * `readFileSync` makes Next trace the whole project into the server output, and `config/` + `schemas/`
 * are NOT traced, so any non-static read would fail on a real deployment. On top of that,
 * config/client.config.json is gitignored, so on a git-based deploy it never exists at all.
 *
 * So config enters ONCE, here, at build time:
 *   1. CLIENT_CONFIG_JSON env var  — how a real client's config reaches a deploy without touching git
 *   2. config/client.config.json   — local development
 *   3. config/client.config.example.json — the committed demo mock (announced loudly, never silent)
 * …validated against the COMMITTED schema by the SAME validator the loader uses, then written to
 * config.generated.json (gitignored) which the app imports as a plain module.
 *
 * FAIL-CLOSED, by explicit instruction: a broken or contract-violating CLIENT_CONFIG_JSON FAILS THE
 * BUILD. It never silently falls back to disk — a deploy that quietly served demo data while the
 * operator believed it was serving a client's would be exactly the silent failure this repo forbids.
 */
import { writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadConfigDetailed, validateConfigObject, isDemoMode } from '@salon/shared/config';

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE_ROOT = resolve(HERE, '..');
const OUT = join(SITE_ROOT, 'config.generated.json');

function fail(msg) {
  console.error('\n✗ BUILD STOPPED — client config: ' + msg + '\n');
  process.exit(1);
}

let config;
let source;
const raw = process.env.CLIENT_CONFIG_JSON;

if (raw && raw.trim()) {
  // FAIL-CLOSED: the operator explicitly supplied a config. If it is broken, that is a deployment
  // mistake to surface now — NOT a reason to quietly ship the demo mock instead.
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    fail(`CLIENT_CONFIG_JSON is set but is not valid JSON (${e.message}). Refusing to fall back to disk.`);
  }
  try {
    config = validateConfigObject(parsed, { source: 'CLIENT_CONFIG_JSON' });
  } catch (e) {
    fail(`${e.message}\n  Refusing to fall back to disk: you asked for THIS config, so shipping a different one silently would be worse than failing.`);
  }
  source = 'CLIENT_CONFIG_JSON (env)';
} else {
  let detailed;
  try {
    detailed = loadConfigDetailed();
  } catch (e) {
    fail(`${e.message}\n  Set CLIENT_CONFIG_JSON, or provide config/client.config.json.`);
  }
  config = detailed.config;
  source = detailed.configPath;
  if (detailed.usedFallback) {
    // Valid, but must never be silent: a demo deploy mistaken for a client deploy is a lie on a page.
    console.warn('\n⚠  using example config — DEMO MODE. No CLIENT_CONFIG_JSON and no config/client.config.json;');
    console.warn('   this build serves the committed MOCK client (' + config.business.name + ').');
    if (!isDemoMode(config)) {
      fail('the example config is being used but demoMode is not true — the mock ribbon would be hidden on a demo build. Refusing to ship a demo that does not say it is one.');
    }
  }
}

writeFileSync(OUT, JSON.stringify(config, null, 2) + '\n');
console.log(`config: ${source} → config.generated.json  (business="${config.business.name}", demoMode=${isDemoMode(config)}, services=${config.services.length})`);
