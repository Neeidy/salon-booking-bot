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
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
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

// ── PUBLIC-DEPLOY HONESTY GATE ──────────────────────────────────────────────────────────────────
// A demoMode:false build carries NO mock ribbon, NO demo footer notice and NO noindex. That is correct
// for a real client. It is a LIE for our fictional example clients: publishing "Hofgasse Barbers" would
// put a business that does not exist on the public web, indexable, with nothing saying it is a sample
// (.claude/rules/honesty-demos.md). A ROADMAP warning does not stop a deploy — this does.
//
// Public is assumed when DEPLOY_TARGET=public, or when a hosting platform announces itself
// (VERCEL_ENV=production|preview). Assuming public on detection is the fail-safe direction.
const deployTarget = (process.env.DEPLOY_TARGET || '').toLowerCase();
const vercelEnv = (process.env.VERCEL_ENV || '').toLowerCase();
const isPublic = deployTarget === 'public' || vercelEnv === 'production' || vercelEnv === 'preview';
const isDemo = isDemoMode(config);
// Detect a fictional example client by CONTENT, not by file path. Checking the path was not enough:
// piping an example file's JSON through CLIENT_CONFIG_JSON made it look like a real client config and
// the hard block silently did not fire (found by drilling this gate, 2026-09-04). The committed example
// configs are the definitive list of shops that do not exist, so compare against their business names.
function committedExampleNames() {
  const dir = resolve(SITE_ROOT, '../../config');
  try {
    return readdirSync(dir)
      .filter((f) => /^client\.config\.example.*\.json$/.test(f))
      .map((f) => {
        try { return JSON.parse(readFileSync(join(dir, f), 'utf8'))?.business?.name; } catch { return null; }
      })
      .filter(Boolean);
  } catch { return []; }
}
const exampleNames = committedExampleNames();
const fromCommittedExample = exampleNames.includes(config.business.name);

if (isPublic && !isDemo) {
  if (fromCommittedExample) {
    // No acknowledgement can make this right: a committed example client is fictional by definition.
    fail(`refusing to build "${config.business.name}" for a PUBLIC target: it is a committed EXAMPLE client\n`
      + `  (source: ${source}; matched against config/client.config.example*.json).\n`
      + '  An example config describes a shop that does not exist, and demoMode:false strips every marker\n'
      + '  that would say so. A real client deployment supplies its config through CLIENT_CONFIG_JSON or a\n'
      + '  gitignored config/client.config.json — never through a committed example.');
  }
  const ack = process.env.CLIENT_DEPLOYMENT_ACK || '';
  if (ack !== config.business.name) {
    fail('this is a PUBLIC build of a demoMode:false config — it will show NO "this is a demo" marker.\n'
      + `  If "${config.business.name}" is a real client you are deploying for, say so deliberately:\n`
      + `      CLIENT_DEPLOYMENT_ACK="${config.business.name}"\n`
      + (ack ? `  (got CLIENT_DEPLOYMENT_ACK="${ack}", which does not match the config's business name)\n` : '')
      + '  The acknowledgement must name the business, so it cannot be copied blindly between clients.');
  }
  console.warn(`\n⚠  PUBLIC build for a REAL client — "${config.business.name}". No demo markers will be shown.`);
}

// `site` is OPTIONAL at the schema root so the engine's own partial Load Config still validates — but
// THIS build cannot render a page without it, and falling back to hardcoded copy would put the shop's
// voice back in the code as a second source of truth. So require it here, where it is actually needed.
if (!config.site) {
  fail('the config has no `site` block (page copy). The site cannot be built without it — adding fallback '
    + 'copy in the components would re-create the very second-source-of-truth this block removes.');
}

writeFileSync(OUT, JSON.stringify(config, null, 2) + '\n');
console.log(`config: ${source} → config.generated.json  (business="${config.business.name}", demoMode=${isDemoMode(config)}, services=${config.services.length})`);
