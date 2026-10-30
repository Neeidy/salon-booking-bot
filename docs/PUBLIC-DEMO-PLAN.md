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
| **#12** rate-limit BLOCK | **GREEN (R2c):** 40 requests in 2.4 s from this server to a NON-existent `/webhook/zz-rl-probe` path → requests 1–30 n8n's 404, 31–40 Cloudflare's `429` (`error code: 1015`, `Retry-After: 10`); no n8n execution, no LLM. The rule as read by Cowork (R2c): path contains `/webhook/`, 30 requests per 10 s per IP and Cloudflare data centre, Block for 10 s. *(This cell said "25 requests a minute … blocked after the 20th" — the plan's assumed rule, never read; it was wrong, and R2b's probe built on it stayed under the real threshold.)* | the blocking response | yes (requests only) |
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
  processed by an AI model; a nightly job erases their text from the demo's database after 30 days, while backups, the
  engine's run records and owner alerts can keep copies longer — and a `/privacy` page listing the processors (read
  from the workflows). *(Corrected in R1: the plan said "deleted after 30 days" unscoped, which the L2 reviews showed
  was not true of the copies outside the database.)*
- **Said plainly** (honesty additions above): bookings are written to a REAL demo calendar (`dryRun=false`, kept — it is
  the product's proof); leads and conversations go to Postgres; owner alerts (Telegram) may carry the message text and
  are OUTSIDE Purge; WhatsApp sending is off.
- **Retention:** leads 30 days (D4), message text 30 days (unchanged) — one number to tell a visitor.

## 4. Spend and abuse bounds for a public endpoint, and the rollback
- **Bounds:** Turnstile (Managed, hostname-bound after #11) · the Cloudflare edge rule on `/webhook/`, 30 requests per 10 s per IP and Cloudflare data centre, Block for 10 s
  (read R2c; blocking shown by #12 in R2c — R2b's "RED" was a probe under the threshold) — it limits the request VOLUME
  reaching the origin, not spend: it still admits about 3 requests a second per IP and data centre, and a distributed
  source multiplies that; spend is bounded by the controls that follow · the LLM cap, $10 a UTC month · 12 turns per conversation · `bot.killSwitch`
  (flipping it is a workflow write).
- **The Main edit (Ruling (d)):** `Eval Spend` today runs the turn when the meter cannot be read (fail-open, ruled at
  K-SPEND); for a public endpoint it becomes fail-closed — a deterministic handoff reply and an alert (built in R1,
  staged; live at R2's put).
- **Take the demo offline in one step:** pause the Vercel project (back with unpause). The site and the widget go. The
  engine does NOT stop: its webhook stays up, bounded by the LLM cap, the edge rate limit (#12, shown in R2c) and the turn cap (Turnstile's
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
| 4 | rate limit | 40 requests within ~3 s, a non-existent path | blocked from the 31st (R2c: shown) | the edge rule | an n8n execution |
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
**Open (Yigitcan):** what contact to publish for a privacy request is his call — since R2a the page shows a visible
PLACEHOLDER until he answers, and it is go-live check 1 below. *(R2h: the contact, and the controller beside it, now come
from build-time env — rulings R2h-1/2; see go-live check 1.)*

**4. `scripts/demo-offline.sh`** — `measure` (no token) · `pause` / `unpause` (Vercel's documented
`POST /v1/projects/{id}/pause|unpause`, then the page MEASURED: 503 / 200). The token is read from a 0600 env file and
sent through a 0600 header file, never on a command line, in output, or in a child process's environment (even when
the env file or the caller exports it). No answer at all (000) is "NOT measured", never "offline", and a pause counts
only on a measured 503 (`code-reviewer` MEDIUM-5) — *R1's record; since R2a only Vercel's paused answer (503 with
`DEPLOYMENT_PAUSED` in the body) counts, and the counts below are R1's (R2a: mutants 15/15).* `tests/unit/demo-offline.test.py` (in check-all; 24 checks, shims
recording every curl argument list and every child environment) and `demo-offline-mutants.py` 13/13 (the API address
must be https, or http to 127.0.0.1, with no user part — a fix-round finding, measured by `code-reviewer`). **Bound:** the shell
route needs a Vercel token that does not exist; in R2 CC pauses through its Vercel connection (`pause_project`) and
measures with `demo-offline.sh measure` — whether a token for the shell route is wanted is Yigitcan's call.

**5. Seed tool `pd-` actions** — `pd-lead-insert` (synthetic: no name, no phone), `pd-conv-insert` (one conversation at
`handoff` for #19), `clean-pd`; their own prefix (`widget:w-pd-`, `pd-`), so `clean` and `clean-pd` cannot reach each
other's rows (shown both ways on fixture rows); a pd lead's "no name, no phone" is enforced in the SQL too
(`security-auditor` LOW-1). `seed-workflow.test.py` 162 checks; `seed-pd-mutants.py` 10/10 (one mutant equivalent and
recorded). **Bound:** a visitor who CHOOSES that prefix for a session or a lead makes that row
removable by `clean-pd`.

### Convergence — what the fix-round review found again, recorded rather than reopened
The second `code-reviewer` pass (on `ceeeafc`/`05a1bfd`) confirmed every fix and found three residues of classes it had
already reported once. Under the convergence rule they are **recorded bounds, not another round** — each is corrected
**before go-live in R2**, because none is public until then:
- **(HIGH-1's class) the leads safety limit is not a one-night pause.** The page says the job deletes "nothing that
  night"; the cap is recomputed every night and, with few new leads, the aged share only grows, so the refusal can
  persist until the owner acts. The sentence must say that.
- **(MEDIUM-5's class) `measure` reads every non-200 answer except 000 as "offline".** A 401 (deployment protection),
  404 (a wrong domain binding) or a redirect would read as "offline" too; the pause itself already counts only a 503.
  `measure` must count only 503 (with Vercel's paused marker) as offline and report other codes as unexpected.
- **(MEDIUM-4's class) `Build Spend-Cap Reply`'s first comment** still says "the monthly LLM budget is reached"; after the
  put it also runs on an unreadable meter. It goes with Yigitcan's decision on bound (i) above (widen the Main delta to
  that node, or the next Main edit).
Fixed in the same pass because they were NEW classes: the API-address check could be passed with a user part
(`http://127.0.0.1:1@…`, measured) — now refused, with a test case and a mutant; the backup sentence said "14 days" where
`find -mtime +14` keeps a dump about 15 (and keeps it while the nightly backup fails) — now "more than 14 full days …
typically about 15"; the site's lead-retention rule now equals the Purge's (an integer ≥ 1); a test anchor that matched
any word ("run") was lengthened.

### CRT #15 — the Codex run (one run, pin `4210208`; `docs/codex/public-demo/crt15.md`, containment beside it)
**No HIGH; two MEDIUM, both test coverage; no runtime defect found in the staged edits** under the documented engine
model (Codex had no engine source; the model is measured live in R2, as planned). Both fixed in-round, each with a test
case and a mutant it kills; not re-run through Codex (no HIGH):
- **F1 — a cost rounded to cents passed the spend suite** (it would block a legitimate 9.999999 under a cap of 10 and
  drop spend before `Build Spend Record`). A full-precision test case and the rounding mutant: `eval-spend` 10 tests,
  mutants 11/11.
- **F2 — the Purge suite stayed green with the deletion verifier disabled** (its fake store always removed what it
  acknowledged). A store that acknowledges and removes nothing must now produce `leads_purge_arithmetic_mismatch`
  (`leads-purge-read-error` 12 tests); `tests/unit/leads-purge-mutants.py`: 3 mutants × the committed and the staged
  export = 6/6. Shown: the verifier-off mutant SURVIVES the previous version of the test and dies on the new one.
  **Recorded gap (F2's other direction, `code-reviewer`):** the verifier also guards a delete that removes MORE than
  asked, and no test drives that direction — a verifier blind to it (`before - after < deleted`) survives. The delete
  removes one row by primary key, so it needs a concurrent deleter; recorded, not built.

### R2 — measured before any write
1. **`Read Spend`'s error behaviour, on a scratch** (a temporary webhook path behind Access; a workflow with a DB
   credential — ⚠ ONAY): a row, no row, and a forced query error (a missing table) — output 0, output 1, and what
   `$('…').all(1)` returns in each. A thrown error cannot be provoked safely: it stays a model result, stated.
2. **The leads table, read with `salon_ro`:** total rows, rows older than 30 days, `pd-` rows. The Purge's cap is
   `min(200, floor(20% of the table))`, so one aged `pd-` lead needs at least 5 rows in the table (fresh `pd-` leads
   make up the difference); any NON-`pd-` row older than 30 days will be deleted by the first 30-day run — that is
   D4's policy, but it is a real delete, so it is reported before the put; and if the aged rows are more than a fifth of
   the table, that run deletes nothing and alerts (the cap).
3. **The existing widget:** which widget the demo's site key belongs to and its current hostnames — CC cannot read
   widgets (the token is refused), so Yigitcan reads them in the dashboard first.
4. **Retention outside the database, for the /privacy page:** how long the instance keeps execution data (the engine's
   run records) and the backup retention in force (`PG_BACKUP_KEEP_DAYS` or the script's default 14) — the page is
   corrected to the measured values before go-live.

### R2a — measured, then fixed (2026-10-30; rulings of 2026-10-29 in the R2a brief)
**Measurements (before any write):**
1. **`Read Spend`, live, on a scratch** (an Access-covered temporary webhook → a Postgres node built like `Read Spend` —
   same type, version, query, `alwaysOutputData`, `continueErrorOutput`, the one postgres credential; SELECT only; each
   path refused at the edge without a token first — 403, an Access header, no execution; the scratch removed, GET 404):
   a row → output 0 one item (numeric `fields.cost_usd`), output 1 empty · no row → output 0 ONE empty item, output 1
   empty · a query error (a missing table) → output 0 one empty item, output 1 one `{error, message}` item;
   `$('…').all(1)` returned `[]` for a row and for no row, one item for the query error, and never threw. **The model in `eval-spend-fail-closed.test.cjs` is confirmed** for
   these three (`ROW`, `NO_ROW`, `QUERY_ERROR`); the thrown case was not provoked and stays a model result.
2. **The leads table, `salon_ro`, counts only:** **0 rows** (positive control on the same connection: `bot_metrics` 1 row,
   `to_regclass('salon.leads')` exists). So the first 30-day run deletes nothing, and no real lead is affected. For #13
   the seed needs at least 5 `pd-` rows (one aged), because the cap is `floor(20% of the table)`.
3. *(Yigitcan's, with Cowork — the widget page.)*
4. **Retention outside the database:** the engine's run records — the oldest stored execution was **13 days 23 hours**
   old (every execution read through the API), which fits n8n's default pruning of 336 hours; the setting itself was
   not read. The salon dumps — the nightly job calls `pg-backup.sh` without `PG_BACKUP_KEEP_DAYS`, so its default
   **14** is in force. **Found, not planned:** the engine's own database, which holds the run records, is backed up
   too and those copies are removed after 14 days as well. *(Raw counts and file listings are deliberately not
   recorded here — inventory that goes stale, `security-auditor` L1.)* `/privacy` now states all three: run records about 14 days, and backups of either database
   kept more than 14 full days.

**Fixed (each with a test case and a mutant that dies):**
- **Bound (i), ruled WIDEN:** `Build Spend-Cap Reply` raises `spend_meter_unavailable` (and the error flag in the body,
  like the other `*_unavailable` replies, 200) when `_spend.meter` is `unreadable`; a reached budget stays `spend_cap`.
  On a caught read error the meter alert and the closed turn now carry the same class and so one throttle key: the owner
  gets one alert. Its first comment no longer says only "budget reached" (the MEDIUM-4 residue). The Main delta is
  four nodes (`Build Spend-Cap Reply` added; not a GATE node); the sticky's last sentence, which named the old bound, is
  corrected. `eval-spend` 13 tests, mutants 16/16.
- **The leads-cap sentence (the HIGH-1 residue):** the page says the limit is checked every night and can keep stopping
  the job until the owner deletes by hand. Privacy mutants 13/13.
- **`measure` (the MEDIUM-5 residue):** only Vercel's documented paused answer — 503 with `DEPLOYMENT_PAUSED` in the body
  (vercel.com/docs/errors/DEPLOYMENT_PAUSED; no header is documented, so none is relied on) — is "offline" (exit 3); a
  401, 404, redirect or bare 503 is "unexpected" (exit 5); `pause` succeeds only on the paused answer. demo-offline
  mutants 15/15.
- **The privacy contact:** pending Yigitcan — the page shows a visible PLACEHOLDER while the value is absent. **A go-live
  blocker.** *(Until R2h this read "`PRIVACY_CONTACT = null`, pinned by the test"; since R2h the value is the build-time env
  `NEXT_PUBLIC_PRIVACY_CONTACT` and the test pins the env read, never a literal — corrected in place, `security-auditor`
  M2.)*

**Deployed (2026-10-30, the ⚠ ONAY in the R2a brief):** each edit rehearsed on a scratch first (edit + rollback read
back green, scratch deleted with a 404 read back), then deactivate → put (a pre-PUT snapshot kept outside the repo) →
activate (published == draft). Main: 4 nodes changed, the dummy-token probe 403, the sole holder of its path; Purge: 1
node. **Promoted** in the next commit: the staged exports copied over the committed ones (`n8n/staged/` emptied), the
example config's `leadsRetentionDays` 30, and the fail-open sentences corrected (FLOW-DIAGRAM, DATA-MODEL,
UX-ARCHITECTURE, the engine-shape table in `chatClient.ts`). Purge's first 30-day run is tonight's 04:00 run (the table
is empty, so it deletes nothing — measurement 2).

**Vercel (2026-10-30, the ⚠ ONAY in the R2a brief):** account plan **Hobby** (read from the API). Project
`salon-booking-demo` created with `framework: nextjs`, `rootDirectory: web/site` and **NO git link**, so no push can
deploy it before the go-live checks — the first deployment is a deliberate step. **Protection, measured as far as it can
be without a deployment:** `ssoProtection: {deploymentType: "all"}` (Vercel Authentication on every deployment,
production domains included) was ACCEPTED on Hobby and reads back `enabled: true, deploymentType: all`; whether it
actually refuses a visitor on the production domain is measurable only on a deployment, so it is **not yet measured**
(and it must be switched off at go-live, or the public cannot reach the demo). Env: `NEXT_PUBLIC_WEBHOOK_URL` (Main's
widget path; public by design — it is inlined into the browser bundle). **Not set by CC:** `NEXT_PUBLIC_TURNSTILE_SITE_KEY`
— its only copy here is in a gitignored env file that CC does not read; it is public and shown on the widget's page, so
it is entered in step B. Domain `demo.<apex>` added to the project: `verified: true`, `misconfigured: true` until the
DNS record exists. **The DNS target Vercel recommends** (`get_domain_config`, rank 1): `CNAME cname.vercel-dns.com.` —
the GENERIC target, not a project-specific one as the dashboard steps below expected; the API offered no other CNAME.
Build settings (install from the `web/` workspace root) are not measured until the first deployment.

### Go-live checks — every one true BEFORE the first public deployment (R2a, `code-reviewer` MEDIUM-1)
**State after R2h:** true — 2, 3, 5, 7, 8, 9 (and the `engines` cap, committed with 9) · open before go-live — 1 (the
contact env is set; the controller's value has not reached CC, and the DEPLOYED page could not be read without a
protection change) and 4 (every row filled in an isolated build with fake values; the deployed page is unread) · after
go-live (rulings) — 6 (the alias cannot mint) and #15, then #13's read, #19, #21 · **at
the phase close: the Vercel token is revoked.**
A check that lives only in a sentence does not stop a deploy, so they are listed here, by number, and the deploy step
reads this list:
1. **The privacy contact and the controller are published** *(R2c: pending — a Zoho address from Yigitcan; Cloudflare
   Email Routing is ruled out)*: measured on the DEPLOYED `/privacy` — neither PLACEHOLDER text is on the page, and the
   contact and the controller are. Since R2h both come from build-time env (`NEXT_PUBLIC_PRIVACY_CONTACT`,
   `NEXT_PUBLIC_PRIVACY_CONTROLLER`, rulings R2h-1/2), so the source cannot answer this check — only the built page can.
   *(Until R2h the check read "`PRIVACY_CONTACT` in `web/site/lib/privacy.ts` is not `null`"; corrected in place,
   `security-auditor` M2.)* **R2g: open —
   STOPPED.** Yigitcan named the address (a Zoho alias at `<apex>`), but `<apex>` is a redaction target, so the
   host-leak guard flags the address in all three of its scans; the brief stops there and no guard is edited without a
   ruling (see "R2g"). **R2h: open** — the mechanism is built (build-time env, rulings R2h-1/2); `NEXT_PUBLIC_PRIVACY_CONTACT`
   is set in Vercel production (read back by name); `NEXT_PUBLIC_PRIVACY_CONTROLLER` is NOT set — its value is in neither
   the brief nor anything CC can read, and CC does not guess a person's name; and the deployed page was not read, because
   every route to a protected page is a protection change (see "R2h").
2. **The Main put and the Purge put are live and promoted** (parity green against the promoted exports).
3. **Widget step B is done and #11 is measured by behaviour** (another hostname → `110200`). **R2b: true** (`127.0.0.1`
   → `110200`, with a control; see "R2b").
4. **The `/privacy` text is final** — the leads retention reads 30 (from the promoted example config) and the measured
   copies outside the database. **R2g: open** — read from the built page: retention and the copies outside the
   database are stated; the controller is not named, there is no legal basis or rights statement, and the deletion
   path runs only through the contact, which is still the placeholder (see "R2g"). **R2h: open** — legal basis, rights,
   the complaint right and the two kept records (measured: "not deleted automatically; deleted on request", with the
   procedure in RUNBOOK §8) are on the page; in an isolated build with fake values every row R2g found empty is filled.
   Still open: the same read on the DEPLOYED page (with check 1), and the counsel note below.
5. **The first real pause records Vercel's actual paused body** — `measure` counts only `DEPLOYMENT_PAUSED` in a 503
   body, the documented form; if the real body differs, `pause` exits 1 and `measure` exits 5 (the safe direction),
   and the script is corrected before go-live. **R2f: true** — the real answer is a 503 with `x-vercel-error:
   DEPLOYMENT_PAUSED` and the marker in its body; `measure` → exit 3; no correction needed.
6. **The `*.vercel.app` alias cannot mint a token** — the deployment's `*.vercel.app` address is a second public name
   for the same page, outside the widget's hostname list, so the widget there must fail with `110200` (measured by
   behaviour on the deployed alias, the way #11 was measured on `127.0.0.1`), or the alias is switched off
   (`security-auditor` L2, R2a). **R2c ruling: measured right AFTER go-live** — while protection is on, the alias shows
   Vercel's protection, not the widget, so there is nothing to mint against before then; #15 moves after go-live too.
7. **#12 is GREEN by behaviour** — the edge rate limit actually blocks above its threshold. **R2c: true** (blocked from
   the 31st of 40 requests in 2.4 s; the rule: 30 requests per 10 s per IP and Cloudflare data centre, Block for 10 s). R2b's "RED" was its probe, see R2b.
8. **#16 is read back on the real deployment** — (a) platform, (b) root `web/site`, (c) no `web/dashboard` path in the
   deployment's file list, (d) an unauthenticated visitor gets Vercel's protection on BOTH the demo hostname and the
   `*.vercel.app` alias, never the page. Only then is protection switched off — which is what makes the demo public.
   **R2f: true** on a READY production deployment (all names and the static paths → `302` to Vercel's login).
   **R2g: true again** on the 16.4.1 deployment — every name × the paths plus `/_next/image`, 45 of 45 → `302`
   *(terminal-measured; see "R2g")*.
9. **`next` is past every critical/high advisory of its own** — measured with `npm audit` on the committed lockfile
   (auditor LOW-1, R2e; ruling (2), 2026-10-30: patching is a gate, not an acceptance). *(R2f: open — the lowest clean
   version is 16.4.1, a minor jump; waiting on a ruling.)* **R2g: true** — `next` 16.4.1 in `6a19a06`; `npm audit` on the
   committed lockfile: 0 advisories of any severity; Vercel's install of the deploy set: "found 0 vulnerabilities"
   *(terminal-measured, not committed)*.

### R2h — `/privacy`: controller and contact from build-time env, GDPR basics, the kept records stated as measured; redeployed, protected (2026-10-30; no go-live)
**Rulings (Yigitcan, 2026-10-30), verbatim except the two values:** "(0) dashboard 16.4.1 deviation ACCEPTED; OPS-10's
state kept (no rollback). (1) contact enters at build time as a Vercel env value (same path as NEXT_PUBLIC_WEBHOOK_URL),
not source. (2) controller identity shown on the page, value = `<controller>`, via the same env path. Neither value ever
enters the repo, a commit, a report or a screenshot — reports write `salon-demo@<apex>` and `<controller>`. (3) generic
text added (same for every client): legal basis for the demo = GDPR Art. 6(1)(f) legitimate interest (demonstrating the
product); rights (access, rectification, erasure, objection); right to lodge a complaint with a data-protection
supervisory authority. Plan note: client deployments must have their own counsel review this page. (4)
conversation-log and booking-record retention: measure where each lives and whether any automatic deletion exists (from
committed workflows/config — no deletion run on real data); the page states what is TRUE. No automatic deletion →
"deleted on request" + the manual deletion procedure written into RUNBOOK. No new purge. (5) delete the R2g scratch repo
— approved."
**Plan note (ruling 3): a client deployment's `/privacy` must be reviewed by that client's own counsel** — the text here
is the demo's, and `security-auditor` noted what it does not cover (the restriction right, Art. 18; transfers to
services outside the EU, Art. 13(1)(f)). Those were not added: ruling (3) names the list.

**Start gates (23:24 Vienna): FIRST and outside the Reminders window** — all green *(terminal-measured, as is everything in C below)* (dummy token 403, both parity guards,
listeners, host leak, hook drift; secret scan "NOT MEASURED" on a clean tree, by design). **(5):** the R2g scratch repo
deleted, read back absent; the file its link pointed to is untouched *(terminal-measured)*.

**A — the mechanism (`9f05b21`).** `PRIVACY_CONTACT` / `PRIVACY_CONTROLLER` = `envValue(process.env.NEXT_PUBLIC_PRIVACY_CONTACT
| …CONTROLLER)` — literal references, which Next inlines at build (its own guide, read in `node_modules/next/dist/docs`);
unset or blank → null → the visible placeholder. Used only by `/privacy` (a server component). Tests:
`web/site/lib/privacyEnv.test.ts` (site `check`), `privacy-facts.test.cjs` (env reads only, no e-mail address in the
source, both branches). **Built in an isolated copy, never in `web/` (OPS-10)** *(terminal-measured)*:

| build | controller | contact |
|---|---|---|
| both env unset | placeholder | placeholder |
| fake values (`example.test`, "Test Controller") | named | shown |

**B — the content (`cb9730a`, then `881a440` and `9a5be00` after review).** Ruling (3)'s text, and ruling (4) measured from
the committed exports and `db/schema/001_init.sql`:

| record | where | automatic deletion |
|---|---|---|
| message text | `conversations.recent_messages` | emptied by Purge after 30 days |
| the conversation record (step, slot, last reply `computed_reply`, session id) | `salon.conversations` | **none** — no workflow deletes from it; Purge's only write empties `recent_messages` |
| the booking | `salon.appointments` | **none** — cancelling sets `status = 'cancelled'` |
| the calendar event (service, time, name in its title) | the demo's Google Calendar | only when cancelled in the chat |
| message ids · callback requests | `processed_messages` · `leads` | 30 days · 30 days, within the cap |

So the page says the conversation record and the booking are "not deleted automatically; deleted on request", that a
record deleted on request keeps its copies in the backups and run records until they expire, and what a requester should
give for the records to be found (the session id is gone with the tab). The procedure is RUNBOOK §8. No purge was added.
The test holds all of it to every committed workflow: every parameter string walked raw, quotes normalised, `TRUNCATE`
included, every Postgres node a plain query, no SQL emptying `computed_reply`, with a positive control. Mutants 27/27.
*(Two forms still pass, recorded rather than chased: an empty value passed as a SQL parameter, and a non-`postgres` node
type with a native delete — `security-auditor` INFO, R2h.)*

**Review — `security-auditor`, four rounds, push GO each time.**
- **M1:** "deleted on request" with no procedure and no way to find a record. Fixed by RUNBOOK §8 and the requester sentence on the page.
- **M2:** the plan still said "`PRIVACY_CONTACT = null`, pinned". Corrected in place, and go-live check 1 now reads the deployed page.
- **L1, then L-1:** the delete scan missed quoted names and `TRUNCATE`, then multi-line SQL. Fixed.
- **L2:** copies of a record deleted on request. Fixed.
- **M-1:** the access step pointed at the dashboard's CSV export, which is masked and returns the whole table (other people's rows). It now sends only the matched rows, read unmasked.
- **L-2:** go-live check 4 still described R2g. Fixed here.

**C — pushed `fae3ea6`; env; redeployed.** `NEXT_PUBLIC_PRIVACY_CONTACT` created through the Vercel connection —
`encrypted`, production — and read back BY NAME through the REST API (key, type, target; no value printed).
**`NEXT_PUBLIC_PRIVACY_CONTROLLER` was NOT set:** ruling (2) names whose name it is, not the value, and the value is in no
file CC can read; CC does not write a guessed name onto a legal page. Redeploy (56 files, 0 under `web/dashboard`):
**`READY`, production**, Next 16.4.1, install "found 0 vulnerabilities" *(terminal-measured)*.
**The deployed page: NOT read — the brief's stop condition.** The REST file tree lists `/out/privacy` and its `.rsc`
segments as `lambda` outputs with no file id, so their content cannot be fetched with the token; every other route to a
protected page changes protection: the Vercel connection's `web_fetch_vercel_url` creates a 23-hour share link anyone
holding it can open *(from the tool's own description, not measured)*, and a bypass secret was ruled out in R2c. **Unauthenticated, 5 names — `demo.<apex>`, the two project aliases, the R2f
deployment URL and the NEW R2h deployment URL (R2g's deployment URL was not in this set) — × the R2g 9 paths
(`/_next/image` included): 45 of 45 → `302` to `vercel.com/sso-api`, the page nowhere** *(terminal-measured)*.

### R2g — `next` 16.4.1 committed and deployed, protected; the privacy contact STOPPED at the host-leak guard (2026-10-30; no go-live)
**Rulings, verbatim where the repo can carry them** *(auditor LOW-5 of R2f: they had only been paraphrased)*:
- R2f, Yigitcan, 2026-10-30: "(1) project Node → 24.x — APPROVED, deployed ALONE (attribution). (2) next advisory — NOT
  accepted; patching is a go-live gate. Target = lowest 16.x where `npm audit` shows no critical/high for next — measure
  it, don't assume it. (3) web/package.json engines upper bound `<25` — APPROVED. Whether Vercel honors it = unverified,
  record as such. Failed deployments stay (no deletes)."
- R2g, Yigitcan, 2026-10-30: "(1) next → 16.4.1 APPROVED (the R2f stop was correct; the conflict was in Cowork's brief
  wording). (2) privacy contact = `salon-demo@<apex>` — Zoho alias, delivery verified by a test mail landing in the
  mailbox." *(The domain is written as `<apex>` because it is a redaction target — the subject of B below. "Delivery
  verified" is an operator statement, not measured here.)*

**Start gates (23:03 Vienna):** all green — dummy token 403, both parity guards, listeners, host leak (3 targets), hook
drift, secret scan. ⚠ **Two gate deviations, recorded:** (1) they did NOT run first — they were deferred to wait out the
Reminders window, and A's install (about 22:58), builds and commit (`6a19a06`, 23:02) happened before them; (2) at 23:03
they were still INSIDE the Reminders window (:55–:05) — the clock was misread; one dummy-token request reached Main and was
refused at Turnstile (403). The end gates ran outside the window. *(The first version of this line named only (2);
`security-auditor` MEDIUM-1 found the order from the timestamps.)*

**A — commit `6a19a06`: GREEN.** `next` 16.3.4 → **16.4.1** in `web/site` AND `web/dashboard` *(declared: the brief named
`next`, not the two packages; they share one lockfile and one deduped `next`, so bumping only the site would have left
the dashboard on 16.3.4)*; `engines.node` `">=22.18 <25"`; `npm audit fix`, non-breaking only. **The audit fix was two
packages, not the five lockfile changes measured in R2f:** `sharp` 0.35.5 (with its `@img/*` binaries) arrives with
`next` 16.4.1 itself, so the fix left `fast-uri` 3.1.7 → 3.1.9 and `source-map-js` 1.2.1 → 1.2.2. The lockfile diff
holds only the `next`/`@next`, `sharp`/`@img`, `fast-uri` and `source-map-js` families plus the two workspace entries
(`security-auditor`: 0 added, 0 removed, every changed entry resolved from registry.npmjs.org with a sha512 integrity).
No app source changed. `check-all` 0; `next build` green on Node 24.21.0 for the site (5 static pages) and the
dashboard. **`npm audit`, all severities** *(terminal-measured)*:

| | critical | high | moderate | low |
|---|---|---|---|---|
| before (`a6584cb`) | 1 (`next`: 3 advisories) | 2 (`sharp`, `source-map-js`) | 1 (`fast-uri`) | 0 |
| after (`6a19a06`) | 0 | 0 | 0 | 0 |

⚠ **The in-place build broke the live owner dashboard for about three minutes** (OPS-10): it runs from `web/dashboard`,
so the install and the build replaced what its 16.3.4 server was loading; `/` returned 500 to the measuring request. A
restart put it on the 16.4.1 build on disk (`/` 200, loopback only, no error since). **So the dashboard now runs 16.4.1** —
by that accident, not by a deployment decision; recorded rather than reverted, since reverting needs a second rebuild
and restart of the same service.

**B — the privacy contact: STOPPED; nothing committed.** The mechanism the plan and code already define is the source
constant `PRIVACY_CONTACT` in `web/site/lib/privacy.ts` — one place, pinned to `null` by
`tests/unit/privacy-facts.test.cjs`; no config or env route existed then, and none was added in R2g *(R2h added the env
route by ruling R2h-1)*. **Measured, not assumed:** in an
isolated scratch repository (the real guard script, `CLAUDE.local.md` linked rather than copied, the address assembled
from the parsed apex rather than typed), the null constant → `check-no-host-leak.sh` exit **0** (3 targets scanned);
the address in the constant → exit **1** unstaged and exit **1** staged, the hit in all three scans *(terminal-measured;
the scratch repository is not committed)*. The brief's stop
condition ("any guard flags the contact address → STOP, no allow-list/guard edit without a ruling") applies. **For the
ruling:** the address's domain IS the apex, so any repo file that carries it carries a redaction target. The options:
(a) the address reaches the build the way `NEXT_PUBLIC_WEBHOOK_URL` already does — a Vercel env value, never a repo
file (that URL carries a redaction target too), with the page failing closed to the placeholder when it is absent; (b) a
guard exception for exactly this address; (c) a different address, on a domain that is not a redaction target; (d) the
apex ceasing to be a target. (a) is a new mechanism and (b) an allow-list edit, so each needs a ruling; **CC's
recommendation is (a)**, because it is the pattern the repo already uses for a value of the same class.
**What `/privacy` states, read from the BUILT page** (`next build` output, not the source):
- **Controller:** not named — the page speaks of "the demo's owner" and "the demo author's own server"; no name, entity
  or address. *(Gap.)*
- **Contact:** the visible PLACEHOLDER ("the contact for privacy requests has not been published yet; it is added before
  this demo goes live"). *(Gap — B.)*
- **Purpose:** stated per item, not as a section — messages go to the AI "to work out what you want"; bookings are
  written to the calendar and database; the owner is alerted on handoff or failure; the session id lets a conversation
  continue. No legal basis is stated. *(Gap.)*
- **Retention:** stated — message text 30 days after last activity; message ids 30 days; callback requests 30 days (with
  the cap's caveats); backups at least 14 days more (typically about 15); the engine's run records about 14 days plus
  backups. The conversation record and the booking record are kept with no period ("kept", "not deleted
  automatically"), and owner alerts are outside the deletion. *(Stated; the two open-ended records are a gap to rule on.)*
- **Deletion request path:** only the contact — "to ask what the demo holds about you or to have it deleted" — which is
  the placeholder at R2g; no other route and no rights or complaint statement. *(Gap — see R2h.)*
No content was added; these are for go-live check 4.

**C — pushed and redeployed: GREEN.** `6a19a06` pushed after `security-auditor` GO (0 findings). Redeploy with the same
script (54 files, 0 under `web/dashboard`): **`READY`, production**, `projectSettings.nodeVersion = 24.x`; the build log
reads "Detected Next.js version: 16.4.1", install "added 39 packages … found 0 vulnerabilities", 5 static pages. Token
outside its 0600 file: 0 *(these build-log and count values: terminal-measured, not committed)*. **Unauthenticated, the R2f name set plus the new deployment URL** (`demo.<apex>`, the two
project aliases, the R2f and R2g deployment URLs) **× the R2f path set plus `/_next/image`** (`/`, `/barber-widget.js`,
`/privacy`, `/install`, a font, a `/_next/static/` path, `/robots.txt`, `/_next/image` with and without a query): **45 of
45 requests → `302` to `vercel.com/sso-api`, the page nowhere** *(terminal-measured)*. Whether Vercel honours
`engines` stays unverified: the build printed no engines message either way.

**Auditor LOW-1…6 of R2f:**
- **LOW-1 — resolved:** `/_next/image` read without authentication (both forms, every name) → 302, above.
- **LOW-2 — resolved:** the Image Optimization reachability sentence in R2f is labelled as reasoning.
- **LOW-3 — resolved:** the ROADMAP's R2f stop sentence now says what the plan says (the brief's "minor jump" and
  ruling (2)'s "lowest 16.x" read differently, so it went to a ruling).
- **LOW-4 — resolved:** the ROADMAP's R2e sentence ("not used in the source") now points to R2f's weakening of it.
- **LOW-5 — resolved:** the rulings are recorded above, verbatim except the redaction target.
- **LOW-6 — recorded, not fixed:** the shell `unpause` waits for a 200, so while protection is on it exits 1 even when
  the project did unpause; the RUNBOOK says so now. The shell `pause`/`unpause` were never run live (R2f used the Vercel
  connection), and R2f's "no correction needed" for `pause` is an inference from the check `measure` shares with it,
  not a measurement.

### R2f — Node 24 green, deployment protected and measured, pause drill done; the `next` patch STOPPED (2026-10-30; no go-live)
**Start gates (21:21 Vienna):** all green.

**A — Node 24.x alone (ruling (1)): GREEN.** The project's Node set to `24.x` through the Vercel connection and read back
through the REST API (`nodeVersion: "24.x"`; install command, root directory, protection `all` and no Git link
unchanged). Redeploy of `8f5a283` (54 files, 0 under `web/dashboard`) with the same script: **`READY`, target
production** — install "added 39 packages", `next build` compiled, 5 static pages, "Build Completed". **Which Node:** the
build log does not print a version; the deployment record reads `projectSettings.nodeVersion = 24.x`. So "Node 24 is
required" is measured for THIS tree only: 26.x red (R2e), 24.x green on Vercel and locally. *(R2e wrote it as a
requirement before Vercel had built on 24 — auditor LOW-3; it is now a measurement, for this tree.)*

**#16 — GREEN on a READY deployment, all four read back** *(terminal-measured; outputs not committed)*: (a) platform
Vercel · (b) root `web/site` · (c) no `web/dashboard` in the file list (R2d, same 54-file set) · **(d) protection, by
behaviour: every name the deployment answers to — `demo.<apex>`, two project aliases (`<project>.vercel.app`,
`<project>-<team>.vercel.app`) and the deployment URL — returned `302` to `vercel.com/sso-api` to an unauthenticated
request, with no page; so did `/barber-widget.js`, `/privacy`, `/install`, a font, `/_next/static/` and `/robots.txt` on
the demo hostname and an alias.** The stop condition (page reachable unauthenticated) was never met.
**Certificate:** issued for `demo.<apex>` by Let's Encrypt, valid 2026-10-30 → 2027-01-28, subject and SAN the demo
hostname only.

**Pause drill — DONE (go-live check 5)** *(terminal-measured)*. `pause_project` (the Vercel connection): the demo hostname
answered at the first poll with **Vercel's real paused answer: `503`, header `x-vercel-error: DEPLOYMENT_PAUSED`,
`server: Vercel`, `content-type: text/plain`, a 99-byte body "The deployment is currently unavailable" / `DEPLOYMENT_PAUSED`
/ a request id.** The body is not the documented "DEPLOYMENT_PAUSED: Service Unavailable" wording, but it carries the
marker `measure` looks for: **`demo-offline.sh measure` → `offline (503 DEPLOYMENT_PAUSED)`, exit 3** — the script needs
no correction. An alias gave 503 too. `unpause_project`: back within about 5 s to `302` (protection) on the hostname and
both aliases, the project reading `paused: false`; **`measure` then exits 5 ("unexpected (302)")** — correct by design:
while protection is on, the site never answers 200, so "online" cannot be measured until go-live, and a protection
answer is never mistaken for offline.

**B — the `next` patch: STOPPED before any change (ruling (2) and the brief's stop condition meet here).** Measured, not
assumed: a lockfile-only install of each candidate in its own scratch directory, then `npm audit` *(terminal-measured)*:

| next | next's own advisories |
|---|---|
| 16.3.4, 16.3.5 | critical 3 · high 2 · moderate 5 · low 1 |
| 16.3.6, 16.3.7 | critical 2 · high 2 · moderate 5 · low 1 |
| 16.3.8, 16.4.0 | critical 2 · high 1 |
| 16.4.1, 16.4.2, 16.4.3 | none |

At 16.3.8 the three remaining advisories all carry the range `>=16.0.0 <=16.4.0`: an unauthenticated RCE in the Image
Optimization API (critical, GHSA-2464-fhr4-w9xw), an RCE in `use cache` functions (critical, GHSA-673q-mjm6-r5xr) and a
Server Actions DoS (high, GHSA-p3m5-59mp-jv5r). **So no 16.3.x patch clears next's critical/high; the lowest clean
version is 16.4.1** (published 2026-10-14). The note that the `next/og` RCE is fixed in 16.3.6 is consistent with the
table (16.3.6 drops one critical), but other criticals remain. **That is a minor jump (16.3 → 16.4)**, and the brief stops
on "a minor jump beyond 16.x patch" while ruling (2) says "lowest 16.x" — the two read differently here, so nothing was
changed: no `next` bump, no `engines` cap, no `npm audit fix`. **A ruling.** *(R2e's "16.0.0–16.4.0" range was itself
read from `npm audit`'s summary range; the per-advisory ranges above are the measured ones.)*
**For that ruling, also measured:** `npm audit fix --dry-run` on the deploy set's lockfile offers non-breaking fixes for
the three transitive advisories (`fast-uri`, `sharp`, `source-map-js`; five lockfile changes). **And the applicability
reading of R2e (auditor LOW-2) is weaker than it looked:** an Image Optimization endpoint can exist whether or not the
app imports `next/image` *(reasoning, not measured — label added in R2g, auditor LOW-2 of R2f)*, so "the feature is not
used in the source" does not show the critical one is unreachable — another reason the patch is a gate, not an
acceptance.

### R2e — install fixed, build red on Node 26 (2026-10-30, the R2e brief; no go-live) — ⚠ stopped: no third attempt
**Start gates (21:06 Vienna):** all green. **Precondition measured first:** in a `git archive` copy of the deploy set,
`cd ..` from `web/site` lands in `web/`, which holds `package.json` (workspaces `shared, site, snippet, dashboard`) and
`package-lock.json`; `npm ci` there added 39 packages with `esbuild` present *(terminal-measured)*.
**Install Command set** to `cd .. && npm ci` (ruling of 2026-10-30) through the Vercel connection, and read back through
the REST API — the connection's answer does not show the field: `installCommand: "cd .. && npm ci"`, `rootDirectory:
"web/site"`, `sourceFilesOutsideRootDirectory: true`, `ssoProtection: {deploymentType: all}`, **no Git link**, `nodeVersion:
"26.x"`.

**The redeploy** (same script, `8223fb8`, 54 files, 0 under `web/dashboard`): **the install is now GREEN** — Vercel ran
`cd .. && npm ci`, "added 39 packages", and the snippet built (18.1 kB). **The build is RED in a new place:** `next build`
(Turbopack) failed with 6 errors, `Module not found: Can't resolve '@vercel/turbopack-next/internal/font/google/font'` /
`next/font/google queries have exactly one entry`, in the `next/font/google` faces of `web/site/app/layout.tsx`.

**The cause, reproduced rather than guessed** *(terminal-measured)*: the same copy built locally with **Node 26.13.0** —
the version in Vercel's build log, from the official tarball checked against `SHASUMS256.txt` (a checksum over TLS, not
a signature check) — fails with the identical errors; built with **Node 24.21.0** it is green (`/`, `/install`,
`/privacy` static). **So the build breaks on Node 26 with this Next (16.3.4), and the project's Node setting is
`26.x`.** The fix is again a project setting, not code: Node **24.x** for the project — **a ruling**, since the brief
allowed no third attempt.

**What an unauthenticated visitor saw — no page anywhere:** the new deployment URL → 302 to `vercel.com/sso-api`;
`demo.<apex>` → no TLS for 90 s (no READY production deployment to assign it). **#16(d) on the demo hostname, the
certificate and the pause drill all still wait for a green build.** Token handling as in R2d: the files the scripts
produced held the token's value 0 times (the same scope as R2d's count).

**Found on the way — Vercel's `npm ci` reported 4 advisories**, listed by `npm audit` on the same lockfile: **`next`
16.3.4 — critical** (range 16.0.0–16.4.0; among them an RCE in `next/og`'s `ImageResponse`, a Draft Mode leak through
`use cache`, ISR cache poisoning when self-hosted) · `sharp` high · `source-map-js` high · `fast-uri` moderate (all
transitive except `next`; fixes exist). A search of `web/site`'s source for `next/og`, `ImageResponse`, `use cache`,
`revalidate`, `draftMode` and `sharp` finds no use (only generated type files and a comment), and every route is static
— so the critical one looks inapplicable, **but that is a reading, not a test. A ruling before go-live:** raise Next
past the fixed range (a version at least two weeks old) or accept with this reason recorded.

### R2d — first deployment attempted (2026-10-30, the R2d brief; no go-live) — ⚠ stopped: Vercel's build was red
**Start gates (20:43 Vienna):** all green, as before. **The route (ruling of 2026-10-30, reversing R2a's "no token"):**
a team-scoped Vercel token created by Yigitcan in `~/.vercel-demo.env` (mode 0600, this user — measured), used only
for this phase and revoked at its close; Git integration stays off. **CLI:** `vercel@64.3.1` — the newest stable
release published at least two weeks earlier (2026-10-15) — installed into a scratch prefix. Its own code reads
`VERCEL_TOKEN` from the environment (`tokenSource = "env"`), so for the deployment the token went from the 0600 file into
the deploying process's environment: never `--token`, never printed; the CLI's global config pointed at a scratch
directory. **The second place it existed, named:** the build-event read below sent it through a temporary 0600 header
file created with `mktemp` and removed by the script's exit trap (the same pattern as `scripts/demo-offline.sh`).
**What was counted, and its scope:** after each token-using step a script counted, among the files it produced, those
containing the token's value — the CLI log, the CLI's global config directory, the deploy directory, the measured
headers and bodies, the build-event output: **0** each time. That count did not cover the temporary header file
(deleted by then) or anything outside those paths.

**Protection read back BEFORE deploying:** `ssoProtection: {enabled: true, deploymentType: all}`.

**The deployment** — `git archive HEAD` (`597b28a`), **54 files, 0 under `web/dashboard`**, `vercel deploy --prod`:
uploaded (344 KB *(terminal-measured, output not committed)*), built in `iad1` by Vercel's own `vercel build`, and **FAILED: state `ERROR`, `module_not_found` in
the build step.** The build events (read through the REST API with the token in a 0600 header file — the CLI's
`inspect` needs a user and a team-scoped token has none, `/v2/user` → 404) show the cause: Vercel's default install ran
in the project root `web/site` and added 36 packages (a local `npm ci` at the `web/` workspace root adds 39 — both
*terminal-measured, output not committed*); the site's
prebuild then built the snippet, and `web/snippet/build.mjs` could not find **`esbuild`** — the snippet's own
devDependency, which an install scoped to the `web/site` workspace does not bring. *(Why the install skipped it is
inferred from the package counts and npm's workspace behaviour, not from a package list.)* The R2b offline proof ran
`npm ci` at the workspace root, which is exactly the step Vercel did not take — the proof was right about the files and
silent about where Vercel would install them.
**Stopped on the brief's stop condition ("Vercel build red"); not retried.** The likely fix is a project setting, not
code: the install command at the workspace root (e.g. `cd .. && npm ci`) — **a ruling.**

**What an unauthenticated visitor saw** (the brief's stop condition was never met — no page anywhere):
- the deployment URL (`<deployment>.vercel.app`) → **302 to `vercel.com/sso-api`**, no page: Vercel Authentication answers;
- the project alias (`salon-booking-demo-<team>.vercel.app`) → **404**: no READY production deployment to serve;
- `demo.<apex>` → **no TLS** (curl 000 for 90 s *(terminal-measured)*); the likely reason — no certificate while no
  deployment is assigned to the domain — is Vercel's behaviour as understood, not measured.
So protection is observed on the deployment URL only, and on a FAILED deployment; on the demo hostname it is still
unmeasured.

**#16 on the real deployment (partly):** (a) platform **Vercel** (the deployment exists in the project, source `cli`,
region `iad1`) · (b) root **`web/site`** — by behaviour: the build ran in `/vercel/path0/web/site` · (c) the
deployment's file list (`list_deployment_files`) holds `config/`, `schemas/` and `web/{package.json,
package-lock.json, shared, site, snippet}` — **no `web/dashboard`** · (d) protection `all` read back, behaviour seen on
the deployment URL only (above). **Pause drill: not done** — it needs a READY production deployment.
The failed deployment is left in place (it serves nothing; removing a deployment is not reversible and buys nothing).

### R2c — measured (2026-10-30, the R2c brief; no go-live) — ⚠ stopped at the first deployment again, for a different reason
**Start gates (20:07 Vienna):** dummy token → 403 · exports parity and live parity green · listeners · host leak · hook
drift — all green.

**Step 1 — the site key env: DONE.** The brief carried the site key (a public value — it ships in every page). Before
use it was compared with the server env file's line by a script that printed only the verdict: **FULL MATCH**. Set in
the Vercel project as `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, type plain, targets Production and Preview; read back with
`filter_project_envs`: both env keys present (`NEXT_PUBLIC_TURNSTILE_SITE_KEY`, `NEXT_PUBLIC_WEBHOOK_URL`), each on
Production + Preview. The value is in no repo file.

**Step 2 — #12: GREEN** *(terminal-measured; the output is not committed)*. The rule as Cowork read it from the zone's
rate-limit phase: `barber-inbound-ratelimit`, enabled, path contains `/webhook/`, **30 requests per 10 s per IP and
Cloudflare data centre, Block, mitigation 10 s**. 40 GET requests in 2.4 s from this server to the non-existent
`https://<n8n host>/webhook/zz-rl-probe`: **requests 1–30 → n8n's 404; 31–40 → `429`, body `error code: 1015`,
`Retry-After: 10` counting down to 9** (no `cf-mitigated` header). The newest n8n execution id was the same before and
after: **0 executions**. The "20 requests a minute" that this plan, the RUNBOOK, the diagrams and the tests carried was
an unread assumption; every current-state sentence now states the read rule, and the historical records carry the
correction beside the old number.

**Step 3 — the first deployment: NOT DONE. The route the brief names cannot carry the files.** The Vercel connection
deploys files only as content inside the tool call: `create_deployment` takes each file's `data` inline, and
`upload_file` takes the file as a base64 `requestBody`. Its other route, `gitSource`, deploys from a Git repository
through the project's Git connection, and this project has none by design — R2a: no push may deploy before the go-live
checks (a Git deployment would also take the whole repository, `web/dashboard` included — reasoning, not measured).
The deployment set (54 committed files, R2b) includes two
binary fonts, `web/site/public/fonts/fraunces-variable.woff2` (205,500 bytes) and `instrument-sans-variable.woff2`
(88,784 bytes) — about 392,000 characters of base64 that would have to be read into CC's context and written back out
byte-exact. That is not a reliable transport, and a deployment that silently drops the fonts is not the page that goes
live. Checked, not assumed: there is no Vercel CLI on this server and no token file (`~/.vercel-demo.env` absent — R2a's
ruling was "no Vercel token"). **A ruling is needed** (recommendation in the R2c report): the recommended route is a
short-lived Vercel token, created by Yigitcan, scoped to the project's team, in `~/.vercel-demo.env` (0600) — the file
`scripts/demo-offline.sh` already specifies — so CC deploys a `git archive` of HEAD with a pinned Vercel CLI, the token
read from that file and never on a command line or in a report. The certificate, #16 (a)–(d), and Vercel's own install
and build wait for it.

**Step 4 — the pause drill: NOT DONE** (it needs a production deployment; without one the hostname does not complete TLS).

**Rulings recorded (Yigitcan, 2026-10-30):** #15 runs AFTER go-live against the public page — no bypass secret is
created. Cloudflare Email Routing is NOT used (the zone's MX is Zoho; enabling it would break existing mail); the
privacy contact will be a Zoho address Yigitcan provides — go-live stays blocked on it.

### R2b — measured (2026-10-30, the R2b brief; no go-live) — ⚠ stopped at the first deployment
**Start gates (19:27 Vienna):** dummy token → 403 · exports parity and live parity green · listeners · host leak ·
hook drift — all green.

**#13 — PENDING, not failed.** Purge has not run since the seed: its executions end at the 2026-10-30 04:00 run, which
was before the seed. The first 30-day run with the seeded row is 2026-10-31 04:00 Vienna. Read with `salon_ro` (counts only):
5 leads, all `pd-`, 1 older than 30 days, no non-`pd-` lead aged; the cap is 1, so that run should delete exactly 1.

**Step A — the DNS record.** Measured by CC: `demo.<apex>` is a CNAME to `cname.vercel-dns.com` on 1.1.1.1 and 8.8.8.8;
Vercel `get_domain_config` reads `configuredBy: CNAME, misconfigured: false`, and the project domain `verified: true`.
**No certificate yet:** `list_certs` is empty and a TLS handshake to the hostname fails (curl exit 35) — Vercel issues
the certificate for a domain that has a deployment, and there is none.

**Step B — the widget.** Mode **Managed** and the hostname list = the demo hostname only are **Cowork's reading through
its Cloudflare API connection, not a CC measurement** (that connection is not loaded in CC's session).

**#11 — GREEN by behaviour** *(terminal-measured; the output is not committed)*. A headless Chromium on this server loaded Turnstile on a page served from `127.0.0.1`
(bound to loopback, stopped by PID after the run), twice with the demo's site key and twice with Cloudflare's
documented always-pass test key as the control: **site key → `ERROR 110200` both times; test key → a token both
times.** The control shows the harness can produce the other answer, so the `110200` is the widget's hostname list
speaking, not a broken page. The page was generated by a script that read the key from the environment it sourced;
the key was never printed and never on a command line. The engine still answers a dummy token with **403** (start and
end gates). Mode recorded as Managed (Cowork's reading, above).

**#12 — R2b recorded RED; R2c showed the PROBE was wrong, not the rule** *(terminal-measured; the output is not committed)*. 25 GET requests in 1.7 seconds from this server to the non-existent `https://<n8n host>/webhook/zz-rl-probe`:
**all 25 answered 404 by n8n; none was blocked.** The instrument was checked rather than trusted: the host resolves to
Cloudflare addresses (no `/etc/hosts` entry), and the answer carries `server: cloudflare` and a `cf-ray` — the requests
DID cross the edge. No n8n execution was created (the newest execution id was the same before and after). Not
repeated. **Corrected in R2c:** the rule, read by Cowork, allows 30 requests per 10 s — 25 in 1.7 s were UNDER it, so
"no block" was the correct answer to a wrong question. R2b listed "the counting window or threshold differs from the
record" among the possible reasons; that was the one. The re-measure with 40 requests blocked from the 31st (R2c).
*(The R2b text concluded "the edge rule did not block" and called it a go-live blocker; both are withdrawn here rather
than left beside the correction. The lesson stands: a probe derived from an unread rule tests the assumption, not
the rule.)*

**Step 1 — the site key — MATCH, but not entered.** The site key in the server's env file starts with the widget's
prefix (`MATCH`, 24 characters; read by a script that printed only the verdict). Entering it into the Vercel project
env through the Vercel connection needs its value in CC's hands, and the command that would have printed it was
**refused by the deny layer** — which CC does not route around (`security-secrets.md`). This is the same limit R2a
recorded ("entered in step B"). **Consequence:** no deployment. The site build fails closed without the key
(`web/snippet/build.mjs`, "no NEXT_PUBLIC_TURNSTILE_SITE_KEY"), so a deployment now would only fail.

**What was proven for the first deployment, offline.** The deployment's file set is the committed tree, taken from
HEAD with `git archive`: `web/package.json`, `web/package-lock.json`, `web/shared`, `web/site`, `web/snippet`, and
from the repo root `config/client.config.example.json` and `schemas/client.config.schema.json` (the build reads the
example config and its schema from there in demo mode). That is **54 files, none under `web/dashboard`**. In a scratch copy of exactly that
set, `npm ci` at the workspace root succeeded with the `dashboard` workspace absent, and the site build with the real
public env succeeded (`/`, `/install`, `/privacy` static; the snippet built). Vercel's own install and build are still
unmeasured until the deployment runs.

**Not done in R2b, because they need the deployment:** #16 (a)–(d) and the alias check (6) · #15 (and Vercel's
"protection bypass for automation": its availability on Hobby is not stated in the documentation read, and generating
one returns the bypass secret to the caller — CC does not hold a secret's value, so that route needs a ruling) · the
pause drill (with no deployment the hostname does not complete TLS, so `measure` could only say "NOT measured").

### Yigitcan's dashboard steps (R2) — from Cloudflare's and Vercel's current documentation, read 2026-10-29
**Order:** CC adds `demo.<apex>` to the Vercel project and reads its DNS target → **A** → CC verifies the domain and
its certificate → **B** → CC measures #11 by behaviour.

**A — the DNS record** (Cloudflare: "Create DNS records"):
1. Cloudflare dashboard → the `<apex>` zone → **DNS** → **Records** → **Add record**.
2. **Type:** `CNAME` · **Name:** `demo` · **Target:** the value Vercel recommends for `demo.<apex>` — read by CC on
   2026-10-30: `cname.vercel-dns.com` (the generic target; the API offered no project-specific one). It is not guessed.
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
