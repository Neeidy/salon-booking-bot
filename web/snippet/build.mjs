#!/usr/bin/env node
/**
 * Snippet build — bakes config + endpoint into one IIFE.
 *
 * THE CONFIG GATE IS NOT COPIED HERE. `web/site/scripts/build-config.mjs` already resolves the client
 * config, validates it against the committed schema, and enforces the public-deploy honesty rules
 * (no committed example client on a public target; CLIENT_DEPLOYMENT_ACK for any demoMode:false public
 * build). Re-implementing any of that would create the second truth `contract-integrity.md` forbids, so
 * this script CONSUMES that gate's output instead: `npm run build` runs it via `prebuild`, and this file
 * refuses to continue if `config.generated.json` is absent. The snippet therefore cannot be built along a
 * path where the gate did not run.
 *
 * WHAT IS BAKED, AND WHY SO LITTLE: the bundle is served to strangers on a client's website. It carries
 * only what the widget actually renders — the shop name, the message templates the engine deliberately
 * does not send, and demoMode. Not the whole config: services, hours, address and site copy are the
 * SITE's business, and shipping them here would publish more than the widget needs.
 *
 * SECRETS: the webhook URL contains the production n8n host, which is a redaction target in this repo
 * (scripts/check-no-host-leak.sh). So (a) the built file is gitignored — the guard scans untracked files
 * too, and would go red if it ever sat in the tree un-ignored — and (b) this script never prints the URL,
 * only its pathname. The Turnstile site key is public by design but is still not echoed.
 */
import { existsSync, readFileSync, mkdirSync, writeFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE = resolve(HERE, '../site');
const GENERATED = join(SITE, 'config.generated.json');
const OUTFILE = join(SITE, 'public/barber-widget.js');
const CHECK_ONLY = process.argv.includes('--check');

function fail(msg) {
  console.error('\n✗ SNIPPET BUILD STOPPED — ' + msg + '\n');
  process.exit(1);
}

/* ── 1. the config gate's output ───────────────────────────────────────────────────────────────── */
if (!existsSync(GENERATED)) {
  fail('web/site/config.generated.json is missing.\n'
    + '  It is produced by web/site/scripts/build-config.mjs, which is where the schema validation and the\n'
    + '  public-deploy honesty gate live. Run `npm run build -w @salon/snippet` (its prebuild runs that script)\n'
    + '  rather than calling this file directly.');
}
const config = JSON.parse(readFileSync(GENERATED, 'utf8'));
if (!config?.business?.name) fail('config.generated.json has no business.name — it did not come from the config gate.');
if (!config?.messageTemplates) fail('config.generated.json has no messageTemplates — the widget cannot fill the two branches the engine leaves empty.');

/* ── 2. endpoint + site key ────────────────────────────────────────────────────────────────────── */
// Read the site's own .env.local when the vars are not already exported, so the local flow is one command.
// Values are never logged from here.
function envFromSiteDotLocal() {
  const p = join(SITE, '.env.local');
  if (!existsSync(p)) return {};
  const out = {};
  for (const line of readFileSync(p, 'utf8').split('\n')) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (m) out[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
  return out;
}
const fromFile = envFromSiteDotLocal();
const webhookUrl = process.env.NEXT_PUBLIC_WEBHOOK_URL || fromFile.NEXT_PUBLIC_WEBHOOK_URL || '';
const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || fromFile.NEXT_PUBLIC_TURNSTILE_SITE_KEY || '';

if (!webhookUrl) fail('no NEXT_PUBLIC_WEBHOOK_URL (env or web/site/.env.local).');
if (!siteKey) fail('no NEXT_PUBLIC_TURNSTILE_SITE_KEY (env or web/site/.env.local).');

// PATH EQUALITY, not a wildcard. A wildcard shape check is exactly what let the n8n EDITOR path
// (/workflow/<id>/webhook/...) through in 6a — it returns no CORS headers, so every send failed in the
// browser while the check said the URL was fine. Compare the whole pathname.
const EXPECTED_PATH = '/webhook/barber-inbound';
let parsed;
try { parsed = new URL(webhookUrl); } catch { fail('NEXT_PUBLIC_WEBHOOK_URL is not a valid URL.'); }
if (parsed.protocol !== 'https:') fail(`the webhook URL must be https (got ${parsed.protocol}).`);
if (parsed.pathname !== EXPECTED_PATH) {
  fail(`the webhook URL's path is "${parsed.pathname}", expected exactly "${EXPECTED_PATH}".\n`
    + '  A production webhook path is not the n8n editor path — that mistake was made once (6a) and cost a\n'
    + '  live drill, because the editor path answers without CORS headers and every send fails in the browser.');
}

/* ── 3. the baked payload ──────────────────────────────────────────────────────────────────────── */
const baked = {
  business: { name: config.business.name },
  messageTemplates: config.messageTemplates,
  demoMode: config.demoMode === true,
};

if (CHECK_ONLY) {
  console.log(`snippet check: OK — business="${baked.business.name}", demoMode=${baked.demoMode}, path="${parsed.pathname}"`);
  process.exit(0);
}

/* ── 4. bundle ─────────────────────────────────────────────────────────────────────────────────── */
mkdirSync(dirname(OUTFILE), { recursive: true });
await esbuild.build({
  entryPoints: [join(HERE, 'src/index.ts')],
  bundle: true,
  minify: true,
  format: 'iife',           // one self-contained function: no globals, no module loader on the host page
  target: ['es2019'],       // wide enough for the browsers a barbershop's customers actually use
  outfile: OUTFILE,
  legalComments: 'none',
  define: {
    __BAKED_CONFIG__: JSON.stringify(baked),
    __WEBHOOK_URL__: JSON.stringify(webhookUrl),
    __TURNSTILE_SITE_KEY__: JSON.stringify(siteKey),
  },
});

const bytes = statSync(OUTFILE).size;
console.log(`snippet: → web/site/public/barber-widget.js  (${(bytes / 1024).toFixed(1)} kB, business="${baked.business.name}", demoMode=${baked.demoMode}, path="${parsed.pathname}")`);
