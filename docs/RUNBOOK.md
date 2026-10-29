# Runbook — operating the salon booking bot

> **Who this is for:** the operator of one deployment (Model 1: one isolated deployment per client). Every command
> runs on the server unless it says otherwise. Every automated check below is a script in this repo, so the procedure
> and the code cannot drift apart; the provisioning steps (§0) and the scheduled-run check (§1) are manual. **No host, password, token or id is written here:** hosts come from the gitignored
> `CLAUDE.local.md`, credentials stay where they already live (`.claude/rules/remote-operator.md`,
> `.claude/rules/security-secrets.md`). Created at 7-3 (2026-10-27); the plan item is PHASE-7-PLAN, 7-3.

**The environment every n8n check needs** (sourced, never printed):

```bash
set -a; . ~/.n8n-api.env; set +a                     # the n8n API env file, as scripts/check-exports-parity.sh instructs
export N8N_HOST="$(sed -n 's/^N8N_HOST=[[:space:]]*\([^[:space:]]*\).*/\1/p' CLAUDE.local.md | sed -E "s/^[\"']+//; s/[\"']+\$//")"
# the same parse scripts/check-no-host-leak.sh uses (value, then a surrounding pair of quotes stripped)
```

Exit codes. `check-exports-parity.sh`, `check-content-parity.py` and `check-active-set.py`: **0** OK · **1** a real
failure (drift, a wrong active set) · **2** NOT MEASURED (credentials missing, a read that did not complete) — a 2 is
never a pass, and `check-exports-parity.sh` turns an inner 2 into its own 1. The others have their own:
`check-live-parity.py` exits 1 for drift AND for an error; `workflow-step.py` exits 2 on a usage error and 3 when a
scratch could not be proven deleted; `turnstile-window.py` exits 2 when a precheck refused and **3 = SAFETY**.

---

## 0 · Provisioning a client's Postgres (once per deployment)

> What a new client needs under Model 1 is a Postgres service, its secrets and its backup step (MIGRATION-PLAN §8).
> The steps below are the ones this deployment went through (D2b-2, 2026-10-19; 003 in the migration's Round 3c), as
> the schema files themselves prescribe. **As one start-to-finish procedure for a NEW client they have not been run**
> (Phase 8 proves the workflows' half offline — section 0b — not this database half). Every step is the operator's:
> the compose directory and the roles file are root-owned.

1. **The service:** Postgres major 18, its image pinned by DIGEST in the compose file (MIGRATION-PLAN §3n), in the
   deployment's compose project, published on `127.0.0.1:5432` only, so n8n reaches it by service name and the
   dashboard over loopback (§3h, option A). Check: `ss -ltn` shows `127.0.0.1:5432` and no wildcard bind, and
   `bash scripts/check-listeners.sh` stays green.
2. **Two password files, both kept out of n8n's own env file** (Q14: every workflow can read n8n's environment): the
   Postgres service's env file holds only the bootstrap superuser's password; a root-only roles file holds
   `SALON_MIGRATOR_PASSWORD`, `SALON_APP_PASSWORD` and `SALON_RO_PASSWORD` and is never given to the container as an env
   file (`docker inspect` would show it). How the `salon` database itself was created is not recorded in this repo.
3. **`db/schema/001_init.sql` + `db/schema/002_roles.sql`, in ONE transaction, as the bootstrap superuser, inside the
   container, the SQL on STDIN:** first wrapped in `BEGIN … ROLLBACK` (a dry run that proves every statement,
   `CREATE ROLE` included), then in `BEGIN … COMMIT`. The root shell loads the roles file and passes the three names
   with `docker compose exec -e NAME` and no value, so only the NAME is on a command line; `002` reads them with
   `\getenv` and fails loudly on a missing or short one.
4. **`db/schema/003_revoke_large_object_writes.sql`**, connected to database `salon`: the same dry run (its final
   COMMIT turned into ROLLBACK), then for real. Check, as `salon_ro`: the large-object create function is not
   executable (it answers SQLSTATE 42501).
5. **The credentials:** n8n's Postgres credential holds `salon_app`, its connection limit lowered to 10 (MIGRATION-PLAN
   §3o (e); created by its owner in n8n); the dashboard's
   environment holds `salon_ro` under the standard `PG*` names (MIGRATION-PLAN §3t, decision 2).
6. **The backup step:** the nightly job calls `db/ops/pg-backup.sh` (section 2). Its first night's log is the check.

## 0b · Rendering the client's workflows (Phase 8; offline)

> Shown on a fictional second client (`tests/unit/render-client.test.py`), **not run for a real one yet**. The bounds:
> EUR only (`priceEUR`, and `€` written in two nodes), customer text in English, two config keys that drive nothing (`instagram`, `business.locale`), the prompt carries a fixed example that hair colouring is not offered; a client offering it gets a contradicting prompt until a Main edit (quality only: `Merge Slots` and `Slot Gate` refuse a service id the config does not hold), the new instance's credentials linked by hand, and not yet shown on a real second deployment.

1. **The client's config** — a copy of `config/client.config.example.json` filled in for the client, kept OUTSIDE the
   repo or as exactly `config/client.config.json` (gitignored; another name under `config/` is NOT ignored). Check:
   `CONFIG_EXAMPLE=<file> node scripts/check-config-schema.cjs`.
   Two template keys the engine reads with a fallback, `messageTemplates.cancelRetry` and `dryRunNoChange`, are
   optional: given as non-empty text, they are carried; left out, the node's generic text answers; given empty or
   null, the render refuses them. **Check every template by eye:** one given only spaces is taken as text, and the
   customer gets a blank reply (a recorded bound, PHASE-8-PLAN R2b).
2. **The secret input** — a JSON file with `telegramChatId` and `turnstileSecret`, mode 0600, owned by the operator,
   outside the repo (the render refuses one inside it); written by the operator, never through a chat. Either key may
   be left out, and its slot then stays the `REPLACE_WITH_…` placeholder — which means editing those nodes by hand in
   the new instance: "no node edited by hand" holds only with both keys given.
3. **Render:** `python3 scripts/render-client.py --config <file> --secrets <file> --out <a directory that does not exist yet, outside the repo>`.
   It refuses, by name: a key the demo's committed config literal holds that the config lacks (the two optional keys
   above are the only keys read beyond those literals — `tests/unit/render-client.test.py` checks that every config
   path a workflow reads is one or the other), a value of another kind, a list element (a service, a day's hours)
   without the shape of the demo's, an empty template, `services` that is not a list, a number that is not finite (NaN,
   or one that overflows) or lies outside the JS safe-integer range; it also refuses an output path that exists or
   resolves into the repo, and an export whose slots moved. Run it from the repository: it finds the repository from
   its own real path, so a copy of the script elsewhere guards the wrong directory. The output (0700 / 0600) can hold
   the secrets: delete it once imported.
   *(Corrected 2026-10-28, Phase 8 R2: this step said it refuses "a key the workflows read that the config lacks" —
   too broad: the two optional keys are read and not required.)*
4. **Import** the five `workflow.<key>.json` into the client's own n8n, link each node's credential there (the exports
   carry placeholders for them), and run that instance's own parity and probe checks before activating anything.

## 1 · Daily health checks (read-only)

| Check | Command | Green means |
|---|---|---|
| Every production workflow equals its committed export, and the active workflows are exactly the listed ones | `bash scripts/check-exports-parity.sh` | exit 0: the five `WORKFLOWS` entries match live (content + settings), all active, no unlisted active workflow |
| The graph that RUNS (published) matches the committed Main structurally | `python3 scripts/check-live-parity.py` | `PARITY OK` on the one active holder of `barber-inbound` |
| Turnstile is on | `python3 scripts/workflow-step.py probe db/copies/main.json <Main workflow id>` | a dummy token answers 403 `turnstile_failed`, executed by Main, the path's only active holder |
| Nothing of ours listens on every interface | `bash scripts/check-listeners.sh` | exit 0 (other users' daemons are listed, never failed on) |
| The owner dashboard is running | `systemctl --user status salon-dashboard` | active; the unit is `ops/systemd/salon-dashboard.service`, restarted on a crash |
| The scheduled workflows ran | n8n's execution list for Reminders and Purge (the API's `GET /executions?workflowId=…`) | the latest runs have status `success` |

The workflow ids are the ones `scripts/check-exports-parity.sh` lists in `WORKFLOWS` (`scripts/workflows.py` parses it).

## 2 · The nightly backup — verify it

- **What runs:** the backup user's own scheduled job (outside the repo) calls `db/ops/pg-backup.sh`. It dumps the
  `salon` database from one snapshot, records a sha256 and per-table statistics, restores the dump whole into a
  throwaway container with no network, and compares the restored statistics with the recorded ones.
- **Green:** the job's log shows `pg-backup: dump written …` and `pg-backup: verify OK — …` for the night, and no
  `pg-backup: FAILED at <step>` line.
- **Re-verify any dump on demand:** `bash db/ops/pg-backup.sh --verify <dump file>` (checksum, the five tables in the
  TOC, a full restore into a throwaway, statistics equal).
- **Known residual:** the job runs the script from the repo's working tree, so an uncommitted edit present at that
  hour is what runs (final security pass, PHASE-7-PLAN item 9). Keep the tree clean.
- Restoring a whole deployment (the repo, n8n's database and key, Postgres) is `docs/RESTORE-PROCEDURE.md`.

## 3 · Deploying a workflow change — `scripts/workflow-step.py`

One call per step, each read back; nothing automatic. Only an APPROVED delta can be applied
(`scripts/diff-workflow-copy.py` → `APPROVED_DELTAS` / `APPROVED_RENAMES`, by exact identity); a plain parameter edit
uses `--allow <node names>`. The full rules are the script's own docstring and `docs/n8n-rollback.md`.

1. **Commit the export first.** The tool reads `HEAD:n8n/workflow.<key>.sanitized.json`, never the working tree.
2. **Rehearse on a scratch:** `python3 scripts/workflow-step.py rehearse-rollback db/copies/<key>.json <id> HEAD:n8n/workflow.<key>.sanitized.json (--allow … | --delta-file F)`
   — creates an inactive `SCRATCH — …` copy of the live workflow, applies the edit, rolls it back, deletes the scratch.
   Not green → stop.
3. **Deactivate** → **put** with a new snapshot file OUTSIDE the repo (`--snapshot <scratchpad>/S1.json`). The put
   prints every node whose stored content it changes (sticky notes included) and reads everything back.
4. **Activate** (it proves published == draft) → **evidence**: `probe` for Main (dummy token 403) and Owner Actions
   (a body probe: unsigned 403 `invalid_signature`, signed unknown record 404 `not_found` or 503 `store_unavailable`,
   the path's only holder); for the others, parity and the next scheduled run.
5. **Parity:** `N8N_WORKFLOW_ID=<id> python3 scripts/check-content-parity.py n8n/workflow.<key>.sanitized.json`, then
   `bash scripts/check-exports-parity.sh`.
6. **If anything after the deactivate is red:** `deactivate` (if active) → `rollback db/copies/<key>.json <id> S1.json`
   → `activate`, and stop. Delete the snapshot once the edit is closed (it holds live values).

Each production run of these steps is an irreversible-action approval of its own (`.claude/rules/irreversible-actions.md`).

## 4 · A Turnstile window (a test run that needs real messages)

`python3 scripts/turnstile-window.py --precheck-only` first (read-only). Then
`python3 scripts/turnstile-window.py -- <command>`: it lowers Turnstile on Main ONLY for the command's duration,
restores it, and proves the restore with a dummy-token 403. Exit **3 = SAFETY: Turnstile is NOT proven restored** —
restore the literal before anything else. A window is its own approval, with its call budget (PHASE-7-PLAN).

## 5 · Postgres roles (`db/schema/002_roles.sql`)

| Role | Login | Can do | Used by |
|---|---|---|---|
| `salon_owner` | no | owns the schema and every object (DDL) | nobody logs in as it |
| `salon_migrator` | yes | applies migrations with `SET ROLE salon_owner` | the operator, for a schema change |
| `salon_app` | yes | DML on the five tables plus their sequences and two helper functions (and, by default privileges, on tables the owner adds later) | n8n's Postgres credential |
| `salon_ro` | yes | SELECT only | the owner dashboard, verification, the GUI below |

The passwords live in a root-only roles file and in the credential stores that use them; never on a command line,
never in a file in this repo. Postgres publishes on `127.0.0.1:5432` only (MIGRATION-PLAN §3h; the check is `ss -ltn`
showing `127.0.0.1:5432` and no wildcard bind).

## 6 · Viewing the workflows safely

**Measured, not assumed (7-2 R4, 2026-10-26):** the Main workflow was opened in the n8n editor and the editor's
auto-layout was pressed. Nothing was published, but the DRAFT changed: 179 node positions and three sticky-note sizes —
and the workflow setting `binaryMode` appeared (settings are not versioned, so it applies to the running workflow too).
The exports parity guard went red on Main until D6c's put wrote the committed content back (2026-10-27); `binaryMode`
was not written back but allowlisted at exactly `"separate"`, its default reading (MIGRATION-PLAN §7a).
**Not measured:** whether merely opening a workflow, without touching anything, writes to it.

So:
- **Read the workflow from the repo, not the editor:** `docs/FLOW-DIAGRAM.md` and `n8n/workflow.<key>.sanitized.json`
  are the reviewed versions, and the parity guards prove live equals them.
- **If you open the editor,** touch nothing (no auto-layout, no drag, no save), and run
  `bash scripts/check-exports-parity.sh` afterwards: a changed draft shows as `UNPUBLISHED DRAFT` or drift.
- **Never edit a production workflow in the editor.** Changes go through section 3; a draft saved in the editor
  without publishing differs from what runs, which is why the parity guards compare the published graph too
  (`scripts/check-content-parity.py`, `check_published_matches_draft`).

## 7 · A database GUI over an SSH tunnel, as `salon_ro`

> ⚠ **Dry-run procedure — NOT run end to end** (PHASE-7-PLAN, 7-3, item (b)). The steps follow from what is measured
> (Postgres on the server's loopback only; `salon_ro` is SELECT-only) but nobody has connected a GUI this way yet.
> Installing the GUI client on the operator's machine is the operator's step.

1. **On your own machine, open the tunnel** (the host is `SSH_ORIGIN_HOST` from `CLAUDE.local.md`, the machine
   itself — never a Cloudflare-proxied name; local port 5433 so a local Postgres on 5432 does not collide):
   ```
   ssh -N -L 5433:127.0.0.1:5432 yigit@<HOST>
   ```
2. **In any Postgres GUI client** (DBeaver, pgAdmin, TablePlus — any that speaks the Postgres protocol), create a
   connection: host `127.0.0.1`, port `5433`, database `salon`, user `salon_ro`, SSL off (the tunnel is the
   encryption). The password: read it where it already lives — the dashboard's environment file on the server holds
   the `salon_ro` credential — and type it into the client's own password store. Do not paste it into a file, a
   chat or a command line.
3. **What you can do:** read the five tables in schema `salon`. Any write is refused by the role (SELECT only).
4. **What to keep in mind:** `salon_ro` can read every column, including the full `sender_key` (a bearer credential on
   the widget lane) and message content (final security pass, item 3, Q16). Do not export or screenshot rows.
5. **Close the tunnel** (Ctrl-C) when done.

## 8 · Public demo (`docs/PUBLIC-DEMO-PLAN.md`)

**Take it offline — one step.** Pausing the Vercel project makes the demo answer 503: the site and the chat widget go.
The engine does NOT stop — its webhook stays up, bounded by the LLM cap, the edge rate limit and the turn cap; stopping
it is the kill-switch or deactivating Main (⚠ ONAY). An emergency pause has a standing approval (ruling D6); unpausing,
and deactivating Main, do not.
- CC: Vercel `pause_project` (its Vercel connection), then `bash scripts/demo-offline.sh measure` → `offline (503)`.
- A shell: `bash scripts/demo-offline.sh pause` (and `unpause`) — needs `~/.vercel-demo.env` (0600, this user):
  `VERCEL_TOKEN`, `VERCEL_PROJECT_ID`, and `VERCEL_TEAM_ID` if the project is in a team. It prints statuses only and
  exits 0 only when the new state was MEASURED (503 after a pause, 200 after an unpause); no answer at all is "NOT
  measured" (`measure` exit 4), never "offline".

**The staged engine edits** (`n8n/staged/`): `Eval Spend` fail-closed (Main, `--delta-file
n8n/staged/workflow.main.delta.json`) and the 30-day lead retention (Purge, `--delta-file
n8n/staged/workflow.purge.delta.json`). Each is deployed with §3 — note §3 step 1: the tool reads the export from HEAD,
so the put names the STAGED path, which is committed. The Main delta allows three nodes: `Eval Spend`'s code and two
text-only edits (`Build Spend-Meter Alert`'s comment lines, the `Spend-cap note` sticky). Before the Main put, the
`Read Spend` scratch measurement
(the plan, "R2 — measured before any write"); before the Purge put, the leads counts read with `salon_ro`.
**The promotion commit** (once both are live and read back): copy each staged export over its committed export, set
`leadsRetentionDays` to 30 in `config/client.config.example.json` in the SAME commit (`render-client.test.py` case 1
holds the example to the committed export), and correct the sentences that describe the meter as fail-open
(`docs/FLOW-DIAGRAM.md`, `docs/DATA-MODEL.md`, `docs/UX-ARCHITECTURE.md`) — they are true until the put and false after.
**Before go-live:** the /privacy page states the backup retention from `db/ops/pg-backup.sh`'s default and says the
engine's run records are kept "for a period set on the server" — measure both values in force and correct the page if
either differs (the plan, "R2 — measured before any write").

**Seed rows** (`scripts/seed-workflow.py` — its `up`, each action and `down` are each gated, per its docstring): `pd-lead-insert
--message pd-… --created-at <ISO, more than 30 days back>` for #13 (plus fresh `pd-` leads if the table is too small for
the Purge's cap — at least 5 rows per aged one); `pd-conv-insert --session w-pd-… --turn-count N` for #19; `clean-pd`
removes every `pd-` conversation and lead, and nothing else.
