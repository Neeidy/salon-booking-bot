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

> **Honest scope of `client.config.types.ts` today:** it is generated from the schema and drift-guarded,
> but **nothing compiles it yet** — there is no `tsconfig.json` and `node --test` strips types rather
> than checking them. It is documentation with a guard until the Next.js apps (6a-2 / 6c) actually
> typecheck against it. Runtime safety comes from `loadConfig`'s ajv validation, not from the type.

## Source of truth for what gets built
`docs/SCREEN-INVENTORY.md` (98 screens/states) is the brief; `design/mockups/` holds the 9 delivered
static design surfaces. A screen that is not in the inventory does not exist —
`design/mockups/tokens.css` is **not** used (BULGU-4).
