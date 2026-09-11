#!/usr/bin/env node
/**
 * Snippet build — bakes config + endpoint into one IIFE.
 *
 * THE CONFIG GATE IS NOT COPIED HERE. `web/site/scripts/build-config.mjs` already resolves the client
 * config, validates it against the committed schema, and enforces the public-deploy honesty rules
 * (no committed example client on a public target; CLIENT_DEPLOYMENT_ACK for any demoMode:false public
 * build). Re-implementing any of that would create the second truth `contract-integrity.md` forbids, so
 * this script CONSUMES that gate's output instead: `npm run build` runs it via `prebuild`, and this file
 * refuses to continue if `config.generated.json` is absent.
 * ⚠ SCOPE, stated honestly: that makes `npm run build` unable to SKIP the gate. It does not make the file
 * trustworthy in general — there is no provenance stamp on it and no freshness check, so a hand-written or
 * stale `config.generated.json` would build fine. The earlier wording here said "cannot be built along a
 * path where the gate did not run", which claimed more than the code checks (code-reviewer, 2026-09-10).
 *
 * WHAT IS BAKED, AND WHY SO LITTLE: the bundle is served to strangers on a client's website. It carries
 * only what the widget actually renders — the shop name, the message templates the engine deliberately
 * does not send, and `demoMode`, which draws a "Demo" tag in the panel header so a widget running on mock
 * data says so on someone else's site (honesty-demos.md). Not the whole config: services, hours, address and site copy are the
 * SITE's business, and shipping them here would publish more than the widget needs.
 *
 * SECRETS: the webhook URL contains the production n8n host, which is a redaction target in this repo
 * (scripts/check-no-host-leak.sh). So (a) the built file is gitignored — the guard scans untracked files
 * too, and would go red if it ever sat in the tree un-ignored — and (b) this script never prints the URL,
 * only its pathname. The Turnstile site key is public by design but is still not echoed.
 */
import { existsSync, readFileSync, mkdirSync, statSync, mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
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
// The committed schema requires `messageTemplates` to EXIST but defines no keys inside it, so a config
// with `{}` satisfied both the schema gate and this one — and every fallback then rendered as
// `undefined`, i.e. an empty bubble. Check the keys this widget actually reads, by name.
const NEEDED_TEMPLATES = ['handoff', 'notUnderstood'];
const missing = NEEDED_TEMPLATES.filter((k) => typeof config?.messageTemplates?.[k] !== 'string' || !config.messageTemplates[k]);
if (missing.length) {
  fail(`config.generated.json is missing messageTemplates: ${missing.join(', ')}.\n`
    + '  These are the two branches where the engine deliberately sends NO text and the widget must supply it\n'
    + '  (400 invalid_payload and 503 state_unavailable). Without them the visitor gets an empty bubble.');
}

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
// Only the keys the transport actually reads. ⚠ Until 2026-09-11 this baked `config.messageTemplates`
// WHOLE — all 29 keys, `cancelDone` and every other engine-owned line included — into a bundle served to
// strangers on a client's site, while the comment at the top of this file said the bundle carries "only
// what the widget actually renders" (code-reviewer measured both). Narrowing the payload to the gate's
// own list is the fix that makes the sentence true AND makes gate and payload one truth instead of two.
// The disproving search, shown, because this is a claim about shape. ⚠ The first version printed here
// was `grep -rn 't\.[a-zA-Z]*' chatClient.ts`, which returns 21 lines — most of them prose — so it did
// NOT measure the sentence it was quoted for (code-reviewer, 2026-09-11; the same class of error this
// round had just corrected elsewhere). The search below excludes comment lines and is the one actually
// run:
//   $ grep -nE '^\s*[^*/].*\bt\.[a-zA-Z]+' web/shared/src/chat/chatClient.ts | grep -oE '\bt\.[a-zA-Z]+' | sort -u
//     t.handoff
//     t.notUnderstood
//   $ grep -rn 'messageTemplates' web/snippet/src web/shared/src → no other consumer reads a key
// `welcomeLine()` is a hardcoded string in the transport, not a template, so nothing else is lost.
const baked = {
  business: { name: config.business.name },
  messageTemplates: Object.fromEntries(NEEDED_TEMPLATES.map((k) => [k, config.messageTemplates[k]])),
  demoMode: config.demoMode === true,
};

/**
 * esbuild's log is silenced, so warnings are printed from the RESULT — on every path, always.
 * Defensive about the shape: this is called from BOTH build paths, and on the real build path a throw
 * here would print the bare Node stack trace this file exists to avoid (security-auditor F10).
 */
function reportWarnings(result) {
  const warnings = result?.warnings;
  if (!Array.isArray(warnings)) return;
  for (const w of warnings) {
    console.warn(`⚠ snippet warning: ${w.text}`
      + (w.location ? `  (${w.location.file}:${w.location.line})` : ''));
  }
}

/**
 * The ONE build configuration. The freshness check rebuilds with exactly this, so "the bundle on disk
 * equals the bundle this source produces" is a real comparison and not two configurations that happen
 * to agree today (.claude/rules/contract-integrity.md).
 */
function buildOptions(outfile) {
  return {
    entryPoints: [join(HERE, 'src/index.ts')],
    bundle: true,
    minify: true,
    format: 'iife',         // one self-contained function; no module loader is added to the host page.
                            // NOT "no globals": the widget deliberately sets `__barberTurnstileLoading`
                            // to guard a double script load, and that is listed on /install and in ARCH-DEC.
    target: ['es2019'],     // wide enough for the browsers a barbershop's customers actually use
    outfile,
    legalComments: 'none',
    // ONE VOICE, on BOTH paths. esbuild's own log is silenced and everything is reported from the
    // RESULT instead, because a log level is a DISPLAY setting: a warning that exists only at one
    // display setting is a warning nobody is guaranteed to see.
    //
    // Two rounds of getting this wrong, both recorded rather than tidied away. First `--check` printed
    // a raw esbuild stack trace while every other failure here printed "✗ SNIPPET BUILD STOPPED"
    // (code-reviewer #19). Then a blanket `logLevel:'silent'` fixed that and muted esbuild WARNINGS on
    // the REAL build, which has no try/catch of its own — measured by `security-auditor` with an
    // `impossible-typeof` warning: default printed it, silent printed nothing, both exited 0
    // (BULGU-3, 2026-09-12). `CLAUDE.md`: failures must be VISIBLE, never silent.
    logLevel: 'silent',
    define: {
      __BAKED_CONFIG__: JSON.stringify(baked),
      __WEBHOOK_URL__: JSON.stringify(webhookUrl),
      __TURNSTILE_SITE_KEY__: JSON.stringify(siteKey),
    },
  };
}

if (CHECK_ONLY) {
  // ⚠ The check used to validate the INPUTS and then report OK, which made it possible for the gate to
  // pass while the product did not exist: `public/barber-widget.js` is a gitignored build artefact, so a
  // tree that had never run the build reported a healthy snippet and shipped a 404 (Codex CRT #13,
  // finding 4). A check that cannot see the absence of its own output is not checking the thing anyone
  // cares about. It now requires the bundle, and a plausible one.
  if (!existsSync(OUTFILE)) {
    fail('the bundle web/site/public/barber-widget.js does not exist.\n'
      + '  --check validates the config and the endpoint, but the deployable artefact is the BUNDLE, and a\n'
      + '  gate that reports OK without it lets a site ship whose one-line embed 404s.\n'
      + '  Run `npm run build -w @salon/snippet --prefix web` (the site\'s prebuild does this too).');
  }
  const size = statSync(OUTFILE).size;
  if (size < 4096) {
    fail(`the bundle exists but is only ${size} B — too small to be a real build.\n`
      + '  A truncated or placeholder file passes an existence check and fails a visitor.');
  }

  // FRESHNESS. Existence is not enough: the gate used to ask "is there a plausible bundle" and never
  // "is this the build of the CURRENT source". Measured in the CRT #13 pre-push audit — 17840 B on
  // disk against 18278 B from the committed source, gate GREEN. A stale bundle is worse than a missing
  // one, because the missing one 404s loudly while the stale one serves yesterday's product.
  // So: rebuild into a temp dir with the SAME options and compare bytes.
  const tmp = mkdtempSync(join(tmpdir(), 'snippet-freshness-'));
  const probe = join(tmp, 'barber-widget.js');
  let fresh;
  try {
    reportWarnings(await esbuild.build(buildOptions(probe)));
    fresh = readFileSync(probe);
  } catch (e) {
    // One failure shape for the whole file. Without this, a broken SOURCE made --check exit on a raw
    // esbuild stack trace while every other failure here printed "✗ SNIPPET BUILD STOPPED"
    // (code-reviewer S6). ⚠ `fail()` calls process.exit, so `finally` NEVER RUNS on this path — the
    // first cut therefore stranded a temp directory on every ordinary build failure, not just on a
    // SIGKILL as this round's own notes claimed (code-reviewer #15, 2026-09-12). Clean up FIRST.
    // The message carries esbuild's own first error text rather than `e.message`, which is only
    // "Build failed with 1 error:" and says nothing (#19).
    rmSync(tmp, { recursive: true, force: true });
    const detail = e?.errors?.[0]?.text ?? (e?.message ? String(e.message).split('\n')[0] : String(e));
    const where = e?.errors?.[0]?.location;
    fail('the freshness rebuild itself failed, so the bundle could not be compared.\n'
      + `  ${detail}${where ? `  (${where.file}:${where.line})` : ''}\n`
      + '  The source does not currently build. Fix that first; nothing can be said about the bundle\n'
      + '  on disk until it does.');
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
  const onDisk = readFileSync(OUTFILE);
  if (!onDisk.equals(fresh)) {
    let at = 0;
    while (at < Math.min(onDisk.length, fresh.length) && onDisk[at] === fresh[at]) at++;
    fail('the bundle on disk is NOT what the current source and config produce.\n'
      + `  on disk: ${onDisk.length} B   ·   rebuilt from source: ${fresh.length} B   ·   first difference at byte ${at}\n`
      + '  A stale bundle is worse than a missing one: the missing one 404s loudly, this one serves the\n'
      + '  previous build to every visitor while every gate stays green.\n'
      + '  Run `npm run build -w @salon/snippet --prefix web`.\n'
      + '  (If the source is unchanged, the ENDPOINT config differs from the one this bundle was baked\n'
      + '  with — which is the same defect wearing different clothes.)');
  }

  console.log(`snippet check: OK — business="${baked.business.name}", demoMode=${baked.demoMode}, `
    + `path="${parsed.pathname}", bundle=${size} B, freshness=byte-identical to a rebuild`);
  process.exit(0);
}

/* ── 4. bundle ─────────────────────────────────────────────────────────────────────────────────── */
mkdirSync(dirname(OUTFILE), { recursive: true });
let result;
try {
  result = await esbuild.build(buildOptions(OUTFILE));
  reportWarnings(result);   // INSIDE the try: see reportWarnings' own note (F10)
} catch (e) {
  // The real build path had no catch at all, so with esbuild silenced its only failure display would
  // have been a raw Node stack trace — the exact shape the --check catch was added to remove.
  const detail = e?.errors?.[0]?.text ?? (e?.message ? String(e.message).split('\n')[0] : String(e));
  const where = e?.errors?.[0]?.location;
  fail('the bundle did not build.\n'
    + `  ${detail}${where ? `  (${where.file}:${where.line})` : ''}`);
}

const bytes = statSync(OUTFILE).size;
console.log(`snippet: → web/site/public/barber-widget.js  (${(bytes / 1024).toFixed(1)} kB, business="${baked.business.name}", demoMode=${baked.demoMode}, path="${parsed.pathname}")`);
