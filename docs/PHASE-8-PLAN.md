# Phase 8 — Template-ize · PLAN

> **Status: ✅ CLOSED 2026-10-28 after R2b** (CRT #14: a pre-fix Codex audit — no HIGH, four MEDIUM, two LOW — and
> internal verification of the fixes; five fixed with a test and a killing mutant, M1 a recorded bound by the owner's
> ruling — below). *Was:* **APPROVED by Yigitcan (plan-gate), 2026-10-28**, presented in chat in the full
> format, rulings D1–D4 as proposed. Derived against `0c97044`. Offline only: no live write, no n8n call. **R1 stopped at its start (below):** a
> slot outside the measured set turned up; ruled the same day: it is the tenth slot (below).
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
| `Build Booked State`, `Build Mirror-Failed State`, `Build Dry-Run Booked State`, `Build Cancelled State` | the demo's template text as the fallback after `cfg.messageTemplates.… \|\|` | used only when the config lacks the key (or, as the review found, holds it empty); the render refuses both |

**Safety, measured in the code:** an id that is not in `config.services` is nulled by `Merge Slots`, refused by
`Slot Gate`'s allow-list, and would make `Build Event Request` throw — so B cannot book a wrong service; at worst the
bot asks for the service once more. It is a quality and template-claim defect, not a booking-correctness one.

**R1 waits for a ruling** on how the plan treats it (the brief's STOP condition: "a slot outside the measured set turns
up — report it, extend the plan only by ruling").

**Ruled (Yigitcan, 2026-10-28): option (a).** `Build LLM Request`'s few-shot examples become the **tenth slot**: the two
`"serviceId":"haircut"` and the two "a haircut" phrases are rendered from the client's FIRST service id and name, at fixed
anchors with an expected count — a count mismatch makes the render refuse; render(example) stays byte-identical. The
comments and the `messageTemplates` fallback strings are **not** slots: each goes onto the A-leak scan's allowlist by
node + text + reason, one entry per hit, never a pattern. R1 continues on that basis.

**Read with the slots, stated so it is not mistaken for a new one:** the 52 credential references in the exports
(`REPLACE_WITH_*_CREDENTIAL_ID`) are per-instance links, not per-client values; the render leaves them as placeholders
and they are linked in the new instance — the plan's "credentials are per instance" and the acceptance criteria's
"credential setup" bound.

## R1 — built offline (2026-10-28)

- **`scripts/render-client.py`** fills the ten slots. The three literals are read WITHOUT executing them (bare keys
  quoted, line comments dropped, then JSON — the test compares that reading with node's own evaluation of each
  committed literal) and re-written in the committed literal's style (bare keys), because the repo's own tools read
  that style: the deploy tool's `turnstile: { enabled: … }` pattern and the parity script's `timezone: "…"` /
  `ownerAlert: { … }` patterns find nothing in JSON's quoted keys — and a parity check that finds nothing on both sides
  passes. The comments inside the Purge literal are not carried into a rendered client (its header comments are).
- **`tests/unit/render-client.test.py`** (in `check-all`): proofs 1–6 and the drill matrix, 63 cases at R1's push (45 in
  the first cut; the review rounds below added 18; R2 brought it to 75). The A-leak scan
  takes every string of the demo client (5+ characters, lists included) that example-b does not hold, minus `site.*`
  (no workflow literal carries the site's copy — asserted); its allowlist has six entries, one per hit (two comments,
  four template fallbacks), and a stale entry is red; positive control: every probe is found in render(example);
  negative control: an A literal planted outside the slots is caught. Proof 5 includes a tamper control: a timezone
  split between render(B)'s Main and Reminders turns `check-cancel-validation-parity` red, so it reads the rendered form.
- **Mutants — `tests/unit/render-client-mutants.py`, 17 of 17 red at R1's push (35 of 35 after R2b), each by its own case** (not in `check-all`: it
  re-runs the test per mutant). *(A mutant of the repository check writes into the repo, as such a mutant would; in
  the first runs its directory — the mock client's render, placeholders only, gitignored — was left and deleted by its
  literal path, twice, and it contaminated the later mutants' runs. Every case that targets the repo now removes exactly
  what it created and fails, and the runner stops if anything is left.)*
- **The review round (code-reviewer + security-auditor, offline), all fixed before the commit:**
  - **HIGH — proof 2 measured nothing where example-b equals the demo** (45 of Main's 65 keys, all 3 of Purge's, the
    calendar id among them): three targeted mutants (the calendar id and Zernio account from the demo literal, the
    Purge literal from the demo, the bot / ownerAlert policy from the demo) passed the first test. Closed by a
    synthetic third client whose every leaf differs from the demo's: each literal must carry its value at every key
    and the demo's at none. Those three mutants, and an abspath-for-realpath one, are now in the runner and red.
  - **The A-leak scan's scope, stated:** strings of 5+ characters that example-b does not hold, in node parameters.
    Numbers and shared values INSIDE the three literals are covered by the synthetic client, not by the scan; a demo
    number hard-coded outside the slots would be seen by neither.
  - **List elements were not checked** (a service without `priceEUR`, or with it as a string, passed) — now each
    element must carry the committed first element's keys and kinds. **An empty template** fell through to the
    code's demo-text fallback — refused now, so the allowlist's "unreachable" holds. **NaN / Infinity** — refused.
    **Trailing newlines** passed the shape checks (`$` matches before `\n`) — `fullmatch` now.
  - **The output directory:** only a NEW directory, created by `mkdir`, re-checked after creation (realpath outside the
    repo, and the same inode as the directory opened), files created by directory fd without following links — a link
    swapped in after the first check can no longer steer the output into the repo (a test swaps the parent for a link
    into a stand-in repository after the check; a mutant without the re-check writes there). Cases added: a link into the repo,
    `..` into the repo, an existing (even empty) directory.
  - **The secrets file:** opened without following links and checked on the open descriptor; refused inside the repo;
    an unknown key is counted, not named (a secret pasted as a key would otherwise be printed).
  - **Docs:** the claim narrowed to what the tests show (above); RUNBOOK §0b says a left-out secret key means a hand
    edit in the new instance, and where the client config may live (another name under `config/` is not ignored); the
    test copies only the five exports (it used to copy the gitignored live snapshots into its temp directory too);
    the credential count corrected to 52.
  - **Recorded, not changed:** the article before a service name in the few-shot is approximate (`a`/`an` by the first
    letter) — grammar only.
  - **The re-review (both reviewers, offline) found three LOW side effects of the fixes, all closed:** a day the demo
    leaves empty (`sun: []`) let any value through — now checked against a filled sibling's shape; a refusal after
    `mkdir` could leave the empty directory — removed now when it is ours, and every write error is a refusal; a
    FIFO as the secrets path blocked the open — opened non-blocking now. Each has a case and a mutant. **And a defect in
    the test itself, found by reading why a mutant died:** the FIFO case ran the script from its own location, so every
    mutant (a copy in a temp dir, whose ROOT is that temp dir) failed it — mutants could be "killed" by it without their
    own case going red. The child now loads the script with ROOT pinned to the repo, and the runner prints how many
    cases each mutant turned red. With that fixed, the abspath mutant SURVIVED: the write's re-check caught what the
    pre-check missed, so the pre-check itself was untested — the repo cases now require the pre-check's refusal.
- **Docs:** README, `docs/CASE-STUDY.md` §1 and §8, `.claude/rules/honesty-demos.md`, `docs/RUNBOOK.md` §0b and
  `MASTER-BRIEF.md` carry the honest sentence with its bounds in the same sentence; CRT #14 is in MASTER-BRIEF §9
  (`[ ]` until Codex) and ARCHITECTURE-DECISIONS §7, the rulings in its decision log. README's status note, which still
  said Phase 7 was in progress and Phase 8 not started, is corrected.
- ~~Next: R2 — Codex audits CRT #14.~~ → done, below.

## R2 — Codex CRT #14, and the fixes (2026-10-28)

- **The run:** the prompt committed and pushed first (`docs/codex/phase-8/prompt.md`, pin `35df5cc`), one container run
  in the 7-2 R2 harness, the raw answer committed verbatim (`docs/codex/phase-8/crt14.md`), the containment record in
  `docs/codex/phase-8/containment.md`. *Declared there: the first attempt's mount check failed on its OWN filter — it
  selected mounts by filesystem type and dropped tmpfs, where the scratchpad and therefore `/audit` and `/codexhome`
  live; Codex never started. Corrected to select by mount point and shown able to fail (one extra mount → 97) and pass
  before the second attempt, whose check passed.*
- **Codex's findings (no HIGH) and what each became.** Codex audited the code at the pin, BEFORE these fixes; the
  fixes were verified by the internal reviews (R2b below), not re-audited by Codex.
  - **M1 — a catalogue assumption outside the slots:** `Build LLM Request` has a fixed example saying hair colouring
    is NOT offered; a client whose services include it gets a self-contradicting prompt. **Not made a slot** (the slot
    set is the ruled ten). R2 first answered it with a word guard (refuse a service whose id or name matched
    `colou?r`); the reviews showed it both missed (Balayage, Highlights, Hair Dye …) and refused the unrelated (Gel
    Colour …), so the owner ruled it a **recorded bound** (R2b): the guard is removed, the bound is written beside the
    others, and the example is watched, not rewritten.
  - **M2 — two template keys a workflow reads were dropped:** `Build Cancel-Aborted State` reads
    `messageTemplates.cancelRetry` and `dryRunNoChange`, which Main's literal does not hold, so a client's text for
    them never arrived (the node's generic fallback answered). They are now **optional**: carried when the config
    gives them as non-empty text, refused when given empty or null, the code's fallback when absent. The drift check
    behind it is the R2b one: every config path a workflow reads, in every section, is held by its literal or is on that
    optional list. RUNBOOK §0b corrected — it said every read key is refused when missing.
  - **M3 — running the script through a link moved "the repository":** `ROOT` came from the link's location, so the
    inside-the-repo refusal checked the wrong directory. `ROOT` now comes from the real path; the case runs a link to a
    copy of the script that sits in a stand-in repository. **Bound, stated in the script and RUNBOOK:** a COPY of the
    script elsewhere, or a hard link to it, still guards the directory it sits in — run it from the repository.
  - **M4 — a number that overflows (`1e999`) parsed to infinity** without any NaN/Infinity token and reached the
    literal as `Infinity` (a spend cap that never trips). Every number is now checked finite AND, for an integer,
    inside the JS safe-integer range (R2b: `10**400` slipped past the first, float-only check), by name.
  - **L5 — list elements kept fields the workflows never read:** an element was checked against the committed shape and
    then copied whole; it is now projected onto the committed element's keys.
  - **L6 — the "never printed" case read stdout only, and no case covered the owner check:** the test now captures
    stderr too, and runs the owner check against another uid (without root).
  - **Also from the audit's notes:** a directory as the secrets path raised instead of refusing — the checks now run on
    the open descriptor before it becomes a file object; a secrets file with a second hard link (a second name could
    sit inside the repo) is refused. Recorded, not changed: the mode check takes "no group/other access" (0400 passes).
- **No HIGH, so no second Codex run** (the brief: a re-run only after a HIGH's fix).

## R2b — the internal reviews of the R2 fixes, and the last round (2026-10-28)

- **Why there was a round after R2:** `code-reviewer` showed three R2 fixes closing the instance Codex showed and not
  its class — M4 (`10**400`, an integer, went past the float-only check and still rendered `Infinity`), M1 (the word
  guard above) and M2 (the drift test read `json.dumps` text with two spellings, and missed `?.`, brackets,
  destructuring, a line-split chain and every section but `messageTemplates`) — plus a regression (`"services": 5`
  raised a traceback instead of refusing), a `null` optional key accepted, a second "not offered" example unwatched,
  and four surviving mutants. `security-auditor` passed security and failed the content (the colour bound over-claimed,
  the Codex sentence without "pre-fix", the attempt number, the containment record's gaps, RUNBOOK §0b). The round
  STOPPED under "the same defect twice"; the local commit was not pushed, and its content is rewritten here.
- **The owner's ruling (Yigitcan, 2026-10-28):** M1 a recorded bound; M4, M2, the regression, `null`, the second
  example, the four mutants and the docs fixed; no second Codex run; **convergence** — the reviews judge only this
  round's diff, and the same class again is recorded as a bound with its reason, not another round.
- **What R2b did:** the word guard removed and the bound written on every surface that carries the bounds · numbers
  finite and inside ±(2^53 − 1), in lists too, and the largest safe integer shown to come back exact from JS ·
  `services` not a list refused by name · an optional key given `null` refused · the example's `(not in services)`
  marker watched once, so a second such example is refused (one written without that marker is not seen — stated) ·
  the drift scan rewritten on the RAW parameter strings: every chain from the Load Config item or `$json`, through
  aliases, one-level destructuring, groupings and every accessor spelling, checked against the workflow's own literal
  in every section, with sixteen synthetic spellings as its negative controls and, on the real exports, `OPTIONAL`
  emptied as a red control; its bounds are stated in the test (a computed key ends a chain; a config object passed into
  a function is not followed; a grouping stands for its deepest config chain) · the test turns an exception in the
  script into a red case, so a mutant that crashes cannot pass as "no red line" · the containment record completed
  and its runner committed.
- **After R2b:** the render test **103** cases green; the mutant runner **35 of 35** red, each by its own case (the four
  that survived R2 replaced by mutants aimed at the gaps they showed, one for each R2b check, and one from the review).
- **The review of R2b's diff (`code-reviewer`, only this round's diff, per the convergence ruling):** no HIGH; it
  re-ran the test (102 then) and the mutants (34/34) itself. One NEW-class finding, fixed: the "±" of the safe-integer
  check was untested (dropping `abs` survived) — a `-2**53` case and its mutant were added, after the review (not
  re-reviewed; the behaviour itself the reviewer had already measured correct). Six findings of the SAME classes,
  **recorded as bounds, not fixed** (the ruling), each written where it applies:
  - the drift scan (M2's class; the test's comment): a declaration with several names, a grouping after a keyword
    (`return (…).k`), and an item reached other than through `$('Load Config…')` / `$json` are not followed — none
    occurs on a config read in today's exports (measured: 70 of the 80 `.config` accesses start at a recognised root,
    the other 10 are the followed `lc` alias or comments), so a NEW read written that way would pass unseen;
  - the number check (M4's class; the script's docstring): a list nested about a thousand deep ends in a recursion
    traceback before anything is written; an integer of more than 4300 digits is refused, but not by name;
  - the optional keys (M2's class; the script's docstring): a template given only spaces is taken as text, and the
    customer gets a blank reply — true of the required templates too.

## Phase 8 — closed (2026-10-28)

**A new client = a config file + secret inputs → `scripts/render-client.py` → import into its own n8n; no node edited by
hand (with both secret inputs given)** — shown OFFLINE on a fictional second client and a synthetic third; CRT #14: a pre-fix
Codex audit + internal verification of the fixes (`code-reviewer` and `security-auditor`, R2b). **The bounds, in the same breath:** EUR only (`priceEUR`, and `€` written in two nodes), customer text in English, two config keys that drive nothing (`instagram`, `business.locale`), the prompt carries a fixed example that hair colouring is not offered; a client offering it gets a contradicting prompt until a Main edit (quality only: `Merge Slots` and `Slot Gate` refuse a service id the config does not hold), the new instance's credentials linked by hand, and not yet shown on a real second deployment. Not built in this phase and named: a real
second deployment (its own n8n, Postgres and credentials), and the per-client Turnstile provisioning (moved to the
public-demo phase).
