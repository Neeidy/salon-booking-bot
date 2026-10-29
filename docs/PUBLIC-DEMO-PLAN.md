# Public demo — PLAN

> **Status: APPROVED by Yigitcan (plan-gate), 2026-10-29**, presented in chat in the full format, rulings D1–D6 as
> proposed (below). Derived against `07a10b5`. **R1 stopped at its start (below):** the proven deploy tool cannot carry
> the D2 Main edit under its current rules; nothing of R1 is built. The ship gate this phase serves is ROADMAP →
> "Ship gate after D6c" (items 11–16, 19, 21) plus the per-client Turnstile provisioning item moved here from Phase 8.
> Hostnames are written as placeholders on purpose: `<apex>`, `demo.<apex>`, `<n8n host>`, `<dashboard host>`.

## Rulings (Yigitcan, 2026-10-29)
- **D1** — the site on **Vercel Hobby**, public hostname **`demo.<apex>`** (a DNS-only CNAME to Vercel).
- **D2** — **ONE Main edit**, three parts: the Turnstile **hostname check** (siteverify's `hostname` against the config
  key `channels.widget.turnstile.hostname` — schema, render and both example configs), the **Turnstile secret into an
  n8n credential** (closes Phase 8's D4 finding), and **`Eval Spend` fail-closed**.
- **D3** — **one short-lived Cloudflare token**: Turnstile Edit + this zone's DNS Edit + WAF/Rulesets Read, 7 days,
  revoked at the phase close.
- **D4** — demo lead retention **30 days** (`leadsRetentionDays`).
- **D5** — gate #13 closed by the **real 04:00 Purge** deleting a back-dated synthetic `pd-` lead.
- **D6** — **standing approval for an emergency Vercel pause**; Main deactivation stays behind `⚠ ONAY GEREKİYOR`.
- **Honesty additions:** the `/privacy` page and the widget notice say plainly that bookings are written to a REAL demo
  calendar and that owner alerts (Telegram) may carry message text and sit outside Purge. Alert volume after go-live is
  measured in R3 and reported (no change now).
- **Convergence** (as in Phase 8): each review judges its round's diff; the same defect class twice → a recorded bound,
  no extra round.

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
| **#11** Turnstile weak | D2's hostname check; a NEW demo widget in **Managed** mode listing only `demo.<apex>` (no `localhost`), created by the provisioning script | offline: a stubbed siteverify `{success:true, hostname:<other>}` is refused (test + mutant); live: the dummy token is 403 | yes (Main write, ⚠ ONAY) |
| **#12** rate-limit BLOCK | to be measured: 25 requests a minute from this server to a NON-existent `/webhook/zz-rl-probe` path (the rule matches "path contains `/webhook/`"; no n8n execution, no LLM) — blocked after the 20th; the rule itself read with the D3 token | the blocking response and the rule's fields | yes (requests only) |
| **#13** leads TTL live | D5: a back-dated synthetic `pd-` lead seeded into production (the S2 pattern); the real 04:00 Purge deletes it | `salon_ro`: 1 row before, 0 after; the Purge execution | yes (a temporary workflow with a DB credential, ⚠ ONAY) |
| **#14** Privacy Addendum, the open half | a `/privacy` page on the site, linked from the footer and the widget | headless: the page, the links, Cloudflare's privacy link | no (build) |
| **#15** SP4a in Managed mode | the existing harness, headless, against the deployed page | the render-moment record | yes (read) |
| **#16** platform checks | read from Vercel after the deploy: (a) platform, (b) root directory, (c) `web/dashboard` absent from the deployment's file list, (d) the protection state | `get_project`, `list_deployment_files` | yes (read) |
| **#19** owner from the internet | Yigitcan opens `<dashboard host>` on his phone, signs in through Access, presses "release" on a seeded `pd-` conversation | CC reads the store change with `salon_ro` | yes (**Yigitcan**) |
| **#21** Turnstile up, real browser | Yigitcan books and cancels on the live demo | CC reads the executions, the store and the calendar (`cancelled`) | yes (**Yigitcan**) |
| **Turnstile provisioning** | `scripts/provision-turnstile.py`: creates the widget through the Cloudflare API and writes the secret straight into an n8n credential, never printing it; the site key into the Vercel env | offline: a mock API shows the secret reaches no stdout, stderr, log or file (test + mutant); live: one widget, its domain list = the demo hostname, no `localhost` | yes (Cloudflare + n8n writes, ⚠ ONAY) |

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
- **D2:** `Eval Spend` today runs the turn when the meter cannot be read (fail-open, ruled at K-SPEND); for a public
  endpoint it becomes fail-closed — a deterministic handoff reply and an alert.
- **Take the demo offline in one step:** pause the Vercel project (back with unpause). The site and the widget go; after
  #11 no valid token can be minted on another hostname, so the engine cannot spend either. `scripts/demo-offline.sh`
  (to be built in R1) will pause and measure. D6: standing approval for this pause in an emergency; Main deactivation stays ⚠ ONAY.

## 5. Yigitcan's unavoidable manual steps (minimised, grouped)
**Once, at the start of R2:**
1. **The D3 Cloudflare token** (spec at the end of R1); he types its value into `~/.n8n-api.env` himself — it never
   passes through the chat. Revoked at the phase close.
2. If Vercel's GitHub app does not cover this repo (unmeasured), one click to grant it.

**At the end, after go-live:**
3. **#19** — the dashboard from his phone, one button (Access e-mail code).
4. **#21** — one booking and its cancel on the live demo.

Everything else is CC's: the build, the Vercel project and env, the DNS record, the widget, the n8n credential, the
Main edit, the measurements.

## 6. Scope, NOT-build, skeleton, CRT, estimate
- **Goal:** the demo site public at `demo.<apex>` with gates 11–16, 19 and 21 closed or declared open with a reason.
- **NOT-build:** no new features; no WhatsApp / Zernio; no Phase 6c work beyond the gates; no CORS narrowing (not a
  security boundary — the Turnstile hostname check is); not #17's rotations, #18 or #20; no multi-tenancy.
- **Skeleton:** the Main edit (`Turnstile Valid?`, `Verify Turnstile` → credential, `Load Config` hostname key, `Eval
  Spend`); the Purge literal (`leadsRetentionDays`); `web/site/app/privacy/page.tsx` and the widget notice;
  `scripts/provision-turnstile.py`; `scripts/demo-offline.sh`; seed tool `pd-` actions; a RUNBOOK "public demo"
  section.
- **Integrations:** Vercel · Cloudflare (Turnstile, DNS, rulesets read) · n8n (Main, Purge, a credential) · Postgres
  (seed, reads) · Google Calendar (#21) · Telegram (alerts).
- **Mock data:** the demo salon is config-driven mock data; drill rows carry the `pd-` prefix and are cleaned to 0 by
  guarded SQL.
- **CRT derivation:** **#15 "public Turnstile boundary"** — the hostname binding, the secret in a credential, the
  provisioning that never prints it (criteria 3 and 5, plus a secret). One Codex run on the Main diff and the
  provisioning script. The deploy itself is configuration: checks, not a CRT.
- **Acceptance:** #11–16, #19, #21 closed or ruled open with a reason; the demo's own production widget, no
  `localhost`; "take it offline" shown (pause → the site unreachable, measured → unpause); tests and mutants green;
  guards 0; CRT #15 closed.
- **⚙ Drill matrix:**

| # | Scenario | Setup | Expected | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|---|---|
| 1 | real token | Yigitcan, live demo | book + cancel, one event | the LLM, the calendar write | a second event |
| 2 | wrong hostname | stubbed siteverify | 403, no LLM | the Turnstile branch | the LLM |
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
