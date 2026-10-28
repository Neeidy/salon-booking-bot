# Phase 8 — Template-ize · PLAN

> **Status: APPROVED by Yigitcan (plan-gate), 2026-10-28**, presented in chat in the full format, rulings D1–D4 as
> proposed. Derived against `0c97044`. Offline only: no live write, no n8n call. **R1 stopped at its start (below):** a
> slot outside the measured set turned up; the plan is extended only by ruling.
> **Order (ruling 2026-10-28):** Phase 8 now (offline, 2 rounds), then a **public demo** phase (ship gates 11–16, 19,
> 21, the deploy). The Phase 8 row's named item "per-client Turnstile provisioning" moved to that phase (ROADMAP).

## Goal
A second (mock) client's five workflows are produced **from its config file and its secret inputs alone** — no node
edited by hand — and this is proven offline.

## Measured preconditions (committed exports, read-only, 2026-10-28)

| What forces a node edit for a new client today | Where | Measured |
|---|---|---|
| **Three inline config copies** (CASE-STUDY §8 named one) | Main `Load Config` (65 leaf keys), `Load Config (Reminders)` (12), `Load Config (Purge)` (3) | each is an **exact subset** of `config/client.config.example.json` — 0 values differ, 0 extra keys — so all three can be produced mechanically from a config |
| **The owner's Telegram chat id, a literal** | 5 nodes: Main 1, Owner Actions 2, Purge 1, Reminders 1 | `REPLACE_WITH_…` in the exports, the real value live |
| **The Turnstile secret in a node parameter** | Main `Verify Turnstile` | a finding: a secret held in the workflow JSON, not in a credential or env (D4) |
| **Currency fixed to EUR** | `€` in `Build LLM Request` and `Answer FAQ`; the config key is named `priceEUR` | EUR only — a bound |
| **Two dead config keys** (as CASE-STUDY says) | `business.locale` read 0 times; `instagram` only inside the literal | K-2, v2 |
| Language | part of the customer text is fixed English in nodes | CASE-STUDY §3 — a bound |

Not blockers: the front ends are config-driven already (the site produced a different site from `example-b` on an
identical code-tree hash, 6a — ROADMAP; the dashboard reads `CLIENT_CONFIG_JSON`); `example-b` carries every key the
three copies project (0 missing); Code nodes can read `$env` (`OWNER_HMAC_SECRET` is read in two); credentials are per
instance; webhook paths are per deployment, which is fine under Model 1.

## Scope · NOT-build
**Scope:** a render script that fills the "slots" of the five committed exports from a client's config and secret
inputs (the 3 `Load Config` literals, the 5 Telegram `chatId`s, the Turnstile secret); tests and mutants; docs
(CASE-STUDY §8, `honesty-demos.md`, README, RUNBOOK §0); CRT #14.

**NOT-build:** multi-tenancy · a real second deployment (a second n8n, Postgres, credentials) · reading config at
runtime from env or the database · editing any production workflow (Main included) · wiring `business.locale` /
`instagram` (v2) · generalising currency or language · Phase 6c, WhatsApp, the site deploy, new features, the Loom ·
per-client Turnstile provisioning (moved to the public-demo phase).

## The mechanism (D1: render at deploy time)
The n8n counterpart of the site's `build-config.mjs`. `scripts/render-client.py --config C --out DIR`:
- rewrites the three literals from the config's projection (each workflow's key list derived from today's literal);
- fills the secret slots from a local 0600 input (D2), or leaves `REPLACE_WITH_…` when no input is given;
- refuses a config that lacks a projected key, naming it;
- writes outside the repository only (the `workflow-step` snapshot rule).

Not the env route: that needs three live edits (Main, Reminders, Purge) and a root step on the container's env; the
render route touches no production workflow and is proven offline. **The cost, stated:** the deployed node still holds
the config as a literal, and a config change still means re-render + deploy — mechanical now, not by hand.

## How the second client is proven (offline)
1. **render(example) equals the committed five exports** (canonical JSON; the three `Load Config` nodes compared by
   evaluating their literal) — the slots capture every per-client value.
2. **render(example-b) vs the committed export: the node-level difference set equals the slot set** — every other node
   byte-identical.
3. **A-leak scan:** no value distinct to client A appears anywhere in render(B) — with a positive control (the same scan
   finds those values in render(A)).
4. **Behaviour:** `Answer FAQ` and `Build LLM Request` run offline on B's config and answer with B's prices, hours and
   services, not A's.
5. **The existing guards are green on render(B)** (`check-config-schema`, `check-cancel-validation-parity`, by path env).
6. **Mutants:** a render that skips a slot, or a fixed value added outside the slots, turns 1 / 3 red.

**No live check (D3):** render(example) = committed exports and committed exports = live (the parity guards) already tie
the chain to production; importing a mock client would add nothing.

## Integrations · mock data
None external; no live write. Mock: `config/client.config.example-b.json` ("Hofgasse Barbers", fictional —
`honesty-demos.md`). Secret inputs in the tests are synthetic and generated inside the test, never on a command line.

## Critical-Review Target
**CRT #14 — client render isolation.** Criteria: silent failure (5) and a data/PII leak (3): a missed slot silently
carries client A's calendar id, chat id or address into B's workflows — B's customers written into A's calendar, A's
owner alerted. Verification: `python3 tests/unit/render-client.test.py` (proofs 1, 2, 3, 6); audited by Codex (R2).
The rendered output can carry secrets, so forcing it out of the repository is part of the same target.

## Acceptance criteria
Proofs 1–6 green, mutants red, check-all 0; Codex CRT #14 clean or its findings closed; the docs carry the honest
sentence — *"a new client = config file + secret inputs → render → import into its own n8n; no hand node edit"* — with
its bounds in the same sentence: EUR, English, the dead keys, the credential setup, not shown on a real second
deployment.

## ⚙ Drill matrix
| Scenario | Expected | MUST | MUST NOT |
|---|---|---|---|
| render(example) | equals the committed five | canonical equality | any difference |
| render(B) | only slot nodes differ | difference set = slot set | a non-slot node changed |
| A scan on render(B) | 0 hits | the scan's positive control (hits in A) | an A value in B |
| Answer FAQ with B | B's prices | B's services | A's services |
| no secret input | `REPLACE_WITH_…` stays | the placeholder | an empty string or A's value |
| `--out` inside the repo | refused (exit ≠ 0) | refusal | a file written |
| a config key missing | refused | the key's name | a silent default |

## Automation-fit
Neither `/loop` nor `/goal`: two small offline rounds.

## Rounds
R1 (offline): the render script, tests, mutants, docs; code-reviewer + security-auditor. R2: Codex CRT #14 and fixes.
**2 rounds**; +1 if Codex finds a HIGH. No live window.

## Rulings (Yigitcan, 2026-10-28)
- **D1** render at deploy time · **D2** the chat id and the Turnstile secret from the local 0600 secret input, the
  schema unchanged · **D3** no live check · **D4** the Turnstile secret living in a node parameter is a recorded finding
  → v2 or the next Main edit (knowing it lets one call siteverify, not forge a token).
- **Order:** Phase 8 now, then the public-demo phase.
- **Moved:** the Phase 8 row's named item "per-client Turnstile provisioning — required before the system is called
  done" (2026-09-06) goes to the public-demo phase (the demo needs its own production widget anyway). Recorded on both
  ROADMAP rows.

## R1 — stopped at its start (2026-10-28): a slot outside the measured set

Before writing the render script, every string value distinct to client A (in the example config, different from B's
value at the same path and absent from B's config; 19 strings) was searched for in every NON-slot node of the five
committed exports. Seven hits:

| Where | What | Reading |
|---|---|---|
| `Build LLM Request` — the prompt's few-shot examples | `"serviceId":"haircut"` twice, and the phrase "a haircut" in the example messages | **a slot outside the measured set:** client A's service id inside text sent to the model on every turn. For B (ids `skin_fade`, `classic_cut`, `beard_sculpt`, `cut_beard`) the examples teach an id B does not have |
| `Build LLM Request` — a code comment | `// "Europe/Vienna"` | a comment; the value is read from `cfg.business.timezone` |
| `Resolve Date` — a code comment | "haircut friday" in an example sentence | a comment |
| `Build Booked State`, `Build Mirror-Failed State`, `Build Dry-Run Booked State`, `Build Cancelled State` | the demo's template text as the fallback after `cfg.messageTemplates.… \|\|` | used only when the config lacks the key; the render refuses a config that lacks it |

**Safety, measured in the code:** an id that is not in `config.services` is nulled by `Merge Slots`, refused by
`Slot Gate`'s allow-list, and would make `Build Event Request` throw — so B cannot book a wrong service; at worst the
bot asks for the service once more. It is a quality and template-claim defect, not a booking-correctness one.

**R1 waits for a ruling** on how the plan treats it (the brief's STOP condition: "a slot outside the measured set turns
up — report it, extend the plan only by ruling").
