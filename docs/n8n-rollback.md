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

All four run again inside the `security-auditor` pre-push pass. A step is not closed until all are green.

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
