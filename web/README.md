# web — frontend

> **Role of this folder:** the vitrin frontend, built in **Phase 6**.
> **Two apps, not one** — see the deploy topology below. This corrects the earlier "one app, three
> surfaces, dashboard at `/admin`" plan, which `docs/UX-ARCHITECTURE.md` §6 superseded.

## Deploy topology (decided — UX-ARCHITECTURE §6, Phase 6 decision D-1)

| App | Surfaces | Runs on | Why |
|---|---|---|---|
| `site/` | public barber demo site (L1-L9) · chat widget (W1-W65) · embeddable snippet (S1-S4) · install page | **Vercel** | vitrin + CDN for the snippet; must be public |
| `dashboard/` | owner dashboard (D1-D20) — appointments · leads · handoff queue · system health | **our own server, behind Cloudflare Access** | solves Critical-Review Target #9 (dashboard auth) with no auth code of our own, and customer PII never reaches a third party |
| `shared/` | config loading + validation, display formatting, PII masking, design tokens | — (imported by both) | one truth for the things both surfaces must agree on |

**Why two apps and not one app with an env flag:** the strongest proof that the Airtable PAT and the
PII read path never ship to Vercel is that **the code is not there**. A single app gated by a flag
would be security-by-flag, which is not security.

### Binding constraints
- **Nothing Vercel-specific.** No edge-middleware-dependent architecture, no Vercel KV/Postgres/Blob,
  no Vercel Cron, no Vercel-only image pipeline. Switching either direction must be a redeploy, not a
  rewrite (UX-ARCHITECTURE §6, portability constraint).
- **The browser never talks to Airtable or to the n8n `/api`.** All access goes through our own API
  layer; the Airtable PAT never reaches a browser, and for the dashboard it is **read-only** — the one
  write action (D11, release the handoff lock) goes through n8n's protected path, not Airtable directly
  (UX-ARCHITECTURE §5).
- **Airtable budget (binding acceptance criterion):** 5 requests/sec/base, shared with the bot →
  **one bulk read per page load, no per-row requests, no auto-refresh, bot gets priority**
  (UX-ARCHITECTURE §7).

## Config-driven

Every surface reads `config/client.config.json` (gitignored) and falls back to the committed mock
`config/client.config.example.json`. The loader **validates against the committed schema** and throws —
a contract-violating config breaks the build instead of painting a half-branded page.

```ts
import { loadConfig, isDemoMode } from '@salon/shared/config';
const config = loadConfig();              // throws ConfigContractError if it fails the contract
// or, when it matters WHICH file was read (a missing client config must never look like success):
// const { config, configPath, usedFallback } = loadConfigDetailed();
if (isDemoMode(config)) { /* mock ribbon stays visible — honesty-demos.md */ }
```

`demoMode` is **frontend-only** (no n8n node reads it, same class as `branding.*`) and optional —
absent means `false`, i.e. a real client install shows no mock ribbon.

## Browser-visible build inputs (slice 2 — the live widget)

`web/site` needs two values at build time. They live in `web/site/.env.local` (gitignored) or in the
deploy platform's environment — **never in a committed file**. Names only, for reference:

| Variable | What | Secret? |
|---|---|---|
| `NEXT_PUBLIC_WEBHOOK_URL` | full URL of the widget inbound webhook (`https://<n8n-host>/webhook/barber-inbound`) | no — the endpoint is public by design |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Cloudflare Turnstile **site** key | no — site keys are public |

The Turnstile **secret** key is not here and never reaches the frontend: it lives in n8n, which is what
verifies the token.

> **The distinction that matters.** `NEXT_PUBLIC_*` values are inlined into the browser bundle, so the
> DEPLOYED OUTPUT carries the webhook URL. That is expected — the browser has to know where to post.
> But `scripts/check-no-host-leak.sh` protects the **repository**, not the build output: it stays green
> because these values exist only in env, and the build output (`.next/`) is gitignored. Read the guard
> as "the host is not in git", not as "the host is nowhere".

## Commands
```bash
cd scripts && npm ci     # the type generator + its pinned prettier live HERE, not in web/
cd ../web  && npm ci     # ajv for the loader

npm test -w @salon/shared                            # config contract tests (must reject bad configs)
node ../scripts/generate-config-types.cjs --check    # types-vs-schema drift guard
```

Both installs are required: `scripts/` owns the generator, `web/` owns the loader. Use `npm ci`, not
`npm install` — the generated file is formatted by a transitive prettier, so an unpinned install can
report a fake drift.

### Fresh-clone order: BUILD, then CHECK (not the other way round)

`config.generated.json` and `public/barber-widget.js` are **gitignored build artefacts**, and the first
command is not optional — `check-all` resolves `ajv` only from `scripts/node_modules` (there is no
`node_modules` at the repo root), so skipping it fails with `MODULE_NOT_FOUND`. A tree that has never been
built fails the verification gate *by design* — that is the CRT #13 lesson, where a
deployment shipped a site whose one-line embed 404'd because only `next build` had run.

```bash
npm --prefix scripts ci                          # 1. ajv + the generator live HERE
npm --prefix web ci                              # 2. ci, not install — see the note above
export NEXT_PUBLIC_WEBHOOK_URL=…                 # 3. or put them in web/site/.env.local
export NEXT_PUBLIC_TURNSTILE_SITE_KEY=…          #    (gitignored, so a clone has neither)
npm --prefix web run build -w @salon/snippet     # 4. produces config.generated.json + the bundle
npm --prefix scripts run check-all               # 5. never WRITES the build artefacts
```

⚠ **This sequence was RUN in a real `git clone`, and the first two drafts of it did not work.** That is
the point of writing it down, and the reason to distrust any build order nobody has executed:

| Draft | What a fresh clone actually did |
|---|---|
| steps 4-5 only | step 5 died with `MODULE_NOT_FOUND` — `check-all` resolves `ajv` only from `scripts/node_modules`, and there is no `node_modules` at the repo root |
| + steps 1-2 | step 4 died with `✗ SNIPPET BUILD STOPPED — no NEXT_PUBLIC_WEBHOOK_URL`; those values live in gitignored `web/site/.env.local`, which a clone does not have |
| + step 3 | build OK, and `build.mjs --check` confirmed the bundle byte-identical to a rebuild **in the clone** |

**Step 5 still exits `2` in a fresh clone, and that is CORRECT, not a failure of the build:**
`check-no-host-leak.sh` prints `NOT CONFIGURED` because it reads the production host from `CLAUDE.local.md`
or `$N8N_HOST`, and `CLAUDE.local.md` is gitignored by design. **Exit 2 means "this guard did not run",
never "this guard passed"** — read it as a missing configuration, not as a clean scan.
(Same distinction already recorded for the parity scripts: an exit 2 is an unset environment, not a verdict.)

**Why the two are deliberately NOT chained into one script.** `build.mjs --check` no longer merely asks
"does a plausible bundle exist" — it rebuilds into a temp directory with the same options and
**byte-compares**. A gate that rebuilds immediately before comparing can never fail, so chaining would
convert a real freshness check into a test that cannot go red. The order is written here instead.

*(Precise wording, because two obvious phrasings are false. `check-all` does **run a build** — that temp
rebuild is one — so "it never builds" is wrong. And the artefacts are **gitignored, not tracked**; staying
untracked is the point, so "tracked build artefacts" inverts it. What it never does is **write the build
artefacts**, which is why it cannot manufacture the outputs it is checking for.)*

### The build-time server/client boundary

```bash
npm --prefix scripts run check-client-imports            # gate the tree
npm --prefix scripts run check-client-imports:selftest   # prove it can still go red
```

`@salon/shared` exports three subpaths, **two of which have opposite rules**, so the gate is written against the SUBPATH and
never the package name: `./config` is server/build-time only and may not be reachable from browser code;
`./chat` is browser-safe by design and is imported by both `site` and `snippet`. A package-name rule would
fail in both directions — blocking every legitimate widget build, or, relaxed to compensate, missing a real
`./config` leak. Rules are enforced by resolved FILE PATH, so a hand-written relative route to the same
module is the same offence.

It walks the import graph **transitively** from every `'use client'` file plus the snippet entry (browser
code with no directive — it had zero coverage until that was measured), reports the full chain, and FAILS
rather than skipping whenever it cannot follow something: a computed specifier, an unresolvable relative
import, an unreadable file, an unparseable file, or a `web/*` app nobody added to the scan list. A
`tsconfig` path alias fails it only for a tsconfig under the scanned apps — **two known holes (a symlink
around a banned file, and an alias declared in a walked-but-unscanned package) are open and recorded in
`docs/ROADMAP.md`, not fixed.**

**It uses the TypeScript parser, not pattern matching — and that was the expensive lesson.** Three earlier
versions hand-rolled a scanner; three audit rounds each found a fresh batch of holes of ONE class — a regex
literal eating the file, a division misread as a regex, a missing semicolon merging statements, a BOM, a
default import bound to the name `type`, JSX prose firing on correct code. Those were LEXING problems and
the parser removes the class entirely. ⚠ *Corrected 2026-09-12: this sentence first said "every one" of the
audit findings was a lexing problem, and that is false. The same rounds also found resolution and coverage
defects — a bare Node builtin filed as third-party, a workspace package behind a symlink, a payload JSON
that was never banned, an unscanned app, a computed specifier, a JSONC trailing comma disabling a detector.
That code is still hand-written and can still break. The parser closed one class, not all of them.* `scripts/` therefore pins `typescript@5.9.3` **as a parser only** — `web/` pins `7.0.2`, the Go
port, whose npm package does not expose the classic compiler API and whose AST sits behind an `unstable/`
export. Two versions, two jobs.

> **Honest scope of `client.config.types.ts` today** — *corrected 2026-09-11; the previous wording
> ("nothing compiles it yet — there is no `tsconfig.json`") described the tree before 6a-2 and had been
> false ever since.* `web/site` has a `tsconfig.json` and its `check` script is `tsc --noEmit`, so the
> generated type IS compiled and IS enforced. **Measured, both directions:** a clean tree exits 0; a
> wrong type on a known key (`const x: number = config.business.name`) exits 1 with `TS2322`.
> **The real remaining limit, which the old sentence hid rather than stated:** the generated type has a
> root index signature (`[k: string]: …`), so reading a key that is NOT in the schema does **not** fail
> the typecheck — it resolves to the union of the declared value types. ⚠ *Cause corrected 2026-09-12:
> this first said the signature comes from `additionalProperties`. Measured: the schema root is
> `additionalProperties: false`; the signature comes from `patternProperties: ["^\\$comment"]`, and the
> generated file says so in its own comment. The conclusion was right and the reason was invented —
> inside a paragraph already labelled as a correction.* And `site/lib/config.ts` casts through `unknown`, so the JSON's real shape is never checked
> against the type. Runtime safety therefore still comes from ajv validating the config against the
> committed schema at build time, not from the type.

## Source of truth for what gets built
`docs/SCREEN-INVENTORY.md` (98 screens/states) is the brief; `design/mockups/` holds the 9 delivered
static design surfaces. A screen that is not in the inventory does not exist —
`design/mockups/tokens.css` is **not** used (BULGU-4).
