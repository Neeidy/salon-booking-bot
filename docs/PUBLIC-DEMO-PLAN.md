# Public demo — PLAN

> **Status: APPROVED by Yigitcan (plan-gate), 2026-10-29**, presented in chat in the full format, rulings D1–D6 as
> proposed (below). Derived against `07a10b5`. R1 stopped at its start (the deploy tool could not carry the first D2);
> **Ruling (d), same day, replaced D2 and withdrew D3 with no deploy-tool change** (below), and **R1 was built offline
> under it** ("R1 — built"). The ship gate this phase serves is ROADMAP →
> "Ship gate after D6c" (items 11–16, 19, 21) plus the per-client Turnstile provisioning item moved here from Phase 8.
> Hostnames are written as placeholders on purpose: `<apex>`, `demo.<apex>`, `<n8n host>`, `<dashboard host>`.

## Rulings (Yigitcan, 2026-10-29)
- **D1** — the site on **Vercel Hobby**, public hostname **`demo.<apex>`** (a DNS-only CNAME to Vercel).
- **D2** — *superseded by Ruling (d):* it was ONE Main edit in three parts (a Turnstile hostname check, the Turnstile
  secret into an n8n credential, `Eval Spend` fail-closed). Under (d) the Main edit is `Eval Spend` fail-closed alone.
- **D3** — *withdrawn by Ruling (d):* no new Cloudflare token. The DNS record is Yigitcan's, in the dashboard; #12 is
  shown by behaviour.
- **D4** — demo lead retention **30 days** (`leadsRetentionDays`).
- **D5** — gate #13 closed by the **real 04:00 Purge** deleting a back-dated synthetic `pd-` lead.
- **D6** — **standing approval for an emergency Vercel pause**; Main deactivation stays behind `⚠ ONAY GEREKİYOR`.
- **Honesty additions:** the `/privacy` page and the widget notice say plainly that bookings are written to a REAL demo
  calendar and that owner alerts (Telegram) may carry message text and sit outside Purge. Alert volume after go-live is
  measured in R3 and reported (no change now).
- **Convergence** (as in Phase 8): each review judges its round's diff; the same defect class twice → a recorded bound,
  no extra round.

## Ruling (d) (Yigitcan, 2026-10-29) — none of (a)/(b)/(c); no deploy-tool rule changes
- **#11 split.** Parts 2 and 3 (an Invisible widget, non-interactive tokens) close by **widget settings**: the EXISTING
  widget set to **Managed**, its hostname list = **the demo hostname only** (Yigitcan in the dashboard, guided; R2).
  Part 1 (the engine reading siteverify's `hostname`) and moving the Turnstile secret into a credential (Phase 8's D4)
  are a **recorded bound**, for the next GATE-touching Main edit. **The reason:** with one allowed hostname Cloudflare
  refuses to mint a token anywhere else (client error `110200`, "Domain not authorized"), so the server check is
  defence in depth, not the boundary.
- **The Main edit shrinks to ONE part: `Eval Spend` fail-closed** — measured first that `Eval Spend` is not a GATE node
  (it is not in `diff-workflow-copy.GATE_NODES`, and it is not a trigger) — as an approved delta through the existing tool.
- **Per-client Turnstile provisioning script: NOT built for the demo** (the existing widget is used). It is recorded as
  **required before the SECOND real client**; the "before done" rule stands.
- **No new Cloudflare token (D3 withdrawn):** the DNS record for `demo.<apex>` is added by Yigitcan in the dashboard
  (R2, guided); #12 is shown by behaviour (the block), not by reading the rule.

## 1. Where the site can run — measured 2026-10-29 (read-only), then the recommendation
**Facts:**
- **Vercel:** the owner's Hobby account is active. It holds two projects, neither of them this one, and no domain is
  registered in Vercel. `<apex>` and `www.<apex>` resolve to Vercel's anycast address (the existing portfolio site).
- **Netlify:** unrelated projects only.
- **Cloudflare:** the developer-platform connection holds no Worker. The zone's nameservers are Cloudflare's.
  `demo.<apex>` and `site.<apex>` have no record. `<n8n host>` resolves inside Cloudflare's ranges (proxied).
- **The Cloudflare token** (read-only, with an expiry) reads tunnels and Access applications, and is REFUSED (403) on
  DNS records, rulesets (the rate limit), Turnstile widgets and Pages. The account id is reachable through the zone
  record — a fifth route beside the four ROADMAP #17 records as closed.
- **The tunnel** that serves `<n8n host>` and `<dashboard host>` is remotely managed (ingress edited in the panel or by
  a token with tunnel rights), and ends in a catch-all 404.
- **The site** (repo records): Next.js; no API routes, no middleware; the routes are `/` and `/install`. A public build
  refuses a `demoMode:false` config. The widget POSTs cross-origin to `https://<n8n host>/webhook/barber-inbound` from
  `NEXT_PUBLIC_WEBHOOK_URL`. CORS reflects any origin (measured earlier), so no proxy is needed. The site key comes from
  `NEXT_PUBLIC_TURNSTILE_SITE_KEY` at build time.

**Recommendation (D1):** Vercel Hobby, root `web/site`, hostname `demo.<apex>`. Cost: $0 (Hobby); Turnstile free; LLM
spend bounded by the existing monthly cap. The widget reaches the engine on the path it uses today, cross-origin to
`<n8n host>`'s webhook. **Rejected:** Cloudflare Pages (the token has no Pages access — more panel steps); serving it
from the server behind the tunnel (public traffic onto the box that runs n8n and Postgres, plus a panel edit of the
ingress). **Unverified:** that Hobby's personal/non-commercial terms cover a portfolio demo; whether Hobby can protect
a production deployment (measured at deploy time with `get_project`).

## 2. The gates — what closes each, the proof, and whether it is live
| Gate | Closed by | Proof | Live? |
|---|---|---|---|
| **#11** Turnstile weak | Ruling (d): the EXISTING widget set to **Managed**, its hostname list = `demo.<apex>` only (no apex, no `localhost`) — Yigitcan in the dashboard. Part 1 (the engine's hostname check) and the secret in a credential: a recorded bound | live, by behaviour: a page on a hostname NOT in the list cannot mint a token (`110200`); the demo page can; the dummy token is still 403 | yes (dashboard, **Yigitcan**) |
| **#12** rate-limit BLOCK | to be measured: 25 requests a minute from this server to a NON-existent `/webhook/zz-rl-probe` path (the rule matches "path contains `/webhook/`"; no n8n execution, no LLM) — blocked after the 20th. Shown by behaviour only (D3 withdrawn: the rule is not read) | the blocking response | yes (requests only) |
| **#13** leads TTL live | D5: a back-dated synthetic `pd-` lead seeded into production (the S2 pattern); the real 04:00 Purge deletes it | `salon_ro`: 1 row before, 0 after; the Purge execution | yes (a temporary workflow with a DB credential, ⚠ ONAY) |
| **#14** Privacy Addendum, the open half | a `/privacy` page on the site, linked from the footer and the widget | headless: the page, the links, Cloudflare's privacy link | no (build) |
| **#15** SP4a in Managed mode | the existing harness, headless, against the deployed page | the render-moment record | yes (read) |
| **#16** platform checks | read from Vercel after the deploy: (a) platform, (b) root directory, (c) `web/dashboard` absent from the deployment's file list, (d) the protection state | `get_project`, `list_deployment_files` | yes (read) |
| **#19** owner from the internet | Yigitcan opens `<dashboard host>` on his phone, signs in through Access, presses "release" on a seeded `pd-` conversation | CC reads the store change with `salon_ro` | yes (**Yigitcan**) |
| **#21** Turnstile up, real browser | Yigitcan books and cancels on the live demo | CC reads the executions, the store and the calendar (`cancelled`) | yes (**Yigitcan**) |
| **Turnstile provisioning** | Ruling (d): NOT built for the demo (the existing widget is used) — **required before the SECOND real client**, the "before done" rule standing | — | — |

## 3. Honesty — what a visitor sees and what happens to what they type
- **Today:** the footer "DEMO — mock data", the "Mock" ribbon, `noindex`, the widget's "Demo" tag.
- **Added:** one line above the widget's first message — a demo; do not enter real personal details; messages are
  processed by an AI model and deleted after 30 days — and a `/privacy` page listing the processors (read from the
  workflows when it is built).
- **Said plainly** (honesty additions above): bookings are written to a REAL demo calendar (`dryRun=false`, kept — it is
  the product's proof); leads and conversations go to Postgres; owner alerts (Telegram) may carry the message text and
  are OUTSIDE Purge; WhatsApp sending is off.
- **Retention:** leads 30 days (D4), message text 30 days (unchanged) — one number to tell a visitor.

## 4. Spend and abuse bounds for a public endpoint, and the rollback
- **Bounds:** Turnstile (Managed, hostname-bound after #11) · the Cloudflare edge rule on `/webhook/`, 20 requests a
  minute per IP, Block (shown by #12) · the LLM cap, $10 a UTC month · 12 turns per conversation · `bot.killSwitch`
  (flipping it is a workflow write).
- **The Main edit (Ruling (d)):** `Eval Spend` today runs the turn when the meter cannot be read (fail-open, ruled at
  K-SPEND); for a public endpoint it becomes fail-closed — a deterministic handoff reply and an alert (built in R1,
  staged; live at R2's put).
- **Take the demo offline in one step:** pause the Vercel project (back with unpause). The site and the widget go. The
  engine does NOT stop: its webhook stays up, bounded by the LLM cap, the edge rate limit and the turn cap (Turnstile's
  hostname binding is checked against the origin the browser reports, so it is not a proof that no token can be minted
  — corrected after `code-reviewer`'s R1 review, reasoning, not measured); stopping the engine is the kill-switch or
  deactivating Main (⚠ ONAY). `scripts/demo-offline.sh` measures the pause (built in R1, below). D6: standing approval for
  this pause in an emergency; Main deactivation stays ⚠ ONAY.

## 5. Yigitcan's unavoidable manual steps (minimised, grouped)
*Revised by Ruling (d): no token; the DNS record and the widget settings are his, in the dashboard. The exact steps,
read from Cloudflare's and Vercel's current documentation, are in "R1 — built" → "Yigitcan's dashboard steps".*

**In R2:**
1. **The DNS record** for `demo.<apex>` (one CNAME, DNS only) — after CC has added the domain to the Vercel project and
   read its target.
2. **The widget settings** — the existing widget to Managed, its hostname list = `demo.<apex>` only.
3. If Vercel's GitHub app does not cover this repo (unmeasured), one click to grant it.

**At the end, after go-live:**
4. **#19** — the dashboard from his phone, one button (Access e-mail code).
5. **#21** — one booking and its cancel on the live demo.

Everything else is CC's: the build, the Vercel project and env, the Vercel domain, the Main and Purge edits, the seed,
the measurements.

## 6. Scope, NOT-build, skeleton, CRT, estimate
- **Goal:** the demo site public at `demo.<apex>` with gates 11–16, 19 and 21 closed or declared open with a reason.
- **NOT-build:** no new features; no WhatsApp / Zernio; no Phase 6c work beyond the gates; no CORS narrowing (not a
  security boundary — the Turnstile widget's hostname binding is; under Ruling (d) that binding is the widget's own
  hostname list, the engine-side check a recorded bound); not #17's rotations, #18 or #20; no multi-tenancy.
- **Skeleton (revised by Ruling (d)):** the Main edit (`Eval Spend` only); the Purge literal (`leadsRetentionDays`);
  `web/site/app/privacy/page.tsx` and the widget notice; `scripts/demo-offline.sh`; seed tool `pd-` actions; a RUNBOOK
  "public demo" section. (`scripts/provision-turnstile.py` is not built — Ruling (d).)
- **Integrations:** Vercel · Cloudflare (Turnstile widget settings and the DNS record, both in the dashboard) · n8n
  (Main, Purge) · Postgres (seed, reads) · Google Calendar (#21) · Telegram (alerts).
- **Mock data:** the demo salon is config-driven mock data; drill rows carry the `pd-` prefix and are cleaned to 0 by
  guarded SQL.
- **CRT derivation (revised by Ruling (d)):** **#15 "public-demo spend brake and retention"** — `Eval Spend`
  fail-closed and the Purge's lead retention (money handling and an irreversible delete: criteria 3 and 5). One Codex
  run on the staged Main + Purge diff. The widget and DNS settings are configuration: checks by behaviour, not a CRT.
- **Acceptance:** #11–16, #19, #21 closed or ruled open with a reason; the demo's widget in Managed mode listing only
  the demo hostname, no `localhost`; "take it offline" shown (pause → the site unreachable, measured → unpause); tests
  and mutants green; guards 0; CRT #15 closed.
- **⚙ Drill matrix:**

| # | Scenario | Setup | Expected | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|---|
| 1 | real token | Yigitcan, live demo | book + cancel, one event | the LLM, the calendar write | a second event |
| 2 | wrong hostname | a page on a hostname not in the widget's list (Ruling (d): by behaviour) | no token minted (`110200`) | — | a request to the engine |
| 3 | dummy token | live | 403 | the Turnstile branch | the LLM |
| 4 | rate limit | 25 requests a minute, a non-existent path | blocked after 20 | the edge rule | an n8n execution |
| 5 | over cap / meter unreadable | unit | handoff + alert | the deterministic reply | the LLM |
| 6 | offline | pause | the site unreachable; unpause restores it | — | — |
| 7 | Purge | the 04:00 run, a `pd-` lead | 1 → 0 | the real Purge | any other row deleted |
| 8 | owner access | Yigitcan, phone | the store changes | the Access sign-in | — |
| 9 | the dashboard in the deployment | the file list | `web/dashboard` absent | — | — |
| 10 | jailbreak | the existing cases, live | a safe handoff | — | a write |

- **Automation-fit:** neither — one scheduled check after the 04:00 Purge run.
- **Estimate (as approved):** 3 rounds, 4 if Codex brings findings — R1 offline; R2 live (token → widget → credential
  → the Main write → a protected Vercel deploy → #12, #15, #16 → the seed); R3 (the night's Purge → DNS and go-live,
  approved on its own → #19, #21 → close). **Revised by the stop below.**

## R1 — stopped at its start (2026-10-29): the deploy tool cannot carry D2 as it stands
*History. Resolved by Ruling (d) above: none of the options below was taken, and the deploy tool is unchanged.*
The brief: R1 stages the D2 Main edit "as an approved delta for the proven deploy tool"
(`scripts/workflow-step.py put`, checked by `scripts/diff-workflow-copy.py`). Measured before any build:
1. **The GATE (ruling R1c, 2026-10-26).** `Load Config`, `Verify Turnstile` and `Turnstile Valid?` are GATE nodes:
   never in `--allow`, and no delta may edit them. D2's hostname check and secret move live in exactly these three.
2. **`credentials` may not change on an edited node** (`ALLOWED_ON_EDITED_NODE = parameters, alwaysOutputData`).
   Moving the secret into a credential changes `Verify Turnstile`'s `credentials` key.
3. **A new placeholder has no live value to fill from.** `fill_by_path` refuses a placeholder with no live counterpart
   ("an operator step"). The demo hostname contains `<apex>`, a redaction target, so the committed export and the
   example config must carry a placeholder; at the FIRST deploy neither the hostname nor the new credential's id exists
   live.
4. **The Turnstile literal pattern.** `TS_LITERAL` matches exactly `turnstile: { enabled: … }`; a `hostname` key in the
   same object (`channels.widget.turnstile.hostname`) stops it matching — and it is the pattern the Turnstile window
   uses to lower and restore the gate (`scripts/turnstile-window.py` via `deploy-workflow-copy.py`), plus put's
   shape check and Phase 8's render test.
5. **A new placeholder class** for the hostname in the parity guards and the sanitiser (its name must not contain
   `TURNSTILE`, which the "turnstile secret" class already claims).

**Also measured, needed by R1 under any option:**
- `Verify Turnstile` sends a **form-urlencoded** body. In the n8n node package matching the live instance (read from the
  published package, offline), a form body is moved aside BEFORE a Custom Auth credential's `body` is merged, so the
  credential's secret would not join it. A **JSON** body merges. Cloudflare documents that siteverify accepts
  `application/json`. So the secret move also switches `Verify Turnstile` to a JSON body — inside D2's second part.
- **`Eval Spend` fail-closed depends on an unmeasured engine behaviour.** `Read Spend` carries `alwaysOutputData` and
  `continueErrorOutput`; on a read error its alert branch fires, and whether output 0 ALSO fires (so `Eval Spend` runs
  and can see the error branch) is measured only for the case WITHOUT `alwaysOutputData` (PHASE-7-PLAN, 2026-10-25:
  0 items on output 0). R1 can build it offline; the live behaviour must be measured on a scratch in R2 before the put.

**Options, for a ruling:**
- **(a) — recommended: extend the tool narrowly, each change a ruled entry reviewed as code and inside CRT #15.**
  A ruled gate edit by identity (the three nodes, for this one approved Main delta only; `credentials` allowed to
  change on `Verify Turnstile` only, to exactly one Custom Auth credential). A `--first-fill FILE` on put (0600, outside
  the repo) only for the two named new placeholders and only where live has no value at that path, values never
  printed — after the first deploy, fill-from-live covers them as it covers the chat id. `TS_LITERAL` widened to
  `turnstile: { enabled: true|false, hostname: "…" }` with `enabled` still first, and the window tool's selftests
  extended. The new placeholder class in the parity guards and the sanitiser. Cost: about one more round; the tool
  changes join CRT #15's audit.
- **(b)** The hostname as a parameter placeholder on `Turnstile Valid?` instead of a config key — avoids the
  `TS_LITERAL` change but still needs (a)'s gate exception and first-fill, and moves a per-client value out of the
  config (against Phase 8's principle). Not recommended.
- **(c)** Apply the Main edit by a one-off API call outside the tool — loses the snapshot, rollback and parity
  guarantees the tool exists for. Not recommended.

## R1 — built (offline), 2026-10-29, under Ruling (d)
Nothing live was written in R1. Each part with its proof:

**1. `Eval Spend` fail-closed** — `n8n/staged/workflow.main.sanitized.json` + `workflow.main.delta.json` (`allow:
["Eval Spend", "Build Spend-Meter Alert", "Spend-cap note"]`, no node, edge or setting). **Declared:** the second and
third are TEXT-ONLY — the alert's comment lines and the sticky, which said "fail-OPEN" and would be false after the put
(`code-reviewer` MEDIUM-4); the test proves the alert's code is otherwise unchanged and a mutant that changes it dies.
None of the three is a GATE node. `diff-workflow-copy.py` on the pair: green; `staged-sanitised`: green.
- **Why the old code is open on BOTH failures** — read offline from the n8n engine and workflow packages matching the
  live instance: under `continueErrorOutput` a query error is split onto output 1 first, and `alwaysOutputData` then
  puts one empty item on output 0 (it looks at output 0 only), so `Eval Spend` runs on `{}` and counts it as zero
  spend; a THROWN error passes `Read Spend`'s input through on output 0 with no output 1 at all; a zero-row SELECT on
  this Postgres node version returns no item, so "no row this month" is the same `{}`. The same engine behaviour was
  already on the record: ARCH-DEC 2026-08-25 ("emits on BOTH outputs on error"), MIGRATION-PLAN M5 ("fail-open +
  alert", live), §3r D3d R1 finding 2 (on Purge's reads, live).
- **The new rule:** the LLM runs only on a row with a finite, non-negative `cost_usd` (a number, or numeric text), or on
  the empty item WITH an empty output 1 (`$('Read Spend').all(1)`; if that throws — no output 1 — it is closed).
  Everything else → Spend Gate's over-cap branch: the deterministic handoff reply and the owner alert, no LLM.
  `_spend` gains `meter: row | no_row | unreadable`.
- **Proof:** `tests/unit/eval-spend-fail-closed.test.cjs` (in check-all) — Eval Spend's code and Spend Gate's IF from
  the export, against every output shape above; its negative control runs the pre-fix export (from git) and must come
  out OPEN on the query-error and thrown cases (9 tests). `tests/unit/eval-spend-mutants.py`: 10/10 killed (one survived
  the first version — a thrown error with an empty pass-through item — and a case was added for it).
- **Recorded bounds:** (i) **the owner alert of a closed turn is the spend-cap one, in all three closed cases**
  (`code-reviewer` MEDIUM-3): every closed turn goes through `Build Spend-Cap Reply`, so the owner reads "budget
  reached" — alone on a THROWN read error and on an untrusted row (no output 1 fires, so `Build Spend-Meter Alert` does
  not run), and BESIDE the meter alert on a caught query error. The execution carries `_spend.meter = 'unreadable'`, but
  no node reads it. This falls short of `handoff.md`'s "an infrastructure failure is distinguishable" for those cases;
  carrying `spend_meter_unavailable` would be a behaviour change in a second node, outside Ruling (d)'s one-part edit —
  **a decision for Yigitcan** (widen the Main delta to `Build Spend-Cap Reply` in R2, or keep it for the next Main edit).
  (ii) A config with no
  usable cap never blocks — unchanged, and not part of the meter. (iii) The engine behaviour is a model here; it is
  measured live on a scratch in R2 before the put (below).

**2. Demo lead retention 30 days** — `n8n/staged/workflow.purge.sanitized.json` + `workflow.purge.delta.json` (`allow:
["Load Config (Purge)"]`), produced by `scripts/render-client.py` from a scratch copy of the example config with
`leadsRetentionDays: 30` (only that node differs; diff tool green). The render rewrites the literal as JSON and drops
the comment that sat inside it (its reason stays on `Compute Leads Cutoff` and the branch's sticky note).
**The example config stays at 90 until the promotion**, because `render-client.test.py` case 1 holds render(example) =
the committed export; the promotion commit changes both together, and that test is what forces it.

**3. `/privacy`, the widget notice, the footer link** — `web/site/app/privacy/page.tsx` (demo builds only; local
styles: `globals.css` is a locked contract), `web/site/lib/privacy.ts` + `retention.ts` (the client panel must not reach
`lib/config` — `check-client-imports` caught the first version), the notice above the chat's first message, the footer
link. Every statement is held to the engine by `tests/unit/privacy-facts.test.cjs` (in check-all; 9 tests) and
`tests/unit/privacy-facts-mutants.py` (9/9, on a copied tree): the 30-day text and id retention = Purge's two cutoffs;
leads = the config key Purge reads, AND the Purge's safety limit stated as the code applies it (more than a fifth of
the table, or more than 200, at once → nothing deleted that night; fewer than five rows → never) — the first version
promised "deleted after N days" unconditionally (`code-reviewer` HIGH-1); copies outside the database are named — the
backups (`db/ops/pg-backup.sh`'s default, 14 days), the engine's run records (kept for a server-set period, not
measured yet), the services' own policies — and the notice no longer says "erased after 30 days" without them
(`security-auditor` MEDIUM-1, `code-reviewer` MEDIUM-2); no Purge
statement touches appointments; a cancel deletes the calendar event and keeps the row `cancelled`; every outside host
a workflow calls is a listed service; nothing reaches WhatsApp (`Should Send?` is fed only by the WhatsApp ACK, and
Reminders' `whatsappSendDisabled: true`). Built (`next build`) and rendered headless on 127.0.0.1 — the page, the notice,
two `/privacy` links — and again after the review round's text changes; that evidence is in the session scratchpad,
not committed (UNVERIFIED in the repo). Until the promotion the page says leads are kept 90 days — true for what is live.
**Open (Yigitcan):** the page names no contact for a privacy request; what contact, if any, to publish is his call.

**4. `scripts/demo-offline.sh`** — `measure` (no token) · `pause` / `unpause` (Vercel's documented
`POST /v1/projects/{id}/pause|unpause`, then the page MEASURED: 503 / 200). The token is read from a 0600 env file and
sent through a 0600 header file, never on a command line, in output, or in a child process's environment (even when
the env file or the caller exports it). No answer at all (000) is "NOT measured", never "offline", and a pause counts
only on a measured 503 (`code-reviewer` MEDIUM-5). `tests/unit/demo-offline.test.py` (in check-all; 22 checks, shims
recording every curl argument list and every child environment) and `demo-offline-mutants.py` 12/12. **Bound:** the shell
route needs a Vercel token that does not exist; in R2 CC pauses through its Vercel connection (`pause_project`) and
measures with `demo-offline.sh measure` — whether a token for the shell route is wanted is Yigitcan's call.

**5. Seed tool `pd-` actions** — `pd-lead-insert` (synthetic: no name, no phone), `pd-conv-insert` (one conversation at
`handoff` for #19), `clean-pd`; their own prefix (`widget:w-pd-`, `pd-`), so `clean` and `clean-pd` cannot reach each
other's rows (shown both ways on fixture rows); a pd lead's "no name, no phone" is enforced in the SQL too
(`security-auditor` LOW-1). `seed-workflow.test.py` 162 checks; `seed-pd-mutants.py` 10/10 (one mutant equivalent and
recorded). **Bound:** a visitor who CHOOSES that prefix for a session or a lead makes that row
removable by `clean-pd`.

### R2 — measured before any write
1. **`Read Spend`'s error behaviour, on a scratch** (a temporary webhook path behind Access; a workflow with a DB
   credential — ⚠ ONAY): a row, no row, and a forced query error (a missing table) — output 0, output 1, and what
   `$('…').all(1)` returns in each. A thrown error cannot be provoked safely: it stays a model result, stated.
2. **The leads table, read with `salon_ro`:** total rows, rows older than 30 days, `pd-` rows. The Purge's cap is
   `min(200, floor(20% of the table))`, so one aged `pd-` lead needs at least 5 rows in the table (fresh `pd-` leads
   make up the difference); any NON-`pd-` row older than 30 days will be deleted by the first 30-day run — that is
   D4's policy, but it is a real delete, so it is reported before the put; and if the aged rows are more than a fifth of
   the table, that run deletes nothing and alerts (the cap).
4. **Retention outside the database, for the /privacy page:** how long the instance keeps execution data (the engine's
   run records) and the backup retention in force (`PG_BACKUP_KEEP_DAYS` or the script's default 14) — the page is
   corrected to the measured values before go-live.
3. **The existing widget:** which widget the demo's site key belongs to and its current hostnames — CC cannot read
   widgets (the token is refused), so Yigitcan reads them in the dashboard first.

### Yigitcan's dashboard steps (R2) — from Cloudflare's and Vercel's current documentation, read 2026-10-29
**Order:** CC adds `demo.<apex>` to the Vercel project and reads its DNS target → **A** → CC verifies the domain and
its certificate → **B** → CC measures #11 by behaviour.

**A — the DNS record** (Cloudflare: "Create DNS records"):
1. Cloudflare dashboard → the `<apex>` zone → **DNS** → **Records** → **Add record**.
2. **Type:** `CNAME` · **Name:** `demo` · **Target:** the project-specific value Vercel shows for `demo.<apex>`
   (Vercel: "the recommended project-specific target"). CC reads it from Vercel after adding the domain and hands it
   to you; it is not guessed.
3. **Proxy status:** **DNS only** (grey cloud) — ruling D1. **TTL:** Auto. **Save**.

**B — the widget** (Cloudflare: "Turnstile widget", "Hostname management"):
1. Cloudflare dashboard → **Turnstile** → select the existing widget the demo uses → **Settings**.
2. **Widget Mode:** **Managed** (Cloudflare: "automatically chooses between non-interactive or checkbox challenge based
   on visitor risk level").
3. **Hostname Management:** keep ONLY `demo.<apex>` — remove every other entry, `localhost` and `127.0.0.1` included;
   if it is not listed, **Add Hostnames** → `demo.<apex>` → **Add**. **Never the apex:** Cloudflare says "adding a
   hostname automatically authorizes all of its subdomains", so the apex would authorise every subdomain of the zone.
4. **Save** ("Select Save to apply your changes").
- **Effect:** a token requested on any other hostname fails with `110200` ("Domain not authorized"). **Consequence:**
  local drills that need a real token from `localhost` stop working with this widget (a separate development widget,
  if one is ever needed).
- **Not in the documentation, stated:** Cloudflare's pages document **Add Hostnames** but not the remove control or the
  mode field on an EXISTING widget's settings page, and they do not say how fast a change applies. CC checks by
  behaviour after the save, not by the panel.

### Estimate (revised by Ruling (d))
R2 live: the three measurements → the Main put → the Purge put → the promotion commit → the Vercel project, env and
domain → **A** → **B** → #11, #12, #15, #16 → the seed → the pause drill. R3: the night's Purge (#13) → #19, #21 → the
close. One more round if Codex (CRT #15) brings a HIGH.
