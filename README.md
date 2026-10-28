# salon-booking-bot

**A config-driven salon booking chatbot — one message in, a booked appointment or a captured lead out.**

![status](https://img.shields.io/badge/status-learning%20%2F%20demo%20build-orange)
![phase](https://img.shields.io/badge/phase-7%20%E2%80%94%20test%20%2B%20audit-blue)
![store](https://img.shields.io/badge/store-Postgres%20self--hosted-336791)
![engine](https://img.shields.io/badge/engine-n8n%20self--hosted-EA4B71)
![llm](https://img.shields.io/badge/LLM-Claude%20Haiku%204.5-8A63D2)
![license](https://img.shields.io/badge/license-MIT-green)

> **Honest status:** this is a **demo / learning build**, not a system serving paying customers.
> Phases 0–6 are done. The bot's store then moved from Airtable to **self-hosted Postgres** in an interim
> phase whose cutover was accepted on 2026-10-24. Phase 7 (test, Codex audit, Definition of Done) closed on
> 2026-10-28 with its gaps named, and Phase 8 (a config-only second client) is in progress: its render step is built
> and proven offline, its independent audit is next — live status in
> [`docs/ROADMAP.md`](docs/ROADMAP.md). Everything below marked ✅ has been built **and verified from execution
> logs**; 🔜 means not built yet. No invented metrics, no fake traffic.

---

## The one job

A barbershop loses bookings because messages arrive while the owner is cutting hair. This bot answers
instantly, in the shop's voice, and turns each message into one of two outcomes:

**a booked appointment** — or — **a captured lead + a human handoff**

…with **zero owner effort** and **zero double-bookings**. It is built as a **template**: the goal is that a new
client means a new config file and new credentials, *not* new code — a goal, not yet a demonstrated fact (see
"Config / code / secret" below).

---

## How it works

```
                    ┌─────────────── config-gated channels ───────────────┐
   WhatsApp ────────┤                                                     │
   Web widget ──────┤   →  NORMALIZE  →  one channel-agnostic brain       │
                    │      {channel, sender_key, text}                    │
                    └─────────────────────────────────────────────────────┘
                                          │
   ┌──────────────────────────────────────▼──────────────────────────────────────┐
   │  1  Validate payload            invalid → 400                               │
   │  2  Load conversation state     Postgres, keyed by "{channel}:{id}"         │
   │  3  Handoff lock                a human took over → bot stays quiet         │
   │  4  Guards                      kill-switch · max-turns  → 0 LLM cost       │
   │  5  LLM intent extraction       Claude, structured JSON output              │
   │  6  Validate against schema     ajv compiled from the committed contract    │
   │  7  Confidence & intent gate    < 0.7 / unknown → ask once, then human      │
   │  8  Route (deterministic)       book · cancel · reschedule · FAQ · lead     │
   └──────────────────────────────────────┬──────────────────────────────────────┘
                                          │
        book → collect service/date/time (multi-turn, deterministic)
        FAQ  → answered from config — the LLM never writes the answer
        lead → written to Postgres
                                          │
                              reply returns to the origin channel
```

*`instagram` exists as a config key, but no Instagram adapter is built — a dead key, listed under "Not yet" below.*

**The LLM has exactly one job: understanding.** It converts messy free text into a structured intent.
It never writes a customer-facing answer, never chooses an action, and holds no write permissions.
Prices, hours and services come from config; routing is `IF`/`Switch`. That is why the bot **cannot
quote a wrong price** — the answer path contains no model.

---

## What works today ✅

| Capability | Detail |
|---|---|
| **Multi-channel intake** | WhatsApp + widget shapes normalized to one internal format; channels toggle in config |
| **Conversation memory** | Per-sender state in Postgres (`salon.conversations`: `stage`, slots, turn count) — survives restarts |
| **Intent understanding** | Claude Haiku 4.5, temperature 0, native structured outputs |
| **Contract validation** | Model output validated by an ajv validator **compiled from the committed schema** — no hand-written copy that can drift |
| **Multi-turn booking collect** | "I want a haircut" → "what day and time?" → merged into a complete request |
| **Deterministic FAQ** | Price / hours / services / address answered from config, never from the model |
| **Lead capture** | Non-booking interest written to Postgres (`salon.leads`) with channel + message |
| **Human handoff, 5 distinct classes** | guard-trip (transient) · infrastructure down (an error flag + owner alert; 503 only before the message is claimed) · genuine handoff (writes state) · clarify (first uncertain turn, no lock) · extraction-transient (our schema broke, owner alerted, no lock) — never merged |
| **Visible failures** | Distinct machine-side error flags, never dressed as a normal reply — e.g. `invalid_payload` · `state_unavailable` · `llm_unavailable` · `lead_unavailable` · `calendar_unavailable` |
| **Booking without double-booking** | Calendar first, then re-read the slot; on a lost race the bot withdraws ITS OWN event and hands off, and only a won slot is mirrored to Postgres. A message delivered twice is answered once: `Check Processed` CLAIMS the message id at the start of the turn on a UNIQUE column, so two deliveries cannot both claim it (claim-first; CRT 1a closed in 7-2). The cost is at-most-once — a run that dies after its claim is not retried. See [booking-integrity](.claude/rules/booking-integrity.md) for that and the booking race it does not close |
| **Cancel · reschedule · reminders** | Bot-automated, identity-bound to the channel's `sender_key`. Reminders are proven in dry-run; live WhatsApp template delivery needs the client's own WhatsApp Business number |
| **Owner dashboard** | Read-only panels + the handoff queue + one write (release a handoff lock, through a protected n8n path). Runs on the build server behind Cloudflare Access and reads Postgres as a SELECT-only role. It runs as a systemd user unit (`ops/systemd/salon-dashboard.service`) that restarts it on a crash (measured, 7-F1); its start at boot is shown by configuration, not by a reboot |
| **Spend brakes before the LLM** | Kill-switch, max-turns and a monthly LLM spend cap run *before* any paid call — a tripped guard costs nothing. The cap fails OPEN if the spend meter cannot be read (the turn runs, and a `spend_meter_unavailable` alert goes to the owner) |
| **Embeddable widget, one script tag** | A single self-contained IIFE (well under 20 kB; `npm run build -w @salon/snippet --prefix web` prints the current size — no byte count is pinned in prose here, because one went stale inside a single round) that mounts a booking chat inside a Shadow DOM on someone else's site. Isolation measured in both directions against a deliberately hostile host page — see the case study ([docs/CASE-STUDY.md](docs/CASE-STUDY.md) §9), including what it knowingly does not do |

## Not built yet 🔜

A **real second deployment** (Phase 8 proves the config-only render offline, on a mock client) · a **public deploy of the demo site** (there is no Vercel project; the
site runs locally against the live endpoint). *(`docs/CASE-STUDY.md` and `docs/RUNBOOK.md` stood here until 7-3, 2026-10-27; both are written now.)*

## Not yet — deferred to v2 (ruled 2026-10-24)

Known, named, and deliberately left out of this release. Only one of them can make the bot do something wrong
around a booking: the reminder row, a narrow window, named there. The other named items that would have were sent to
Phase 7's fix checkpoint instead.

| Item | Why it waits |
|---|---|
| **F5** — the deploy-separation guard checks import *spelling*, not reachability | a guard that can miss, not a present leak: Codex found no dashboard-reaching import in the public packages |
| **F6** — the hardlink identity check is a substring match | it can over-report (a false positive), never miss a leak |
| **F9** — the client-import gate does not enumerate `.mts` / `.cts` | no such files exist today; a coverage gap for a future refactor |
| **F10** — the dashboard's runtime browser guard is a DOM-presence heuristic | the build-time server/client boundary is the real control; the runtime check is a diagnostic |
| **F11** — the database schema accepts an empty id, an infinite timestamp and a `NaN` spend, which the dashboard panels would misread | no writer produces them today; tightening needs a migration file and an operator apply |
| **F13** — a capped appointment window can say "Nothing booked ahead" | inherited 1:1 from the Airtable dashboard; it needs more than a hundred cancellations inside the window to show |
| **Two dead config keys: `instagram`, `business.locale`** (K-2) | they drive nothing — there is no Instagram adapter, and customer-facing dates use the n8n runtime's default locale — so they cause no wrong behaviour. **But the config is not fully config-driven while they exist** |
| **The `handoffShown` twin** in `web/snippet` | the snippet and the site each record "lock line shown" at their own call site; deleting that line from one caller leaves the parity suite green — a test blind spot, not a runtime defect |
| **Reschedule reject symmetry (W64/W65)** | a closed-day or busy reschedule offers no working hours and no alternative, while the same rejection in booking does — inconsistent help, not a wrong action |
| **Rebooking a slot you just cancelled** — a customer who cancels and then books the exact same slot and service is handed to a human instead of booked | Google keeps the cancelled event's deterministic id reserved, and the reconcile step correctly refuses a cancelled event. The fix changes the event-id scheme or the reconcile branch, and needs a real calendar write to prove; the customer is never double-booked, only passed to the owner (ruled v2, 2026-10-25) |
| **A reminder for an appointment cancelled while the database mirror was failing** | if the cancel reached Google Calendar but the database row could not be updated, the hourly reminder job can still remind that customer. Closing it means Reminders checks the calendar before sending, which needs a new Google credential in that workflow, so it is not the small change it first looked like (ruled v2, 2026-10-25) |
| **The reschedule orphan alert does not say which old slot to clean** — when moving an appointment cannot remove the old calendar event, the customer is told "moved" (true: the new booking exists) and the owner gets an alert, but the alert does not name the old date, time and service | the fix is written and tested offline; it changes the Main workflow, and Main is not edited before this release (ruled v2, 2026-10-25) |
| **A second owner-alert channel** | owner alerts have one channel (Telegram); if it is down, failures are visible only in the n8n execution log |
| **The older v2 / LATER bucket** (unchanged since 2026-09-17): the idempotent replay's stored reply · `messageTemplates` required keys · the transcript lost on navigation · font subsetting · a `Customers` table · BULGU-4 · R2 · the W57/W58/W60 text mismatch | they improve the product but do not change whether it can be sold (PHASE-7-PLAN → Open items) |


**7-2 CONVERGE items deferred (ruled 2026-10-26, 7-2 R4).** Three were fixed instead (the scanner's `++` lines, the n8n encryption key rule, the postgres URL rule); the fourth, a hook refusal of `--no-verify`, was dropped by ruling (see below); these wait:

| Item | Why it waits |
|---|---|
| deploy tool: a snapshot's age is not checked | snapshots are deleted once an edit closes (`remote-operator.md`), and any snapshot must still pass the webhook invariants before a rollback |
| deploy tool: the Turnstile-window helper reads its spec from any path (D6c review) | its one caller passes `db/copies/main.json`; `workflow-step.py` requires `db/copies/` for every live write |
| deploy tool: the Turnstile window's holder check has no fallback for a listing without nodes (D6c review) | such a listing gives 0 holders, which is red, never a pass |
| deploy tool: a snapshot directory inside another git work tree is accepted | snapshots live in the session scratchpad by procedure; only this repo is refused, which is the leak that matters |
| deploy tool: the helper's `api` raises on an empty curl output | a traceback still stops the run; every next step reads the copy's state before writing |
| deploy tool: `activate` does not re-check the Turnstile literal | `put` checks the literal on the export and in its live read-back before any activate |
| deploy tool: spec and WORKFLOWS are read from the working tree | `check-all` and the pre-push audit run on a clean tree before every live step |
| deploy tool: nodes sharing a name are invisible to name-keyed comparisons | no committed export has a repeated node name (counted at 7-2 R4) |
| deploy tool: put's read-back re-verifies only the trigger's webhookId | only the trigger's id routes inbound traffic; the Telegram nodes' ids are kept by name |
| deploy tool: `settings` does not enforce running after the probes | the runbook orders it last, and the check after it is a body probe that counts no executions |
| deploy tool: pre-snapshot parity cannot see an IF/Switch condition's option fields | no gate decision depends on them today (R2b) |
| secret scan: an agent could commit a secret together with its own exception line | the exception file is a committed, reviewed file, and every push is audited by `security-auditor` first |
| secret scan: UTF-16 content and a key in a file name are not rules | no UTF-16 file in the repo; file names are read in the pre-push audit |
| secret scan: replace refs can hide a pushed object | no replace ref exists here (counted at R4); `--no-replace-objects` was measured to work |
| secret scan: C-quoted path names skip the JSON header-pair check | no tracked path needs C-quoting (counted at R4) |
| secret scan: `SECRET_SCAN_API=3` also matches `=30`; `--remotes=<name>` trusts that namespace | an internal marker; one remote |
| secret scan: fingerprint corner cases (a non-UTF-8 path, a path with a space, three shown per rule, a `--no-ff` merge of an old branch) | each fails strict: the hit stays a hit |
| secret scan: a hard link from an installed copy, a symlinked hooks directory, another worktree's hooksPath, the CC hook's ignore file | the installer writes fresh files from HEAD; one worktree, no symlinked hook (counted at R4); an absent ignore file means no exceptions |
| secret scan: labels print the file path unmasked; a second secret on a hit line shows as context | paths are repository paths, public already; the shown line redacts every 12+ character token, and the line is blocked either way |
| secret scan: manual mode resolves paths against the cwd; a long placeholder prefix now blocks | run from the repo root by habit; the placeholder case fails safe |
| masking: NFKC folds some symbols into letters, non-`Nd` digits are not digits, a 7–8 digit number shows four digits | data minimisation for the owner's own screen, not a security boundary; the golden table covers real phone forms |
| masking: `maskName`'s fallback keeps runs under seven digits whole; a lone `\r`, NEL and U+2028 are not line breaks; test-hygiene notes | below the seven-digit rule by design, or rare input on the owner's screen |
| Main: a verify read with NO `items` key counts as an empty list | a ruled carve-out (R2); reopened only if Calendar is seen omitting the key |
| secret scan: the n8n-key rule misses a human-chosen passphrase with dots or spaces; the postgres rule misses `?password=` or a `/` in the password, and blocks placeholder passwords such as `user:password@` | generated keys and URL-embedded passwords are caught; a false block is visible and a committed line can be excepted by fingerprint |
| secret scan: the git pre-push gate can be bypassed by `--no-verify` (or a core.hooksPath override); guarded by habit, not by code | ruled 7-2 R4: a command-line check was built in three versions and each later one let through forms an earlier one caught; the habit is written in `remote-operator.md`, and every push is audited by `security-auditor` first |
| secret scan: busybox awk ends a working-tree line at a NUL byte | manual mode only — the gate reads committed patches in its Python engine; this machine's awk handles NUL (measured by the R4 review) |
| secret scan: the PLACEHOLDER strip is quadratic on a very long run of key characters | it fails closed (a slow scan blocks the push, never passes it); no such line in the repo |
| Main: node names still say "Airtable" | a node rename is a Main edit; it rides the next one (D6c's Main put renames the workflow only) |
| Main: D-c — an alert can run ahead of the reply on a few paths and delay it | bounded and documented (FLOW-DIAGRAM); restoring it is a Main edit |

**The final security pass: what stays open (7-4 B, ruled 2026-10-28; [PHASE-7-PLAN §4j](docs/PHASE-7-PLAN.md)).** Done
in the pass: the Cloudflare API token replaced by a read-only one that expires (its scopes and the old token's deletion
measured by Cowork; its expiry by the build); the stored Owner Actions executions
deleted (they held an Access token and a cookie); the archived Main original deleted. The rest is either v2 or
**deferred by the owner, recorded** — an accepted risk until the system is complete, not a closed item:

| Item | Status | What bounds it meanwhile |
|---|---|---|
| The leaked `/api` and owner-path Access service tokens, and the n8n API key | deferred by the owner, recorded | the copies are on this machine (transcripts, backups), not public; `/api` needs the service token and the API key, the owner path needs a signed request as well; one later rotation voids every copy at once |
| Revoking the Access sessions; a 24 h dashboard session | deferred by the owner, recorded | the stored executions that held a session token are deleted |
| The Airtable token and base | deferred by the owner, recorded | no workflow and no n8n credential reaches it since D6c; the base is kept until its export (MIGRATION-PLAN §7, Gate 1) |
| Deny rules for every secret-file copy; the tunnel credential in a root-only file; a pinned backup script; an off-server backup target | deferred by the owner, recorded | the secret files are mode 0600 and outside git; the nightly dump is restored and compared before it counts, but it lives on the same server |
| `salon_ro` reads every column; the dashboard's write check is cached; the dashboard logs and shows raw driver errors | v2 | the database role is read-only and the dashboard sits behind Access |
| The infra owner alerts take `sender`/`channel`/`stage` from the error item; a stale line in the intent prompt (reschedule "routed to a human") | v2 | both need a Main edit; with the stale line the model still classifies `reschedule` (G11, 7-4 A), and routing is the workflow's |

**What the regression covers on Postgres, stated (ruled 2026-10-25):** the full suite last ran on the Main copy's test path (D4b, 28/28; the cutover diff proves only the path differs); the production path was exercised by the routing smoke (A1), the dashboard write path (A2, 13/13) and the 7-1 window (a truly simultaneous race pair and a DST booking) — live measurements recorded in PHASE-7-PLAN, their raw output not committed; the seeded ⚙ scenarios were not re-run on Postgres — their paths are covered by D4b G1–G3 and the M7 error drills.

**Not tested end to end: the WhatsApp lane (K-5).** The regression drives the widget lane only; Zernio's inbound
webhook is deliberately closed for spend safety, so no current test crosses the WhatsApp adapter boundary. It was
proven live once in Phase 4, before the store moved. "Regression green" does not mean "the WhatsApp path works".

---

## Engineering decisions worth reading

**Deterministic before AI.** A model is used only where a rule genuinely cannot decide. Asking an LLM
"what does a haircut cost?" is slower, costlier and less reliable than reading one config field.

**The schema is the single source of truth.** The validator inside the flow is *generated* from
`schemas/intent.schema.json` by a script, with a drift check. Two hand-maintained copies of the same
contract always diverge; a generated one cannot.

**Never trust a 200.** Structured output is only guaranteed when the model stops normally, so
`stop_reason` is checked first, enum casing is normalized, and any unexpected shape becomes a handoff
instead of a crash.

**An outage must not look like a handoff.** If the LLM or the database is down the customer still gets a
polite message, but the machine-side response is distinct (an error flag, and an owner alert) so the owner
knows. Once the message is claimed the status is 200, because a 5xx would only make the channel retry a message that
is already claimed; before the claim it is 503. An outage that looks normal is an outage nobody fixes.

**Availability has one source of truth.** Google Calendar owns free/busy; Postgres mirrors it. Writes go
to the calendar first. Two sources of truth mean double bookings — and Postgres's transactions do not change
that, because the calendar write is an HTTP call outside them.

**Safety over liveness: a truly simultaneous pair withdraws both.** Each writer books, re-reads and yields if it sees
another event, so two requests at the same moment can both yield: no double booking, no booking, a human follows up.

**Config / code / secret are separate — shown offline, with its bounds.** The engine's config sits inside its nodes
(three inline copies, plus the owner's chat id and the Turnstile secret), so a new client used to mean editing them.
Since Phase 8's first round, **a new client = a config file + secret inputs → `scripts/render-client.py` → import into
its own n8n; no node edited by hand** (with both secret inputs given) — shown offline on a second, fictional client (`tests/unit/render-client.test.py`: only the ten measured slots differ from the demo's workflows; a synthetic client whose every config value differs from the demo's shows every key of the three config literals fed from the client's own config (the few-shot from its first service, the chat id and Turnstile secret from its secret input); and no demo-client string of five or more characters reaches the new client outside six allowlisted code comments and fallbacks;
`tests/unit/render-client-mutants.py`, 17 mutants red), with these bounds in the same breath:
EUR only (`priceEUR`, and `€` written in two nodes), customer text in English, two config keys that drive nothing (`instagram`, `business.locale`), the new instance's credentials linked by hand, and not yet shown on a real second deployment (`docs/PHASE-8-PLAN.md`; its independent audit, CRT #14, is the next round).

---

## Case study

**[docs/CASE-STUDY.md](docs/CASE-STUDY.md)** — the problem, the approach, the architecture (the LLM as a translator),
the AI-versus-deterministic split, the Airtable → Postgres migration, the independent Codex audit and how it was
triaged, what I learned, and what "one swap to real" does not yet mean. The embeddable widget's case study (Phase 6b)
is its §9.

---

## Repo map

| Path | What |
|---|---|
| [`n8n/`](n8n/) | the engine — **sanitized** workflow exports only: one `workflow.<key>.sanitized.json` per live Postgres workflow (five), listed with its id in `scripts/check-exports-parity.sh`; the Airtable originals' exports were removed at D6c and stay in git history |
| [`db/`](db/) | `schema/` — the Postgres DDL, roles and the large-object revoke · `ops/` — the nightly backup and its restore check |
| [`schemas/`](schemas/) | JSON Schemas — the intent contract and the client config contract |
| [`prompts/`](prompts/) | versioned LLM prompts (the canonical system prompt) |
| [`scripts/`](scripts/) | validator compiler + drift check · the SQL-parameter gate · workflow deploy / parity guards · repo map generator |
| [`config/`](config/) | per-client `client.config.json` (mock example committed) |
| [`docs/`](docs/) | architecture decisions · data model · live roadmap · repo map |
| [`design/`](design/) | Phase-1 mockups + flow diagram |
| [`tests/`](tests/) | golden-set intents · jailbreak / injection cases |
| [`web/`](web/) | frontend surfaces — `site/` (Next.js demo), `snippet/` (the embeddable widget), `shared/` (one transport, both front ends), `dashboard/` (the owner dashboard) |
| [`.claude/`](.claude/) | the rules this repo is actually built under |

**Stack** — n8n (self-hosted) · Anthropic Claude Haiku 4.5 · PostgreSQL (self-hosted, since 2026-10-24;
Airtable retired at D6c, 2026-10-27) · Google Calendar · Zernio (WhatsApp Business API) · Next.js (the site: no
public deploy yet · the dashboard: its own server behind Cloudflare Access).

---

## Security

This repository is **public**, so it is built as if it were.

- No secrets, no customer PII in git — real values live in n8n Credentials. Only sanitized n8n exports
  (`n8n/*.sanitized.json`) are committed; credential, base and calendar ids are placeholders.
- Every push runs a secret/PII scan.
- The n8n editor is never exposed to the internet; only webhook endpoints are.
- The owner dashboard shows PII, so it sits behind Cloudflare Access: measured 2026-10-24, a request without a
  session is redirected to the Access login, and the policy admits one named email
  ([MIGRATION-PLAN §3t, K-6](docs/MIGRATION-PLAN.md)). CRT #9 (dashboard auth) is audited and its findings
  addressed (`[x]`, 7-2) in [MASTER-BRIEF §9](MASTER-BRIEF.md).
- The store's own boundary: n8n's database role has DML on the five tables plus their sequences and two helper functions (default privileges extend that to tables the owner adds later), the dashboard's role
  has SELECT only ([`db/schema/002_roles.sql`](db/schema/002_roles.sql)), and every workflow query is parameterised
  (`scripts/check-sql-params.py`). The database port is not reachable from outside *(operator statement,
  MIGRATION-PLAN §3t, A9)*.
- **A finding from this build, recorded honestly:** the LLM webhook was discovered publicly reachable
  with no rate limit or spend cap. It was taken offline immediately and re-publishing is gated behind
  the Phase-5 brakes. Documented in [`docs/ARCHITECTURE-DECISIONS.md`](docs/ARCHITECTURE-DECISIONS.md).
- **The date guard, and what it does NOT cover (honest limit, 2026-09-09).** The engine — not the model —
  resolves the booking day: the LLM's date is a disagreement signal, never a value. That closed a real
  wrong-day booking (the model answered a Saturday for "friday morning" at `confidence=0.92`, reproduced
  live again during the final drill and overridden). **Four things it still does not do, each with a
  reproduction in [`docs/ROADMAP.md`](docs/ROADMAP.md):** a week shift the sentence carries but the model's
  wording does not is NOT detected (the confirmation step showing weekday + full date is the only backstop);
  a day named in a form outside the recognised vocabulary ("the 20th", "next weekend", non-English) can still
  let a previously stored date stand; the separator fold covers the dash and slash families, not every
  Unicode look-alike; and on a confirmation turn a change request that cannot be resolved writes the date the
  customer was shown. These are demo-grade limits on a template with **zero real customers** — named here
  rather than left for a reader to discover.
- **The extraction-retry path has never been TRIGGERED in production (honest limit).** Precisely: in the live
  drill `Extraction Transient?` executed on every turn and took its FALSE branch every time, while
  `Repeat Extraction Failure?` and `Build Extraction-Retry State` never executed at all. So one node has run
  and never fired, and two have never run. **That per-turn execution count is itself UNVERIFIED here:** its
  only basis is the previous round's drill write-up — the execution log is not committed, so a reader cannot
  re-derive it from this repo. *(An earlier wording said "three safety nodes have never run",
  which the drill record contradicts — "the node never executed" and "its real trigger was never exercised"
  are different claims and only the second is true of all three.)* The trigger — the model omitting a required
  schema KEY — cannot be induced on demand against a live model, so the path has unit and mutation evidence
  only. The drill proved the surrounding behaviour did not regress, nothing more.
- **Cancel identity (honest limit):** a customer can only cancel their OWN booking — cancel looks up
  appointments by the channel-authenticated `sender_key`, never a customer-supplied booking id, so IDOR
  is structurally impossible. On the widget, though, `sender_key` derives from a **client-supplied
  `sessionId`** — session-token strength, not a verified identity. Endpoint rate-limiting and Turnstile
  (Phase 5) raise the cost of abusing it; they do not make the session an identity. Recorded in
  `docs/ARCHITECTURE-DECISIONS.md` §5.

---

## From demo to real

Everything runs today on mock config and a test endpoint. Going live for a client means their real WhatsApp
number, their calendar and **their own Postgres** — under Model 1 (one isolated deployment per client) that is a
Postgres service, its secrets and its backup step per client ([MIGRATION-PLAN §8](docs/MIGRATION-PLAN.md)). The
engine's code does not change; whether *only config* changes is not yet demonstrated (see "Config / code / secret"
above). The operator's runbook — provisioning a client's Postgres, the daily checks, the backup, deploys — is [`docs/RUNBOOK.md`](docs/RUNBOOK.md); its provisioning section has not yet been run as one procedure for a new client.

**Why Postgres and not Airtable — kept here because it is the reason.** The free Airtable plan could not serve a
single real client: 1,000 API calls per month per workspace, shared between the bot and the dashboard, plus a hard
5 requests/second per base (measured 2026-09-12). On 2026-10-06 the quota ran out with no customer traffic at all,
and the bot had no data layer for almost twelve days ([OPS-5](docs/OPERATIONAL-INCIDENTS.md)). The store moved to
self-hosted Postgres (ruling 2026-10-19; cut over and accepted 2026-10-24,
[MIGRATION-PLAN §3t](docs/MIGRATION-PLAN.md)). **Airtable was retired at D6c (2026-10-27)**: the original workflows
are archived and n8n's Airtable credential is deleted, so nothing can reach it; revoking its token and deleting the base
are deferred by the owner, recorded (the final security pass, 7-4 B). What Postgres costs instead: a
database to run, back up and restore for every client. The nightly backup restores each dump into a throwaway
container and compares every table before the dump counts ([`db/ops/pg-backup.sh`](db/ops/pg-backup.sh)).

---

## Documentation

**[MASTER-BRIEF.md](MASTER-BRIEF.md)** — the current architecture ·
**[docs/ROADMAP.md](docs/ROADMAP.md)** — live phase status ·
**[docs/ARCHITECTURE-DECISIONS.md](docs/ARCHITECTURE-DECISIONS.md)** — every decision and why it changed ·
**[docs/DATA-MODEL.md](docs/DATA-MODEL.md)** — the Postgres data model ·
**[docs/MIGRATION-PLAN.md](docs/MIGRATION-PLAN.md)** — how the store moved from Airtable to Postgres, step by step ·
**[docs/CASE-STUDY.md](docs/CASE-STUDY.md)** — the case study ·
**[docs/RUNBOOK.md](docs/RUNBOOK.md)** — operating a deployment.

MIT licensed. Built by [Neeidy](https://github.com/Neeidy) as a portfolio project in AI automation.
