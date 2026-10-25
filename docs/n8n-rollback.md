# n8n workflow rollback — the refactor escape hatch

> **Why this exists.** git does **not** restore the live workflow. The repo holds only
> `n8n/workflow.sanitized.json`, where credential / base / table ids are **masked placeholders**
> (`REPLACE_WITH_*`, `appXXXX…`). Importing that into n8n reconnects nothing — every credential binding
> breaks. (Proven risk: the CRT #8 `authentication:none` drill silently dropped the Delete node's
> credential; only a real restore surfaced it.) So a rollback needs a **full export with real refs**,
> kept **out of git**.

## ⚠ Do NOT trust `n8n_workflow_versions` for THIS workflow
The n8n-mcp version history is **stale**: on 2026-08-17 its newest snapshot was **version 38,
2026-08-15 22:37** — the entire CP3 / CRT-#8 / re-audit body of work (08-16 → 08-17, ~50 changes)
created **no** tracked version. Rolling back through it would **destroy CP3**. It is not a safe
restore source here. Use the two paths below instead.

## After the cutover (7-F1, ruling K1, 2026-10-25): engine edits and their rollback

> ⛔ **`--engine-edit` / `--restore` are DISABLED and ABANDONED** (ruling 2026-10-25, PHASE-7-PLAN §4d): five review
> rounds each found a new HIGH. **Their replacement, single-purpose step commands, did not pass review either** and is
> not on `main` (local branch only). **No post-cutover engine edit has a reviewed tool today.** The section below
> describes the abandoned tool, kept as the record of its design.

Everything below this section is the Airtable-era refactor procedure. After the D6b cutover the five Postgres copies
are the live holders, and **each copy's reference is its own committed export** (`n8n/workflow.<x>.copy.sanitized.json`).
An engine edit and its rollback are ONE command, `scripts/deploy-workflow-copy.py … --engine-edit COPY_ID [--from-rev REV]`
(each run is its own ⚠ ONAY under `irreversible-actions.md`):
- **edit:** commit the edited export, then run without `--from-rev` (it takes HEAD's export): checked before any write →
  deactivate → PUT → read back live == committed → activate → the Turnstile dummy-token probe. The production path has
  no holder for those few seconds.
- **rollback, normal:** `git revert` the export commit, then the same command from HEAD. **Emergency:** `--from-rev` the
  previous commit; the exports parity guard then stays red until HEAD's export matches live again, by design.
- **an engine edit never changes a masked value** (a credential, a chat id, the Turnstile secret, the calendar id):
  those are operator or credential operations. Every placeholder in the export is filled from the live copy's value at
  the SAME path; a placeholder with no live counterpart (e.g. a new node that needs a credential) is refused before any
  write, as an operator step.
- **if a step after the deactivate is red** (or the run is interrupted: Ctrl-C, SIGTERM and a dropped ssh session are
  recorded and the run stops at the next step boundary), the tool re-PUTs the pre-edit live body it holds in memory —
  only if the copy no longer holds it — proves it, re-activates and exits 3. The tool never saves that body, but like
  every request it passes through a 0600 temp file (and the API key and Access secret through a header file the same
  way) that is deleted when curl returns; a kill -9 at that moment can leave them.
- **if even that cannot be proven** it exits 4 (SAFETY). The copy is left INACTIVE, except when its content is back and
  only the probe failed, in which case it stays ACTIVE and the message says so. For the inactive case it prints the
  exact restore command: `… --restore COPY_ID --from-rev REV`, which accepts only that inactive copy, fills by path from
  its own values, writes, reads back, activates and proves. It never activates an original.

## Snapshot — before EACH refactor step (one per step, never reused)

A single snapshot only rescues the moment it was taken — rolling back to it 5 steps later deletes the
4 steps between. So **take a fresh export before every step, named by the step.**

**PRIMARY — targeted per-step node snapshot (surgical, reliable, small payloads):**
A refactor step touches a *known* set of nodes. Before the step, capture the CURRENT full parameters of
exactly those nodes (via `n8n_get_workflow` mode `filtered`, nodeNames = the step's targets) and save them
to `n8n/.snapshots/step-<NN>-<slug>.local.json`. Roll back by `n8n_update_partial_workflow`
`updateNode` writing each saved node back to its captured params (+ re-add/re-remove any nodes/connections
the step changed — record those inverse ops in the same file). This is the method used all session; it
avoids the full-workflow-JSON problem entirely.

**BACKUP — n8n UI native download/import (full workflow, credential-refs preserved):**
Editor → ⋯ → **Download** → save as `…/step-<NN>-full.local.json`; restore via ⋯ → **Import from File**.
Use when a step's blast radius is larger than expected (or after a browser clobber). Needs the UI.

> **Why NOT `n8n_get_workflow full` (MCP) for a full snapshot — proven impractical here, 2026-08-17.**
> The `Validate Intent` node carries a large **compiled ajv validator** (generated blob) that bloats the
> full export. Two MCP export attempts dropped the connection mid-write; one hung ~13 min writing the JSON
> in fragments. So MCP **full**-export/`n8n_update_full_workflow` are **not reliable for THIS workflow** —
> the native UI download/import handles the size fine, and the targeted per-node capture above is small and
> reliable. (`n8n_get_workflow` mode `filtered` on a handful of nodes is fine — it is only the whole-graph
> export that is too big.)

**NEVER COMMIT a snapshot.** It carries **real** credential / base / table ids — one accidental commit
leaks them on a PUBLIC repo (irreversible). Guards: `.gitignore` excludes `n8n/.snapshots/` **and** the
`*.local.json` pattern; the pre-push **`security-auditor` scope includes `n8n/.snapshots/`** so a stray
real id is caught before push. A snapshot in a commit = a leak → rotate the credentials.

## Rollback — if a step breaks the suite

**PRIMARY — targeted node restore (MCP partial):**
1. For each node in the step's snapshot, `n8n_update_partial_workflow` `updateNode` → write it back to
   the captured params; reverse any add/remove the step made (the inverse ops are recorded in the snapshot).
2. `n8n_validate_workflow` → 0 errors.
3. **Publish** → `WEBHOOK_URL=… bash tests/run-regression.sh` → **must be 12/12** before anything else.
   If the step touched a reply-exit path, also run the ⚙ manual drills (see below).

**BACKUP — n8n UI Import** of the step's full download (⋯ → Import from File) → Publish → suite. Use for a
larger-than-expected blast radius or a browser clobber.

**DO NOT USE — n8n version history. ⚠ Known trap here.** Proven 2026-08-17: **MCP editing does not create
n8n version snapshots** — the entire 08-16/17 work (CP3 / CRT-#8 / re-audit) is **absent** from the
version history (newest = v38, 2026-08-15). A "restore" there reverts to **before CP3** and destroys it.
Only consider it if you have independently confirmed a *newer* version exists. (Recorded so no one
reverses this ordering later.)

**Backup — MCP `n8n_update_full_workflow`** is available in principle but **unreliable on this workflow**
(same `Validate Intent` bloat as above) — use only if the UI is unavailable, via a sub-agent, and expect
possible connection drops.

## ⚠ `b1` (Build Reply Payload) has a mandatory extra gate
`b1` reorganizes **every** reply path, but the automated harness only exercises 6 of the 11 reply exits.
The other **5 infra-503 exits + guard-trip + the reconcile pair are `b1`'s highest-risk blind spot.**
**Rule: after `b1`, ALL ⚙ manual drills (suite #2·#6·#19·#23 + the 5 infra-503 exits) are run by hand;
no commit for the `b1` step until every one passes.** (Same discipline applies to any step that edits a
node feeding a reply exit.)

## Close gate — run AFTER publish + suite, BEFORE commit (every refactor step)
The committed `n8n/workflow.sanitized.json` is now HAND-MAINTAINED (surgical, sanitized-preserving
edits — a raw full export is unreliable: the compiled ajv validator in `Validate Intent` bloats/mangles).
A hand-built artifact can silently drift from the live workflow, and Codex (L3) audits the committed file —
so drift means auditing something that is not the running system. Two machine checks close every step:

1. **Live↔committed parity** — `N8N_API_URL=… N8N_API_KEY=… python3 scripts/check-live-parity.py`
   compares node count · node-name set · connection topology (never the heavy Code bodies). Exit 0 = OK,
   1 = DRIFT → **stop and reconcile before commit**. (Host is behind Cloudflare; the script sends a
   browser User-Agent to clear the 1010 browser-integrity block — the API key still authenticates.)
2. **Host-leak guard** — `bash scripts/check-no-host-leak.sh` (reads the real host from `$N8N_HOST` /
   gitignored `CLAUDE.local.md`, git-greps tracked files). Exit 0 = clean, 1 = LEAK → **fix before commit**.
3. **computed_reply coverage** (Refactor #5 invariant) — `python3 scripts/check-computed-reply-coverage.py`
   asserts EVERY reply-producing builder (nearest Code ancestor of a Save State) sets `computed_reply`. The
   thin-reader Build Reply Payload reads the reply from that column, so a builder that forgets it emits an
   empty reply. Exit 1 = a builder drifted → **fix before commit**. Catches CP4's new reschedule builders.
4. **cancel-validation parity** (Refactor #4 invariant) — `python3 scripts/check-cancel-validation-parity.py`
   asserts the cancel-validation rules (duplicated because n8n Code nodes can't share a helper) never drift:
   the gid shape regex `^[0-9a-v]{5,1024}$` is identical in all 3 uses, the `confirm_turn` regex `^[1-9][0-9]*$`
   in both confirm gates, and Cancel Lookup (ask `structOk`) + Validate Cancel Target both check {finite
   start_utc, gid shape, calendar_id present}. Exit 1 = a copy drifted → **fix before commit**.
5. **content parity** (CP4 sub-step 3) — `N8N_API_URL=… N8N_API_KEY=… python3 scripts/check-content-parity.py`
   compares, per executable node, a normalized projection of `parameters` + `credentials` (sanitize
   placeholders + n8n serialization noise — `__rl` display cache, empty `options`, condition `id`/meta,
   omitted-GET method, trailing whitespace — are normalized; sticky notes excluded). Catches the drift the
   STRUCTURAL parity (#1) is blind to: a changed Code body, mapping, condition, or HTTP option. Exit 1 =
   DRIFT (prints node + field) → **reconcile before commit**. (On its first run it caught a real live
   regression — `Get Calendar Busy` had silently lost its 15 s timeout; #1 could not see it.)

All five run again inside the `security-auditor` pre-push pass. A step is not closed until all are green.

## Standing rules (Ö3–Ö5) during refactor
- **Isolation (Ö3):** refactor test traffic uses a dedicated `sender_key` prefix; every Airtable row
  and GCal event it creates is cleaned at the end of the step (the harness self-cancels its bookings so
  the GCal events are deleted). Never touch real/demo records.
- **Stop rule (Ö4):** on a single unexplained suite failure — roll back the step (above), report, and
  **stop**. No same-session "quick fix".
- **One session = one step (Ö5):** steps are not chained.

## Rehearsal log
A rollback rehearsal (snapshot → trivial change → restore → publish → suite 12/12) is recorded in the
commit that adds this file; re-rehearse if the n8n host or credential set changes.

## ⚠ API save blocked by `settings must NOT have additional properties` (2026-08-18)
> **Corrected in place 2026-10-22** (settings-parity, [MIGRATION-PLAN.md](MIGRATION-PLAN.md) §3r). The symptom
> below is what the instance's version did on 2026-08-18. Three statements were wrong by today's measurements and
> are rewritten where they stood: the cause, "re-adds these defaults", and the behaviour impact.

**Symptom.** Every MCP save (`n8n_update_partial_workflow`, any op — even a one-field `patchNodeField`)
fails with `Invalid request: request/body/settings must NOT have additional properties` (400,
`rollbackPerformed:false`, nothing applied).

**Cause, as it stood on 2026-08-18.** The instance stored workflow-settings keys that the public API's settings
schema of that version did not list: `binaryMode`, `availableInMCP`, `timeSavedMode`, `callerPolicy` (beside
`executionOrder`). The MCP tool re-sent them verbatim and the API answered 400. This is not credential or
permission related.

**Today (measured 2026-10-22):** the instance's own OpenAPI spec lists all four keys. `binaryMode` (and
`credentialResolverId`) are "derived, internal" and **ignored** on create and update: a PUT carrying `binaryMode`
returns 200 and the value is dropped (D3c). `callerPolicy` and `timeSavedMode` are **kept** on create (T0).
*Corrected:* this section used to say n8n "re-adds these defaults server-side on every save". It does not: a
workflow created through the API with `settings: {}` reads back `{}` (T0), three originals carry no extra key, and
Reminders carries only `binaryMode`. The source explains where `binaryMode` comes from: the editor's settings
dialog turns an undefined `binaryMode` into `"separate"` when it saves.

**Fix — save via the raw public API with a cleaned settings body (MCP cannot do this):**
`GET /api/v1/workflows/{id}` → build `{name, nodes, connections, settings:{executionOrder:"v1"}}`
(drop every other top-level key AND the 4 extra settings keys) → `PUT /api/v1/workflows/{id}`.
The request succeeded (HTTP 200). *Corrected:* it was written that the API "re-adds the 4 defaults itself".
Whether a PUT that omits a stored key PRESERVES it is **not measured**. That is route R3, moved to D6b's plan;
Main's history is deliberately not used as evidence for it. Auth =
`X-N8N-API-KEY` + a browser `User-Agent` (Cloudflare 1010), same as `scripts/check-live-parity.py`. Verify
after: node count unchanged, `active:true`, node params byte-faithful vs the pre-PUT GET, suite 12/12.

**Operating note.** The editor stays **closed** (relaxed-model). While this instance behaves this way, all
live edits go through the raw-API PUT, not MCP `n8n_update_partial_workflow`. (A future n8n-mcp that strips
unknown settings before PUT would restore the MCP path.) Behaviour impact of a missing key, *corrected 2026-10-22*:
`binaryMode` absent behaves as `"separate"` (every reader at the running build's source tag, listed in
MIGRATION-PLAN §3r) · `callerPolicy` absent is its documented default, and no workflow here has an Execute
Workflow node · `timeSavedMode` is a metrics setting · **`availableInMCP` is NOT inert:** Main carries `true` and
the instance-level MCP server is enabled (measured). It is recorded as an accepted exposure behind Access at the
edge and MCP bearer auth at the origin, and it is on the final security pass list. *The old sentence said "no
binary data" and "MCP-exposure off".* The second was false. The first is in doubt: the Zernio HTTP node runs on
the default response format, which can emit binary (a static finding; D3c). Original values snapshotted in `n8n/.snapshots/substep3-workflow-settings.local.json`.
