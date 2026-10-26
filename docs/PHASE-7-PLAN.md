# Phase 7 — Test + Codex + DoD · PLAN v4

> **Status: PLAN v4 APPROVED by Yigitcan (plan-gate), 2026-10-24**, presented in chat in the full format and approved with
> the amendments below; derived against `97aded7` after the migration closed (D6b accepted 2026-10-24, A1–A9; K-6 closed,
> `0bd4e74`). It replaces v3 (approved 2026-09-17, derived against `232321c`; its full text is in git at `97aded7`). v3's
> measurements and rulings that still stand as records (M1, M2, CP 7-0, the window protocol, the v3 7-1 window plan) are
> kept at the end of this file. *(History: Phase 7 was ⏸ ON HOLD from 2026-10-19 until the migration's cutover was
> accepted.)*
> **A plan that is not in the repo is not a plan, it is a memory** (`governance-sync.md` §2) — which is why v3 existed,
> and why v4 replaces it in place rather than living in chat.
## Re-entry rulings (Yigitcan, 2026-10-24) — the premise re-derivation after the migration

The fifteen premises re-derived after D6b (MIGRATION-PLAN §3t, Round 3c close) were ruled:
- **1–12 and 15 ACCEPTED as recommended:** (1) the Airtable request budget is gone; a window's precondition becomes a
  declared LLM spend cap plus a counted Google API quota · (2) the "7-1 has no live route" conflict is resolved by the
  2026-10-18 window protocol · (3) the window runs through the deploy helper's `--turnstile-swapped` mode and a COMMITTED
  window script · (4) §1 is re-measured from scratch · (5) the migration's race drill (A3) is CRT 1b's sequential
  evidence; a truly simultaneous pair is a separate drill with its expectation written first · (6) evidence the migration
  already produced (CRT 1a/6/8/10/11) is not re-run · (7) the drill matrix and harness are scanned for Airtable-only
  semantics and a COMMITTED seed tool replaces direct row injection · (9) RUNBOOK covers Postgres provisioning ·
  (10) ship-gate lines naming Airtable are rewritten with D6c · (11) the named items form their own fix checkpoint ·
  (12) the final security pass keeps its place at the end, scope frozen · (15) K-5 stays its own "not tested" line.
- **13 (the dashboard runs as an unsupervised process) → the FIRST item of the fix checkpoint.**
- **14 (K-6) → DONE** (`0bd4e74`: the route exists, behind Access, one named email).
- **8 → D7 is Phase 7's FIRST checkpoint**, before any test checkpoint: rules, DATA-MODEL, the MASTER-BRIEF stack and
  README describe Postgres; Airtable only as "read-only until D6c".
- **Two NEW Phase 7 items:** (a) a read-only owner view or export of their own data (Postgres stays the single source of
  truth, no dual write; the form and the columns, given PII, are decided in PLAN v4); (b) a database GUI for the operator
  over an SSH tunnel as `salon_ro` (5432 stays closed).

## Ship-gate #17 — MOVED to the end-of-phase security pass (Yigitcan's ruling, 2026-10-18)

**The final security pass: what it carries (list consolidated 2026-10-22).**
1. **Ship-gate #17** (below).
2. **Main's `availableInMCP: true` with the instance MCP server enabled** (measured 2026-10-22). It is an
   accepted exposure behind Cloudflare Access at the edge and MCP bearer auth at the origin (ruling; MIGRATION-PLAN
   §3r "MCP exposure"). The pass decides whether it stays.
3. **Q16:** split `salon_ro`'s column access (speed plan 2026-10-22; it was "before D5").
4. **D6d:** a permanent off-server backup target (speed plan 2026-10-22).
5. Backups of a secret file fall outside the deny scope (MIGRATION-PLAN §3n), and the root-only-file item in
   [OPERATIONAL-INCIDENTS.md](OPERATIONAL-INCIDENTS.md) (already recorded as joining this pass).
6. **The dashboard logs the full read error server-side** (`web/dashboard/app/page.tsx`, `console.error`): a driver message
   can carry the database host. It reaches neither the repo nor the page (which shows only `table: code`), but it reaches
   the local log (Yigitcan's ruling, 2026-10-23; MIGRATION-PLAN §3t).
7. **WhatsApp senders (phone numbers) in the inactive Main original's `staticData`**: its owner-alert throttle keys are
   `class:sender`, kept by n8n indefinitely; no purge reaches them, and they stay with the original after the cutover
   (Yigitcan's ruling, 2026-10-24; MIGRATION-PLAN §3t, #11).
8. **Codex CRT #10 F2: the dashboard's write check runs once per process and its pass is cached**, and the pool takes its
   identity from the environment at each new connection, so a grant made after the first render, or a changed `PG*`
   variable, is never re-checked. Taken WITH item 3, Q16 (Yigitcan's ruling, 2026-10-24; MIGRATION-PLAN §3t, Round 3b).
9. **Auditor I-2: the nightly job runs `db/ops/pg-backup.sh` from the repo's working tree**, so an uncommitted edit
   present at that hour is what runs (Yigitcan's ruling, 2026-10-24; MIGRATION-PLAN §3t, Round 3a and 3b).
10. **`storeError` puts the driver's error code on the dashboard page unfiltered** (`web/dashboard/lib/store.ts`); the
   pool listener's class filter could apply there too (Yigitcan's ruling, 2026-10-24; MIGRATION-PLAN §3t, Round 3c).
11. **The Purge schedule time stands in public files** (ROADMAP, MIGRATION-PLAN), against the rule that job times stay
   out of them (security-auditor LOW, Round 3b; Yigitcan's ruling, 2026-10-24; MIGRATION-PLAN §3t, Round 3c).
12. **The dashboard's Access session is 730 h:** decide a shorter one; and confirm, without printing it, that the policy's
   single email equals the repo author's email (a boolean only) (Yigitcan's ruling, 2026-10-24; MIGRATION-PLAN §3t, K-6).
13. ✅ **CLOSED 2026-10-26 (7-2 R3, measured live):** every Main owner alert prints the sender MASKED (the dashboard's form; `_alert_sender` stays full for the stamp and never reaches Telegram) — in R3's window the handoff alert reached Telegram without the full session id (§4g). ⚠ The other half of this item's ruling — `sender`/`channel`/`stage` filled from node references for the infra alerts (named item (5)) — is NOT shown done: `Send Error Response` still passes the error item's own fields (read in the committed Main export at 7-2 R4). It stays open as named item (5); with masking in place, filling the sender no longer widens an exposure. *Was:* **Main's owner alerts print the full `sender_key` into Telegram** (`Build Owner Alert`: `'sender: ' + sender`). On
   the widget lane a full `sender_key` is a bearer credential (`security-secrets.md`). Mask it there AND, in the same
   change, fill `sender`/`channel`/`stage` from node references for the infra alerts (named item (5)), because filling
   the sender first would widen this exposure before it is masked (Yigitcan's ruling, 2026-10-25, at the 7-F1 plan
   approval). *Added after premise (12) froze the scope at twelve: by an explicit ruling, not by drift.*

**Ship-gate #17** (`CF_API_TOKEN` revoked or reduced to Read, AND the four leaked credentials rotated)
**is no longer the gate in front of CP 7-0.** It moved to a security pass at the END of Phase 7. It stays
OPEN on the ship gate — the row is not deleted, only its position changed.

*(This section used to read "STEP 0 — before the first BUILD step … CP 7-0 does not start until it is
done." That was the plan as approved on 2026-09-17; the rotation then stopped on a measured capability
wall — the Cloudflare account id is unreachable from this machine — and the plan is corrected in place
rather than annotated beside, per `governance-sync.md` §6.)*

**Why the deferral is safe:**
*Yigitcan's rationale (his ruling, recorded as given), with what was measured against it:*
- **None of the four leaked values sits on a customer path.** The four that leaked on 2026-09-13 are: two
  Cloudflare service tokens (each an id + secret pair), the n8n API key, and the owner's Telegram chat id.
  The two service tokens gate the n8n API and the owner-only `/webhook/owner-*` path; the API key is an
  operator tool; the chat id addresses the OWNER, not a customer. No customer request is authenticated by
  any of them. *(`CF_API_TOKEN` did NOT leak — it is on #17 because its Edit scope must be reduced after the
  rotation, a separate reason. An earlier draft of this paragraph listed it among the four; corrected.)*
- **The leaked values went into a transcript on the machine that already stores them.** Measured
  2026-10-18: all six variables the leak printed are present in `~/.n8n-api.env` (presence only — values
  not read). ⚠ **That makes "no new exposure" true for THIS MACHINE and not beyond it:** the transcript is
  a session that was also transmitted to the model provider, which this framing does not cover.

**Measured before writing this (2026-10-18), not assumed:** no CP in this plan requires a Cloudflare API
WRITE. Every Cloudflare-shaped line in this file was grepped; the only one that writes to Cloudflare is
#17 itself. (Positive control: `grep -ciE turnstile` returned 9 against `00c626f`, before this round's edits.) ⚠ One conditional: CP 7-0's *real-token* option could turn out to need a Turnstile widget
hostname-allow-list change, which IS a Cloudflare write. That is an outcome 7-0 might discover, not a
requirement the plan states — and if it is the only route, it is blocked by the same missing account id
and 7-0 stops and reports rather than routing around it.

---

---

## §1 · DISTANCE TO SHIP — measured from scratch, 2026-10-24 (`97aded7`)

| Surface | Measured |
|---|---|
| Live workflows | 10 on the instance: the five Postgres copies ACTIVE (Main 191 nodes, Owner Actions 44, Purge 27, Reminders 19, Drill State 9) and the five originals parked inactive with the same node counts. The production workflows still carry the names "MIG COPY — …" (renamed at D6c, amendment below). |
| Critical-Review Targets (`MASTER-BRIEF.md` §9, the single status source) | 14 rows · 5 closed (3 · 7 · 8 · 10 · 13) · 9 open (1a · 1b · 2 · 4 · 5 · 6 · 9 · 11 · 12). Two drifts: #11 (§9 open, ROADMAP records the CP 6d remediation) and #1b (§9 open, the decision log and ROADMAP say "CLOSED 2026-08-16"; ruled D1 below). |
| Evidence the migration already produced (premise 6: not re-run) | regression 28/28 on the Main copy (D4b) · `run-d11` 13/13 on the production paths (A2) · the routing smoke (A1) · the sequential race with M2's five points (A3) · the M7 failure window (store down, auth failure, spend meter refused) · Turnstile both ways. |
| Ship gate | the one numbered list in `ROADMAP.md`, items 11–21, all open; only #19 names Airtable (rewritten after D6c, 7-S). |
| Named items | the PHASE 7 row of the open-items table below: Q18 (mandatory), (1)–(15), one observation, and v3's older items. |
| Final security pass | 13 items (top of this file): twelve frozen by premise 12, the 13th added by ruling at the 7-F1 approval (2026-10-25). |
| DoD | built ✅ · tested ◐ (the regression passes only in a Turnstile window; WhatsApp not tested, K-5) · cleaned ☐ · sanitized ✅ (10/10 exports, inverted parity) · README/case study ◐ (`docs/CASE-STUDY.md` and `docs/RUNBOOK.md` absent) · pushed ✅ · resume-point memory ✅ for the migration · Loom ☐ (after D6c, amendment below). |
| Test assets | `golden-set.md` 7 cases, never run; `jailbreak-cases.md` 12/12 in the Airtable era; `validate-intent.test.cjs` not in `check-all` (D9); `secret-scan` is a hook by design. |
| Drill matrix / harness (read-only scan, 2026-10-24) | ten ⚙ setups in `regression-suite.md` wrote Airtable rows directly — Claude holds only `salon_ro` now, so they go through a committed seed tool (7-T); #5 depends on `created_at` order and #5/#33 on a fixed fake gid (UNIQUE now); the "break the table" setups (#35, SC3, E-*) have no Postgres equivalent (ruled D6); `''`-vs-NULL is harmless in these rows (the readers use `NULLIF` and `|| ''`) but evidence queries use `COALESCE`. `run-d11` and `run-regression.sh`'s code paths are clean. |

---

## §2 · STANDING RULINGS — premise re-checked

| Ruling | Still alive? | Verdict |
|---|---|---|
| **K-1** + the 2026-10-18 **window protocol** | ✅ | VALID; the window now runs through the deploy helper's `--turnstile-swapped` (with its order guard) and a COMMITTED window script (premise 3) |
| **K-4** `docs/CASE-STUDY.md`, README's 6b section MOVED | ✅ file absent | VALID (7-3) |
| **K-5** regression from the widget lane | ✅ | VALID, with its two lines: it proves the engine end to end on the widget lane; it does NOT prove the WhatsApp adapter boundary (Zernio closed) — a separate "not tested" line in the DoD |
| **E2** `docs/RUNBOOK.md` | ✅ file absent | VALID, now including Postgres (premise 9) |
| **K-3** Loom at ship gate 20 | ✅ | VALID, and taken only AFTER D6c (amendment) |
| **K-2** dead `instagram` / `business.locale` keys | ✅ | DEFERRED to the v2 backlog (amendment) — README must not claim "fully config-driven" while they exist |

---

## §3 · GOAL
Make the post-migration system shippable on test, audit and DoD: close or honestly bound every open Critical-Review
Target, fix the known defects ruled into Phase 7, produce the case study and the runbook, and end with the frozen final
security pass — without re-running what the migration already proved.

---

## §4 · CHECKPOINTS (amended at approval, 2026-10-24)

| CP | What | Rounds | Yigitcan by hand (only what CC cannot) | Stop conditions | Automation |
|---|---|---|---|---|---|
| **7-D7** governance close | rules (`booking-integrity.md`, `spend-safety.md`, `honesty-demos.md`), DATA-MODEL, the MASTER-BRIEF stack and §9's #1b note (D1), README with an honest "not yet / v2" section; test-doc wording; this plan rewritten as v4 | 1 (round 1, offline, parallel) | — | a doc change would need an unmeasured claim | neither |
| **7-F2** dashboard (NARROWED) | **F4** behaviour test (mock driver) · **F7** trim the unused columns · **F12** triage priority before the limit · **D9** `validate-intent` in `check-all` · **new item (a)** the owner CSV export (D7: dashboard route, appointments + leads, the panels' columns, masked) — built and tested OFFLINE, behind a default-off flag, **not exposed live before 7-2's Codex audit** | 1 (round 1, parallel) | — | the export cannot be made masked-only · a mutant survives and its claim stays | `/goal` allowed (offline, goal: `check-all` 0) |
| **7-T** tooling | a COMMITTED window script (premise 3: `--turnstile-swapped`, restore before rollback, `finally`) · a COMMITTED seed tool (premise 7: Access-covered, prefixes `w-mig-p7-` / `mig-p7-`, prefix-guarded clean-up) · `regression-suite.md`'s ⚙ setups rewritten (D6) | 1 (round 1, parallel, nothing run live) | — | any step needing a live write | neither |
| **7-F1** ops + engine (sequential; **plan APPROVED 2026-10-25, scope narrowed by its rulings**) | **Final scope:** item 13, the dashboard under supervision (D8: a systemd user unit with linger) — **✅ live-proven 2026-10-25 (§4d); boot start shown by configuration, NOT by reboot** · **Q18's alert detail (mandatory)**, Purge and Reminders, closed OFFLINE on fixtures of the error shapes measured live in S10 and M7 (label: "offline-proven, error shape measured live"; no operator window, ruling K5) · (2) the spurious `no_candidates` · ~~the reschedule orphan alert's old-slot line~~ → **v2** (Main is not edited before ship, ruling 2026-10-25) · (1) the 502 body, written and tested now, deployed after 7-2 with round 1's code (K6) · K2: item (4)'s premise corrected below, no workflow change. **Moved out by ruling:** (3) rebook after cancel → v2 (§4b) · the reminder-after-cancel gate → v2 (§4b; K4) · (5) → the final security pass, item 13. **Guards (K1):** after the cutover each copy's reference is its OWN committed export; node-level copy↔original comparison is retired for the post-cutover modes, settings copy↔original parity stays; engine tests read the copy exports; every engine edit goes through the helper's edit path (deactivate → PUT the committed export → live == committed → activate → Turnstile 403), each its own ⚠ ONAY. **Rounds: 2** — A (guards, tests, offline fixes, item 13) and B (E1 Purge: Q18 + (2) · E2 Reminders: Q18 · E3 → v2) — **✅ E1 and E2 deployed live 2026-10-25 (§4d)** | 2 | the one root `loginctl enable-linger` command when 7-F1 asks (D8) | parity red after an edit · a drill breaks behaviour the original had · Turnstile not restorable | neither (gated writes) |
| **7-1** ONE window — **✅ RUN 2026-10-25, re-shaped (§4f): the simultaneous race pair (both withdrew, writes overlapped), the DST booking, the Reminders dry-run path; the full suite not re-run (D4b)** | the full regression, the truly simultaneous race pair (its expectation written first: both writers may yield), one DST booking; precondition: a declared LLM spend cap and a counted Google API quota (premise 1) | 2 | — | Turnstile not restorable · a double booking · any outbound send | neither |
| **7-2** audit | Codex: CRT 4, 12's five R3 items, 1a (its own audit), 1b (after the simultaneous drill; D1), the #11 drift, the owner export route (CRT 9/10's PII surface — the export goes live only after this) · CRT 9 → ship gate 18 (K-6 measured in part) | 3 | triggering Codex | a finding → a fix round | neither |
| **7-3** artefacts | `docs/CASE-STUDY.md` (moved from README) · `docs/RUNBOOK.md`: Postgres provisioning, 001–003, the nightly backup, the dashboard service, **new item (b): a database GUI over an SSH tunnel as `salon_ro`** — dry-run, labelled "NOT run end to end" · golden-set expanded to 15 cases (D11) | 3 | installing the GUI client on his machine | — | neither |
| **7-S** D6c-dependent | ship-gate text naming Airtable (#19) · after D6c, which also renames the production workflows (D3, amendment) | 1 | — | D6c not closed | neither |
| **7-4** final security pass + DoD | the 13 items (12 frozen + #13 by ruling, 2026-10-25) · `cleaned` · golden-set + jailbreak run · resume-point memory · one push | 2 | the #17 rotations · the Access session setting (#12, D10) | an item that cannot close is declared, never dropped silently | neither |

**Rounds: 14** — the three "1"s of 7-D7, 7-F2 and 7-T are ONE round (run in parallel), then 2 + 2 + 3 + 3 + 1 + 2. Not
uniform on purpose: 7-F1 and 7-2 carry the risk. *(Was 15 with 7-F1 at 3 rounds; its approval on 2026-10-25 narrowed it to 2.)* (The chat presentation estimated 21 with those three CPs sequential.)

### §4a · Amendments at approval (Yigitcan, 2026-10-24)
- 7-D7, 7-F2 (narrowed) and 7-T run in ONE round as parallel agents with disjoint files; the LEAD alone edits shared
  files and commits.
- **D3 → D6c:** the "MIG COPY — …" production workflows are renamed at D6c, together with the copy specs, the deploy
  helper's name identity (`deploy-workflow-copy.py` finds a copy by its NAME) and the guards, in one coherent change.
  **Consequence: screenshots and the Loom are taken only AFTER D6c.**
- **7-F1 is the next round**, sequential, each live edit its own ⚠ ONAY, and it presents its own node-level plan first.
- D1, D2, D4–D11 as recommended (below).

### §4b · v2 backlog — DEFERRED by ruling, named and reasoned (also README's "not yet / v2" section)
| Item | Why it waits |
|---|---|
| **F5** deploy-separation guard checks import spelling, not reachability | a false-negative guard, not a present leak (Codex found no dashboard-reaching import in the public packages) |
| **F6** hardlink identity substring match | a false POSITIVE (it over-reports), never a missed leak |
| **F9** client-import gate misses `.mts`/`.cts` | no such files exist today; a coverage gap for a future refactor |
| **F10** runtime browser guard is a DOM heuristic | the build-time boundary is the real one; the runtime check is a diagnostic |
| **F11** schema accepts an empty id, an infinite timestamp, a `NaN` spend | no writer produces them today; constraints need a migration file and an operator apply |
| **F13** a capped appointment window can say "Nothing booked ahead" | 1:1 with the Airtable dashboard; needs >100 cancellations in the window to show |
| **K-2** dead config keys (`instagram`, `business.locale`) | no wrong behaviour; README stops claiming "fully config-driven" |
| the `handoffShown` twin in `web/snippet` | a parity-suite blind spot, not a runtime defect |
| W64/W65: the reschedule closed-day and busy rejects give less help than the booking side | an inconsistency, not a defect (D2) |
| a second owner-alert channel or a delivery check | today a Telegram outage is visible only in n8n's execution log; *triaged v2 by judgment — close to "failures must be visible", so it is flagged for Yigitcan to override* (D2) |
| D2 note | the bare-greeting dead end was CLOSED on 2026-09-07 (the clarify class); the "fail-closed in both directions" item is a standing rule, not a work item |
| **(3)** rebooking a just-cancelled identical slot hands off (7-F1 ruling K3, 2026-10-25) | no double booking, only a handoff; the fix changes the event-id scheme or the reconcile branch and needs a real calendar-write spike first; README "Not yet" says it plainly |
| **the reminder for an appointment cancelled inside the mirror-failure window** (D2 triage; 7-F1 ruling K4, 2026-10-25) | the gate (Reminders reads the event before sending) needs a NEW Google credential in Reminders, which holds none today; D2's premise that this was a small change fell |
| **E3: the reschedule orphan alert's old-slot line** (7-F1 ruling, 2026-10-25) | Main is not edited before ship; the change is written, tested offline and kept staged (`n8n/staged/workflow.main.copy.sanitized.json`), and README "Not yet" names the gap |
| **the nightly "purge-error · no_candidates" alert** (7-1 plan, 2026-10-25) | an empty leads table produces it every night (kept behaviour, MIGRATION-PLAN); noise, not a fault. Cheap to change now through `workflow-step.py` and its edit allowlist |
| v3's v2 / LATER bucket (Open items table below, unchanged) | already deferred on 2026-09-17; listed again in README's "Not yet" so the two surfaces agree |
| stale code comments the docs now contradict: `001_init.sql`'s `lead_no` comment (Airtable-era dashboard), the Purge copy's `Compute Purge Cutoff` ("lexicographic compare"; the SQL casts to `timestamptz`) and `Compute Leads Cutoff` ("Airtable has no undo") | the workflow comments are live-workflow edits (gated) → with D6c's rename change; `001_init.sql` is an applied file whose hash is on record, so its comment is corrected with the next schema file, not in place |

### §4d · 7-F1 Round A — what Round B inherits (2026-10-25)
- **Item 13 ✅ live-proven (2026-10-25, after the operator enabled linger; Linger=yes measured):** the old hand-started
  process group stopped by PID → `systemctl --user start` → 200 · bind 127.0.0.1 only · MainPID under the user manager,
  the listener inside the unit's cgroup · the page renders all 4 database reads · SIGKILL of the MainPID → a new MainPID
  and 200 within the plan's ~10 s bound, one restart, no orphan · check-listeners green · enabled. *(Timings were read
  from the session's terminal output, which is not committed.)* **Boot start is shown by
  configuration only (linger + enabled), not by a reboot.** It serves the pre-round-1 build, as planned.
- **⛔ Round B STOPPED at step 1 (2026-10-25), no workflow edited.** The two criticals were fixed (curl in its own
  session; `api()` returns a dead child as a status; the recovery crash prints the restore; the restore target is the
  revision production ran before the edit, found before any write), but the gating review was NOT clean:
  `code-reviewer` **H1** — the printed `--restore` can itself be refused after a structural edit (a removed node that
  carried a placeholder, an added webhook node, a list length or settings change), leaving production inactive with a
  command that does not work; the fix is to dry-run the restore's preconditions for the before-revision before any write ·
  **H2** (with `security-auditor` M1) — `start_new_session` applied to EVERY call lets a hung curl finish a write after
  the helper has died outside the guarded window, which reaches `--turnstile-swapped` (a late "off" PUT after the window
  closed would leave Turnstile off in production); the fix is a new session only inside `_guarded`, plus SIGHUP/SIGTERM
  turned into exceptions process-wide. Also open: M3 (a signal after a proven restore deactivates it), M4 (`_crash`
  on an ACTIVE copy prints a restore that refuses it), M5/L6–L9, auditor L1/L2. The work is kept on the LOCAL branch
  `wip/7f1-roundb-step1` (not pushed, not merged); `main` keeps the reviewed tool with the modes off. The same
  process-group class exists in `scripts/turnstile-window.py`'s own curl and helper call (not changed).
- **Round B re-planned (ruling 2026-10-25): the self-recovering edit tool is abandoned, not fixed.** It failed review
  five rounds in a row, each fix finding a new HIGH — the stop rule's "fix of a fix": the design was wrong. Its lessons,
  kept so the next tool does not repeat them: **H1** a recovery that writes from a revision it never proved restorable
  can refuse itself and strand production inactive; **H2/M1** detaching a child (`start_new_session`) without owning its
  lifetime lets a write land after its parent died; **M3** a signal arriving after a proven restore must not undo it;
  **M4** a printed restore command must be runnable in the state the copy is actually in; **M5** "cannot be killed" was
  claimed for a call that could be. The branch `wip/7f1-roundb-step1` stays LOCAL and unmerged.
  **Replacement tried: single-purpose step commands (`workflow-step.py`: `deactivate` · `put` · `activate`, each read
  back, no signal handling, no automatic recovery) — ⛔ STOPPED, not merged.** First review: two HIGH (the Turnstile probe
  ran on Owner Actions and Drill State, whose gate is an HMAC signature, so their activate could never be green; a
  deleted Turnstile literal passed `put`), fixed once with killing mutants (the test and its mutants are on the local branch, not committed). Second review: two HIGH again —
  **(1)** `put` does not check the trigger's production path or the temporary trigger, so an OLDER revision of a copy's
  own export is accepted and takes the production holder off its path or brings the deleting test trigger back;
  **(2)** the Turnstile gate can still be bypassed by an export: an edge INTO the gate rerouted, a `Load Config` override
  after the literal, execution flags on a gate node. (2) is the SAME defect as the first review's gate finding, so the
  brief's rule "a second fix of the same defect → STOP" applied. The work is on the LOCAL branch `wip/7f1-roundb-steps`
  (not pushed, not merged); `main` has no step commands and the deploy helper's edit modes stay disabled.
  **What the two rounds show, for the ruling:** a guard that tries to RECOGNISE a harmful export (a gate bypass, a moved
  trigger) is a blacklist and stays incomplete, because the export can express the same effect many ways. The complete
  form is the opposite: a per-edit ALLOWLIST of the node names an edit may change (e.g. E1 = the two builders and the
  three leads nodes), with `put` refusing any other difference against the committed export: nodes, edges, flags,
  settings, triggers. A semantic bypass inside an allowlisted node stays a review question (L2/Codex read that diff).
  **`--turnstile-swapped` on main, read for this ruling:** its `api()` runs curl as an ordinary child (no new session),
  so H2 does not exist there; a signal to the operator's process group reaches curl too. **`scripts/turnstile-window.py`,
  recorded:** its own curl and its helper call are ordinary children as well; the helper call has a 300 s timeout that
  kills only the helper, so a helper hung past it while a curl (≤ 60 s) is in flight could let that one request finish
  after the close began. The close re-reads the draft literal after its deactivate, which covers a write that landed
  before the read but not one that lands after it. Residual, low (it needs a helper hung for five minutes), not fixed.
- **Round B, final shape (ruling 2026-10-25): the allowlist through the REVIEWED diff tool, E1 + E2 only.**
  `scripts/diff-workflow-copy.py --phase edit` compares the copy's COMMITTED export with the staged one: only the named
  nodes may differ, and in them only `parameters` and `alwaysOutputData` (*declared:* that one flag is allowed because
  item (2)'s fix IS removing it; type, typeVersion, credentials, onError, disabled stay); a trigger can never be named;
  nodes added/removed, connections, settings (strict, even if a live-mode allowlist is passed) and every other node are
  red. 15 edit-phase selftest cases beside the 22 existing ones; code mutants were run red (their runs are not committed). `scripts/workflow-step.py` holds
  ONLY the three calls with read-backs (`deactivate`, `put … --allow N…`, `activate`); `put` runs that diff before any
  write and `content_drift` (live == staged) plus a raw comparison with the body sent after it. Scope: copies without a
  webhook trigger or a Turnstile gate (Purge, Reminders); Main is not edited before ship, so **E3 (the orphan old-slot
  line) moves to v2**. The edit allowlists: **E1** = `Aggregate Leads Total`, `Build Owner Alert (Purge)`, `Count Leads
  After`, `Count Leads Total`, `Find Old Leads`, `Leads Purge Sane?`, `Verify Leads Purge` · **E2** = `Build Owner Alert
  (Reminders)` (measured: the staged exports differ from the committed ones in exactly these nodes, connections and
  settings equal).
- **Declared: Round A's push left `check-exports-parity` red** (the committed `n8n/staged/` exports have no pair; the
  pre-commit run saw them untracked). Fixed in Round B: the guard excludes `n8n/staged/` by name. *Lesson: a guard
  that reads git's index must be re-run AFTER the commit, not only on the working tree before it.*
- **⛔ `--engine-edit` and `--restore` are DISABLED** (`ENGINE_EDIT_ENABLED = False` in `scripts/deploy-workflow-copy.py`;
  `main()` refuses both before any API call, and a selftest proves the refusal). Three code-review rounds hardened the
  edit path; the fourth still found two CRITICAL recovery defects, so per `make-the-error-cheap` the mode ships OFF
  instead of a fourth patch in the same turn. **Round B's first step closes them and gets a clean review before E1:**
  (1) curl shares the process group, so a second Ctrl-C or an ssh drop during recovery kills it, `api()` raises on the
  empty output, and the recovery-exception branch leaves the copy INACTIVE without printing the restore command —
  `api()` must return a dead child as a status, and that branch must print the restore; (2) the printed `--restore`
  revision is the failed edit's, not the revision production held before it — it must be the committed revision live
  equals before the deactivate (refuse the edit when none does). Lower items from the same review: the handler is
  installed before the signal list is cleared; a signal recorded during the probe is lost on exit 0; an unnamed list's
  index shift could fill from the wrong path (none in today's exports; fails closed for strings, not for `__rl`); the
  SAFETY message's runnable restore command prints real workflow ids and a commit hash — add a "mask before pasting
  into a report" line when re-enabling (security-auditor LOW-1).
- **Staged edits — outcome (2026-10-25; measured in the session's terminal, output not committed):** **E1 (Purge: Q18 +
  (2)) and E2 (Reminders: Q18) are LIVE.** Each: content
  parity live == committed → `diff-workflow-copy --phase edit` green on its allowlist → `workflow-step.py deactivate` →
  `put` (read back == staged) → the draft re-read == staged right before `activate` → `activate` (published == draft) →
  content parity live == staged → the staged file promoted into the committed export in the same commit → both parity
  guards green AFTER the commit → Turnstile 403. The two offline tests now read the committed exports.
  `n8n/staged/workflow.main.copy.sanitized.json` (the orphan old-slot line) STAYS staged: **E3 is v2** (README "Not yet").
- **(2)'s two live premises, MEASURED 2026-10-25** (terminal output, not committed; within E1's approved scope, which
  named this read-only probe; a temporary read-only workflow, the S10 pattern: an Access-covered
  `owner-mig-p7-` path, edge refusal shown with both signals, webhook-triggered, SELECT only, the Purge copy's own
  Postgres credential, deleted afterwards and GET 404): a READ error under `continueErrorOutput` WITHOUT
  `alwaysOutputData` left **0 items on output 0** and 1 on output 1 (keys `error`, `message`); the staged `jsonb_agg` SQL
  returned a **JS array** (empty window: length 0; a constant two-element aggregate: two strings) and `count(*)::int` a
  **number**. Q18's offline proof stands as labelled: "offline-proven, error shape measured live (S10, M7)".
- **E2's first scheduled run on the new code (terminal-measured, not committed):** trigger mode, status success, 6 nodes,
  no node error, the Zernio send not reached. **Its limit, stated:** `Find Due Appointments` found no due row, so the run
  stopped there; neither the dry-run send path nor the edited `Build Owner Alert (Reminders)` ran. The edited builder is
  proven offline only (Q18's label stands).
- **Soak items (not yet observed):** the Purge copy's next nightly run on the new code; a Reminders run that has due rows
  or a store error (the first that exercises the edited builder live).
- **Declared mechanical faults in E1, fixed and committed:** the deploy helper's selftest built its "export drops
  `alwaysOutputData` while live keeps it" fixture from a node carrying the flag in the committed Purge export; E1
  removed the flag, so the fixture raised (and one case had been skipped silently wherever an export carried no flag).
  It is now built on the live side for all five copies. The step-command test read the staged Purge export, which E1
  removed; it now synthesises its edits from the committed exports. `check-import-safe.py` crashes on a bare file name
  (`dirname('')`); run it with a path (not fixed).
- **`tests/db/copy-contract.cjs`** (operator-run, live) expects record rows from the three changed leads reads; before
  it is next run, those three checks become "one row; an integer count / an `ids` string array".
- **D6c needs a ruling for the guards:** the window's ORDER guard, the production path and the settings parity all read
  the parked original; when it is deleted they lose their source (proposal on record: the path from the export and the
  live copy, the ORDER guard from ROLES alone).
- **The edit path's rule:** an engine edit never changes a masked value; placeholders are filled from the live copy at
  the same path, and a placeholder with no live counterpart is refused as an operator step.
- **Open, not fixed this round:** `check-cancel-validation-parity.py` skips a missing Reminders/Purge export silently
  (`FileNotFoundError` → `continue`); the parity projection still does not compare the four execution fields (only the
  edit path does).

### §4e · 7-1 — plan approved 2026-10-25 (rulings K1–K8); Round 1 STOPPED (driver not clean)
- **Rulings:** K1 the seeded ⚙ scenarios run in the window · K2 auth-strip/config-edit scenarios stay out (Main is not
  edited before ship; label "Airtable era, topology unchanged") · K3 one seeded due appointment: the first live proof of
  the Reminders dry-run + stamp path on Postgres; the edited builder is fed ONLY by `Reminder Error (lookup/stamp/send)`,
  so it stays offline-proven (Q18's label holds) · K4 a 1.00 USD ceiling · **K5 (changed at approval):** no manual quota
  reading; the planned Calendar calls are counted and compared with Google's documented default quotas, and any quota
  error closes the window · K6 the DST booking's slot (not a window time): Mon 2027-03-29 15:00 Vienna · K7 ≤ 25 minutes, no new turn after minute 22, AND any
  request on the production path that is not the driver's closes the window · K8 one ⚠ ONAY block for Round 2.
- **Round 1 ⛔ STOPPED (2026-10-25): the window driver did not pass review; nothing live ran.** Built offline and parked
  on the LOCAL branch `wip/7-1-driver` (not pushed, not merged): `tests/run-7-1.py` (phases harness → 11 seeded ⚙ →
  race pair → DST, run as the window script's command, five stops) and its 106-case offline test. Review history, each
  HIGH fixed once with a killing mutant: **1st** — a hung salon_ro read blinded the guard while the harness ran out of the
  window's group kill; an unreadable execution was never judged; real events were cancelled only on the happy path ·
  **2nd** — a red path check in the race could lose a double booking before it was read · **3rd (the declared stop)** —
  the fix for "judge only finished executions" used n8n's `finished` field, which is true only on SUCCESS: an execution
  that ended in error (`finished: false`) was treated as still running and never judged, so a foreign or outbound
  execution would stop the run only at its end (premise from n8n's semantics, not measured here; one read of a known
  failed execution settles it). Also open from the 3rd round: the race's double-booking label can be lost when another
  STOP is already propagating (exit 3 still holds); `check-import-safe.py` cannot see this driver's live calls (it loads
  them through `importlib` and `node -e`), so its import-safety rests on reading, not on the gate.
- **What stands without the driver:** the rulings above; the Calendar-call count, an offline output of the parked
  driver's `--plan` (≤ 220 calls in the window, ≤ 60 per minute, the race pair ≤ 8 at once) against Google's documented
  defaults (Calendar API "Manage quotas", developers.google.com/workspace/calendar/api/guides/quota, last updated
  2026-09-11: 10,000 requests per minute per project, 600 per minute per user per project; exceeded → 403 or 429
  `usageLimits`); the finding that the edited Reminders builder is fed only by its error branches (K3).
- *Declared in the parked driver, carried to the next attempt:* #28 seeds its booking instead of booking it through the
  bot (its past-guard locks the session in handoff, so a real event booked there could not be cancelled).

### §4f · 7-1 re-shaped and RUN (ruling 2026-10-25): one short window for what is new — ✅ green
*Measured in the session's terminal, output not committed. Ruling: no committed driver; the full suite is NOT re-run
(D4b ran it 28/28 on the same Main copy's test path; A1/A2/A3 covered the production path); ONE window ≤ 10 minutes
through main's reviewed `scripts/turnstile-window.py`, an import-safe scratchpad sequence, a 1.00 USD ceiling.*
- **Preconditions:** Turnstile 403 · Main live == committed (content parity) · the sequence import-safe.
- **The window: 89 s** (opened and closed by the committed script; restored and measured both ways — published literal
  true, a dummy token 403 through the copy, none through the original). 10 requests, 0.022986 USD. Calendar calls in the
  window bounded at ≤ 14 (2 availability asks + 2 confirms at ≤ 2 calls each + 2 withdrawals for the race; 1 + 2 + 1 for the
  DST booking and its cancel; 2 freeBusy asks), within the brief's ≤ ~20 budget.
- **The race pair (expectation written before the run, §4e plan):** both confirms released together; **the two
  Book → Verify write spans overlapped in time — a truly simultaneous pair.** Result: **both writers withdrew** — the
  documented symmetric limit: no double booking and no booking. `Check Race` ×2 · `Build Orphan State` 0 · events
  created 2 = withdrawn 2 · 0 booked rows on the slot, read right after the confirms · both replies "just taken" (a
  human follows up). **GREEN against the written expectation.**
- **The DST booking:** Mon 2027-03-29 15:00 Vienna (after the spring change) stored at **13:00Z (+02:00)**, then
  cancelled through the flow (`Delete Booking Event`).
- **After the window:** every Main-copy execution from open to close was this run's (10) or the window script's own
  closing probe (1): **no foreign traffic**; Zernio 0; no Calendar quota error; both drill slots read free through the
  bot's own availability check.
- **Outside the window — the Reminders dry-run + stamp path, first live proof on Postgres (K3):** one due appointment
  seeded through the committed seed tool (edge check first); the next hourly run: success · `Find Due Appointments` 1
  item · `Reminder Send (dry-run)` ran · `Stamp Reminded` succeeded, the row reads `reminded = true` · `Send Reminder
  (Zernio Template)` did not run. The edited `Build Owner Alert (Reminders)` did not run (no error), as expected: its
  proof stays offline (Q18's label).
- **Cleanup:** the seed tool's prefix-guarded `clean` removed 5 conversations, 2 appointments, 10 processed markers, 0
  leads; the seed workflow deleted (GET 404); every table holds 0 rows under the p7 prefixes. The month's `bot_metrics`
  row is kept (the spend meter).
- **Not re-run, labelled (README):** the seeded ⚙ scenarios — their paths are covered by D4b G1–G3 and M7.

### §4g · 7-2 R3 — the live window (brief 2026-10-26, its own ⚠ ONAY) — ✅ green, one gap
*Measured in the session's terminal, output not committed. Every live step through the committed tools
(`scripts/workflow-step.py`, `scripts/turnstile-window.py`, `scripts/seed-workflow.py`, `tests/run-d11.sh`) and three
import-safe scratchpad drivers; spend ceiling 1.00 USD; not in the Reminders or Purge windows; no manual execution (Q13).*
- **Prelude** `a0a337d` (a missing edge type refused · the DOC12 sentence · §9 rows), prep `6deb684`/`eca838d` (the delta
  tests keep a baseline across the promotion; a two-stage promotion simulated clean first).
- **Two tool defects the rehearsal found before any production write, each fixed by ruling:**
  - `acba229` — the deploy helper refused the APPROVED Owner Actions delta: n8n gives Telegram nodes a webhookId and
    `fill_by_path` refused any dropped node carrying one. Ruling: only a NON-trigger node in the approved `remove_nodes`
    may drop it (the trigger test is diff-workflow-copy's own). The offline fake had no webhookIds on these nodes (the
    Owner Actions exports carry none), so it could not produce the defect; it carries them now.
  - `f635477` — the rollback after `settings` read back with ONLY the settings different from the snapshot (read as a PUT
    not undoing `saveDataSuccessExecution`; the value was not printed). Ruling: that setting is FORWARD-ONLY; rollback's
    settings equality ignores exactly that key, value "none", absent from the snapshot, Owner Actions only. Consequence,
    stated: after such a rollback the copy is not its committed export; and `probe` counts executions, so the check after
    `settings` is a body probe (ruling: unsigned 403 `invalid_signature`, signed unknown record 404 `not_found`, 0 new
    executions on the original).
- **Dashboard:** rebuilt and restarted; loopback 200 · bound to 127.0.0.1 only · cross-site `text/plain` POST 403 ·
  same-origin JSON `{}` 400 · export 404 with the flag off.
- **Owner Actions:** rehearsal on a scratch green (put · settings · rollback == snapshot except the forward-only key —
  which measured that key as the ONLY leftover) → deactivate → put (snapshot S1) → activate → probe (unsigned 403,
  signed unknown record 404, copy 2 executions, original 0) → one seeded `stage=handoff` conversation → `run-d11`
  **15/15** (the duplicate pair: exactly one execution wrote the release; the ts in the signed body reaches `Release
  Handoff Lock` as the same integer) → deactivate → settings (S2) → activate → body probe (403 · 404 · original 0; the
  copy saved 0 executions — success data off) → promoted at **`43754f8`**.
- **Main:** rehearsal on a scratch green → deactivate → put (S3) → activate → dummy-token probe 403 → promoted at
  **`784cdd8`** (before the window: its precheck compares the live copy with the committed export) → **one Turnstile window,
  72 s**: booking → reschedule → cancel in one session (the A1 routing smoke plus the three actions) and one explicit
  handoff turn in another; every request's `processed_messages` row read as `salon_ro` (8/8); booked rows 1 → 1 → 0;
  0.020 USD. Closed by the script, restored and measured both ways (published literal true, dummy token 403 through the
  copy, none through the original).
- **After the window:** 8 executions in it, all this run's (no foreign traffic) · Zernio 0 · no Calendar quota error ·
  events written 2 (booking, reschedule) = deleted 2 (the old slot, the cancel) · the handoff alert reached Telegram with
  its sender MASKED (the full session id not in the text — item 13) · 0 booked rows left under the run prefix.
- **Clean-up:** the seed tool's `clean` removed 3 conversations, 1 appointment, 9 processed markers, 0 leads; the seed
  workflow deleted (GET 404); every p7 count 0. The snapshots S1–S3 deleted after the records.
- **Parity after the window:** `check-exports-parity` 10/10 with the 5 pairs as declared; content + settings parity of the
  Main and Owner Actions copies against their NEW exports OK.
- **The export flag, last:** `DASHBOARD_EXPORT_ENABLED=1` in the unit at **`e899592`**, installed, restarted: both
  exports answer 200 `text/csv` with the masked-export columns. ~~**⚠ the export's live sample was empty (0 rows in the store): "no unmasked phone in a sample" is recorded as a gap, not counted as closed.**~~ → **closed in 7-2 R4 (§4h).** The masking is covered by the dashboard's
  offline tests.
- **Declared:** the handoff turn was not in the brief's drill list; it was added to give item 13 an alert to measure.
  A first content-parity call without a workflow id compared the wrong workflow (red, harmless); repeated with the id.

### §4h · 7-2 R4 — the export gap closed live, CONVERGE disposition, docs, cleanup (brief 2026-10-26)
*Measured in the session's terminal, output not committed.*
- **Start, read-only (ruling 2026-10-26):** the Main copy's PUBLISHED graph equals its committed export (content drift
  0, connections equal; settings differ only in `binaryMode: "separate"`); its DRAFT differs from published only in three
  sticky sizes (and 179 node positions — the editor's auto-layout, Yigitcan's; non-executable, not compared by parity).
  `check-exports-parity` red on `workflow.main.copy` for that alone, every other export green; dummy token 403. n8n's
  `activeVersion` carries no settings, so `binaryMode` applies to the running workflow (behaviour-neutral by the D3
  reading). Reconciled in D6c (ROADMAP). R4 wrote nothing to Main.
- **The export gap, closed live.** The seed tool had no lead insert and no customer name: added (`68f3498`), hardened
  after review (`b0f16c5`: every payload key asserted in the statement's recordset/INSERT/SELECT; per-action options; a
  red response prints keys only); 10 mutants red; security-auditor GO. Live, through the committed tool, values passed
  IN-PROCESS (none on a command line): one appointment (`customer_name`: a plain and a zero-width-split phone) and one
  lead (`name`: an Arabic-Indic and a line-break-split phone; `phone`: +43 spaced), start in 2030 (outside the Reminders
  window). Read back as `salon_ro`: all three fields NOT NULL, lengths equal to what was sent (41 · 32 · 15 — the unicode
  survived the jsonb path). Both CSVs via loopback: customer `Mila 06…67 Z. 06…67`, lead name `Noor ٠٦…٦٧ Q. 06…67`, lead
  phone `'+43…67` — every masked form equal to the token the golden table gives for the same input class (the line-break
  form maps to the single-line row because a name is printed on one line), the longest digit run after normalisation 4
  (the raw synthetic values give 11: the instrument can go red). Clean: 1 appointment, 1 lead; every p7 count 0; the seed
  workflow 404. One permanent trace, stated: `leads.lead_no` (an identity) advanced by one.
- **CONVERGE (Yigitcan):** fixed — the scanner reads content lines starting with `++` (engine and working-tree filter)
  and detects an n8n encryption key and a postgres(ql) URL with a password (`1ce20e7`; the review's LOWs in `bc07ea8`: a
  header control that can fail, the `postgresql+asyncpg://` scheme, ordered seed columns). Full history scanned before
  and after: 0 new hits; seven mutants of the kept fixes, each red. **The hook refusal of `--no-verify` / core.hooksPath
  was built and DROPPED by ruling:** three versions (`1ce20e7`, `34c9065`, `595416f`) each drew a review finding — the
  last two a security NO-GO, each letting through forms its predecessor caught (11 confirmed end to end with real git) —
  and a text rule would block ordinary commands; the code and its test are removed (R4 drop commit), and the bypass is
  guarded by habit (`remote-operator.md`). The rest → v2 (README).
- **Docs (text only):** claim-first idempotency in booking-integrity §1, DATA-MODEL, the schema comment, FLOW-DIAGRAM,
  the regression suite and the snippet comment (its bundle unchanged: byte-identical rebuild) · the D-c wording (an
  alert never changes the reply but can delay it) in FLOW-DIAGRAM and UX-ARCHITECTURE · the 7-2 alert classes in
  UX-ARCHITECTURE, SCREEN-INVENTORY and FLOW-DIAGRAM (`race_lost` alerted now; `dedupe_marker_failed` gone) · handoff
  (five classes), n8n-conventions (Postgres) · remote-operator (the pre-flight parse now strips quotes like the guard;
  the live-snapshot lifecycle) · security-auditor (the git pre-push gate, expected drift, NO NETWORK) · eight decision-log
  rows · OPS-7/8/9 · item 13 closed · README v2 rows · ROADMAP disposition and the Main draft difference.
- **Not changed, named:** the Owner Actions canvas text `Sticky — 3` lags the release conditions — a live write, it rides
  D6c's put with the Main reconciliation.

### §4c · Decisions ruled at approval
| # | Decision | Ruling |
|---|---|---|
| D1 | CRT #1b drift | §9 stays `[ ]`; the 2026-08-16 "CLOSED" is the Airtable-era audit; it closes after the simultaneous drill (7-1) and Codex (7-2) |
| D2 | the older named items absent from this plan | triaged in 7-D7: correctness → 7-F1, the rest → §4b |
| D3 | rename the production workflows | → D6c (amendment) |
| D4 | Phase 7 prefixes | `w-mig-p7-` / `mig-p7-` (the existing prefix-guarded clean-up covers them) |
| D5 | Q18 verification | offline unit test of the builder code from the committed export; the fix is a gated edit; no operator REVOKE window |
| D6 | the "break the table" setups (#35, SC3, E-*) | out of 7-1; covered by the M7 window evidence and offline unit tests |
| D7 | the owner export | dashboard CSV behind Access, appointments + leads, the panels' masked columns; no sheet snapshot (a second PII copy at a third party); full contact data only after Q16 |
| D8 | the dashboard's supervision | a systemd user unit with linger (one root command by Yigitcan) |
| D9 | tests outside `check-all` | `validate-intent.test.cjs` joins; `secret-scan` stays a hook |
| D10 | the Access session (#12) | 24 h, applied in the final security pass |
| D11 | golden-set size | 15 cases in 7-3, run in 7-4 |

---

## §5 · SKELETON
- 7-D7: the six governance files and three test docs above; this file.
- 7-F2: `web/dashboard/lib/store.ts` + `store.test.ts` (F4, F7, F12), the export route under `web/dashboard/app/api/` and
  its tests; `scripts/package.json` (`validate-intent` in `check-all`).
- 7-T: `scripts/turnstile-window.py`, `scripts/seed-workflow.py`, their offline tests under `tests/unit/`,
  `tests/regression-suite.md`.
- 7-F1: its own node-level plan (MAIN copy nodes `Build Owner Alert (Purge)` / `(Reminders)` and the named items'
  nodes; the dashboard's service unit).
- 7-3: `docs/CASE-STUDY.md`, `docs/RUNBOOK.md`, `tests/golden-set.md`.

## §6 · INTEGRATIONS
n8n API (reads; gated edits in 7-F1) · Postgres (`salon_ro` reads; writes only through the seed workflow) · Google
Calendar "Salon Bookings" (bookings and cancels inside the 7-1 window) · Anthropic (window spend cap) · Telegram (owner
alerts) · Cloudflare (Access reads; panel changes by Yigitcan) · Codex (7-2).

## §7 · MOCK DATA
Session and message prefixes `w-mig-p7-` / `mig-p7-`; slots ≥ 24 h ahead in shop hours; seeded rows through the
committed seed tool only; prefix-guarded clean-up with the before/after counts shown; the month's `bot_metrics` row is
the production spend meter and is never deleted; golden-set and jailbreak inputs are synthetic.

## §8 · CRITICAL-REVIEW TARGETS — each with its runnable check
| CRT | Criterion | Runnable check |
|---|---|---|
| 1a idempotency | 4 | migration evidence (D4b #3, `run-d11` replay) + Codex (7-2) |
| 1b concurrency | 4 | 7-1's simultaneous pair: `appointments` booked rows on the slot via `salon_ro`, `Check Race` / `Build Orphan State` from the executions; A3 is the sequential evidence |
| 2 Calendar write | 1 + 2 (quota) | 7-1's bookings: events created = deleted, the slot's freeBusy empty; the quota counted before the window |
| 4 secret / PII | 3 | `bash scripts/secret-scan.sh </dev/null && bash scripts/check-no-host-leak.sh` + Codex |
| 5 handoff threshold | 1/5 | the regression's uncertain-turn scenarios + `conversations.stage` via `salon_ro` (`COALESCE`) |
| 6 error visibility | 5 | the M7 window evidence + Q18's offline unit test (7-F1) |
| 9 dashboard auth | 3 | ship gate 18; K-6 measured the session-less 302 and the one-email allow policy |
| 11 D11 write path | 1/3 | `run-d11.sh` 13/13 on the production paths (A2) + the #11 drift reconciled |
| 12 date resolution | 1/4/5 | `node tests/unit/resolve-date.test.cjs` + Codex on the five R3 items |

## §9 · ACCEPTANCE CRITERIA
1. Every open CRT row is closed, or the reason it cannot close is written.
2. `check-all` 0, including the new tests.
3. The 7-1 window under K-1's label ("tested — gate lowered for the duration of each run, restored and measured after
   each"), Turnstile measured both ways.
4. Golden-set (15) and jailbreak run; results recorded.
5. `docs/CASE-STUDY.md` and `docs/RUNBOOK.md` exist; RUNBOOK dry-run, labelled "NOT run end to end".
6. The dashboard comes back on its own after a restart (supervised).
7. The owner export returns masked columns only, behind Access, and goes live only after 7-2.
8. The 12 security-pass items closed or ruled; nothing dropped silently.
9. The "tested" DoD carries two lines (K-5); the resume-point memory written AND read back.

## §10 · DRILL MATRIX
| Scenario | Where | MUST-RUN | MUST-NOT-RUN |
|---|---|---|---|
| truly simultaneous race pair | 7-1 | `Check Race` ×2 | `Build Orphan State` |
| idempotency | migration evidence + regression #3 | `Check Processed` | a second `Book Appointment` |
| prompt injection | 7-4 jailbreak | handoff | any write |
| uncertain turn (1st clarify, 2nd handoff) | regression | `Mark Handoff` on the second | `Book` |
| invalid LLM output | `validate-intent` (in `check-all`) + regression | the `extraction_invalid` flag | a `stage` write |
| DST | 7-1 | the right wall-clock time | — |
| Q18 alert detail | 7-F1, offline unit test | a readable detail | `[object Object]` |
| dashboard restart | 7-F1 | the service comes back | — |
| PII in the export | 7-F2 offline, 7-2 audit | masked columns | a raw phone or name |
| F6 date said on the confirm turn (7-2 Tur 2) | **needs a LIVE booking** — in dry-run `Build Dry-Run Booked State` runs, which is not a clean booking, so no `date_changed_on_confirm` alert fires (ruling R1c FLOW L2) | `Build Booked State` → `date_changed_on_confirm` with the date line | a second booking on the said date |

## §11 · AUTOMATION-FIT
`/goal` only in 7-F2's offline loop (goal: `check-all` 0). Not for gated writes, live windows or audits. `/loop`: none.

## §12 · NOT-BUILD
- Opening the WhatsApp lane (Zernio stays closed); K-5 stays a "not tested" line.
- Lowering Turnstile outside a window, or a second window beyond the one planned.
- Re-running what the migration proved (CRT 1a/6/8/10/11 evidence, `run-d11` 13/13, the sequential race).
- A second store or a dual write for the owner's data (Postgres is the single source of truth).
- New product features beyond the two new items; tags; D6c itself (the migration's).
- Screenshots or the Loom before D6c.

---

## Open items — v3's four buckets, kept verbatim (v4 routes each: §4 for PHASE 7, §4b for the v2 backlog)

| Bucket | Items | One-line reason |
|---|---|---|
| **PHASE 7** | **MANDATORY, carried from the migration (Yigitcan's ruling, 2026-10-20; MIGRATION-PLAN §3p, Q18):** `Build Owner Alert (Purge)` and `Build Owner Alert (Reminders)` must read a Postgres error item that has no `message` key (under `independently` the detail value is `[object Object]`, which the owner sees as `detail: -object Object-` after the builders' markdown escape, and the SQL reason is lost; measured on these nodes' own `continueErrorOutput` configuration by S10, MIGRATION-PLAN §3r) · the regression's Turnstile blocker · CRT 1a/1b/2/4/5/6/9/11/12 · `CASE-STUDY.md` · `RUNBOOK.md` · K-2 dead keys · the §9 #11 drift · the `handoffShown` twin (the parity suite stays green if one caller is deleted) · `golden-set`/`jailbreak` never run · **two more, NAMED (Yigitcan's ruling, 2026-10-22; MIGRATION-PLAN §3r, K-3 result; both exist in the originals, so they are not migration regressions):** (1) a release failure reaches the dashboard as the edge's generic `error code: 502`, not the `release_failed` JSON (503 and 404 bodies pass): the dashboard must decide on the status code, and where the body is replaced (Cloudflare's edge or the tunnel) is measured there; (2) a leads READ error also emits a spurious `no_candidates` alert next to the real errors, because `alwaysOutputData` on `Count Leads Total` / `Find Old Leads` leaves an empty item on output 0 · **two more, NAMED (Yigitcan's ruling, 2026-10-23; MIGRATION-PLAN §3s, D4b result; both exist in the originals, so they are not migration regressions):** (3) a customer who cancels and then rebooks the exact same slot and service is handed to a human: Google answers 409 `duplicate` because the deterministic event id stays reserved by the cancelled event, and the reconcile step correctly refuses a cancelled event; the fix belongs to the event-id scheme or the reconcile branch; (4) on a session's FIRST turn an owner alert's `Find Conversation Row` runs before `Save State` has created the row, returns 0 items, and `Record Alert Class` does not run, so that alert's class is not stamped on the row (`last_alert_class` / `last_alert_at`, which the dashboard's alert state reads). *Corrected 2026-10-25 (ruling K2, 7-F1 plan): this said "the alert's throttle is not recorded", and that was wrong — the throttle lives in the workflow's static data and `Build Owner Alert` records it BEFORE the send, first turn included (read in the Main copy export). What is missing on a first turn is only the row's stamp, because the row does not exist yet; no workflow change.* · **one more NAMED item and one observation (Yigitcan's rulings, 2026-10-23; MIGRATION-PLAN §3s, D4c):** (5) the infra alerts fed by a data node's error item (`Send Error Response` and its siblings) must build `sender`, `channel` and `stage` from node references: the error item carries only `{error, message}` (the same on Airtable, exec 84), so today the alert reads `sender: unknown` and one throttle key, `state_unavailable:unknown`, covers every customer; (observation) when only the spend READ is refused, `Record LLM Spend` fails too (`INSERT … RETURNING` needs SELECT), so that turn's cost goes uncounted, visibly (the `spend_meter_unavailable` alert); a real outage fails the read and the write together, as on Airtable · **nine more, NAMED: Codex's CRT #10 re-audit of the Postgres dashboard (at `59009e7`; Yigitcan's rulings, 2026-10-24; MIGRATION-PLAN §3t, Round 3b). Current behaviour holds per Codex (no browser credential leak, no request-controlled SQL); the static proofs are weaker than claimed:** (6) **F4** a behaviour-based store test (a mocked driver recording what is actually sent, every export called with arbitrary arguments) in place of the source-text checks, which Codex kept green with twelve proxy mutants; (7) **F5** `check-deploy-separation` checks import spelling, not reachability (a split specifier, a computed import, an alias, a new public package or a CSS import passes); (8) **F6** its hardlink comparison is a substring match (a false positive); (9) **F7** trim the five non-PII context columns no panel draws (appointments' `end_utc`, `reminder_sent`, `created_at`; leads' `created_at`; the queue's `stage`); (10) **F8** rendered text IS in the RSC payload, the release button receives the masked label, and dev mode serialises the error message: the comments that say otherwise get corrected; (11) **F9** `check-client-imports` does not enumerate `.mts`/`.cts`; (12) **F10** the runtime browser guard is a DOM-presence heuristic, the build-time boundary is the real one; (13) **F11** the schema accepts an empty id, an infinite timestamp and a `NaN` spend, which the panels then misread; (14) **F12, 1:1 with the Airtable dashboard:** the handoff queue's cap (a page of 100, `LIMIT 101`) is applied before its unconfirmed-first ordering, so an old unconfirmed handoff can sit behind a hundred newer confirmed ones and never show; (15) **F13, 1:1 with the Airtable dashboard:** a capped appointment window can say "Nothing booked ahead" when cancellations fill the first hundred | all of them are inside the definition of "test + audit + DoD" |
| **SHIP GATE** | 11–20 (one numbered list in `ROADMAP.md`) | needs deployment or Yigitcan's hands; not build work |
| **v2 / LATER** | `Idempotent Replay` stored reply · `messageTemplates` schema requirement · transcript loss on navigation · font subsetting · `Customers` table · BULGU-4 · R2 · the W57/W58/W60 text mismatch | improves the product but does not change whether it can be sold |
| **DELETE** | *(empty)* | every open item belongs to a bucket or is already closed; an invented "delete" bucket would be padding |

---

---

## History — v3's measurements and rulings, kept as records

## M1 · IS TURNSTILE ACTUALLY ON RIGHT NOW? — measured 2026-09-17

**YES. There is no live gap.** Asked two independent ways, because a config value and a behaviour are
two different claims:

- **Config:** the live `Load Config` carries `turnstile: { enabled: true }` in **both** the draft and
  the **published** graph — the one the webhook actually runs.
- **Behaviour:** a real widget-shaped request with a dummy token returns
  `403 {"ok":false,"error":"turnstile_failed"}`.

**Why this was asked at all, and it was the right question:** `run-regression.sh` passes only with the
gate down, so if anyone had flipped it for a drill and not flipped it back, that would not be a planning
item — it would be a live exposure of the same shape as the dev server this repo left listening for 37
hours. It was flipped back. **Nothing to fix; the check is recorded so the next reader does not have to
wonder.**

## M2 · WHAT THE ENGINE DOES TODAY ON A LOST RACE — measured 2026-09-17

The drill matrix's expected value was *"one booking + handoff"*, taken from `booking-integrity.md`'s
design intent and **never measured**. Measured from the live graph, the real behaviour is **richer, and
one branch the matrix never named**:

```
Verify Slot ──► Check Race ──► Race Gate ──┬─ true  ─► Cancel Our Event ─┬─► Build Race-Lost State ─► Save State (Post-Write)
                                           │                             └─► Build Orphan State
                                           └─ false ─► Write Appointment
```

- The **winner** writes the appointment.
- The **loser**'s calendar event is **cancelled**, and `Build Race-Lost State` sets
  `stage: 'handoff'`, clears `gcal_event_id` and writes a `computed_reply`.
- ⚠ **`Check Race` FAILS CLOSED, and this is the part the old expected value would have mis-read:** if
  the calendar list came back paginated (`nextPageToken`) or in a different timezone, it sets
  `race_lost: true` with **`race_other_count: -1`** and `verify_incomplete: true`. So a handoff can be
  produced by an *incomplete verification* rather than by a real race. A drill asserting only "handoff
  appeared" would pass for the wrong reason.
- ⚠ **A third outcome exists:** if `Cancel Our Event` FAILS, the loser goes to `Build Orphan State` —
  neither booked nor cleanly cancelled. The matrix named two outcomes; the engine has three.

**MEASURED EXPECTED VALUE for the drill (this replaces the assumed one):**
1. exactly ONE `appointments` row with `status='booked'` for that slot;
2. the loser's `conversations.stage = 'handoff'` with `gcal_event_id` cleared;
3. the loser's calendar event **cancelled**, not orphaned;
4. **`race_other_count >= 1`** — this is what separates a REAL race from a `verify_incomplete` handoff,
   and without it the case is not evidence;
5. `Build Orphan State` did NOT run.

⚠ **This is a STRUCTURAL measurement, not a behavioural one.** It says what the graph does; it does not
say what happened, because firing two concurrent widget bookings needs the Turnstile gate — which is
exactly CP 7-0. The behavioural confirmation belongs to CP 7-1 and is not claimed here.

---

## CP 7-0 · RESULT — measured 2026-10-18 (round 1 of 2) · ⛔ STOPPED for a ruling before 7-1

**Verdict: a real-token path for the automated suite is NOT POSSIBLE from this machine, and every
remaining route either changes the security model or tests only a sliver. Per the plan: no redesign —
stop and report. K-1 applies.**

### The measurement — a 2×2, each cell in a FRESH headless browser

| | Cloudflare's always-pass test key | the REAL site key |
|---|---|---|
| `127.0.0.1` | ✅ token minted | ❌ **error 600010** |
| `localhost` | ✅ token minted | ❌ **error 600010** |

- **The control is what makes the treatment mean something.** The test key mints on both hostnames, so
  the widget script loads and the harness works; the real key fails on both with the same code. ⚠ *Narrower
  than it first read:* an always-pass test key does not run a real bot-detection challenge, so it proves the
  harness and the script — not that this browser could pass a real challenge.
- **What 600010 is, from Cloudflare's own error-code table, not from memory:** `600*` = *"Generic challenge
  failure — Bot behavior detected."* The hostname-allow-list failure is a DIFFERENT code, **110200**
  *"Domain not authorized"*. We got 600010, so **the measured wall is bot detection, and a hostname change would not
  address it.** ⚠ What is NOT measured: whether the hostname list is ALSO wrong — if bot detection is
  evaluated first, a 110200 could be masked behind it. The conditional recorded earlier on 2026-10-18 is
  resolved only in that narrower sense: no Cloudflare write is indicated by what was measured.
- Getting past bot detection would be detection evasion against our own control. It is not an option.

⚠ **An instrument defect was caught on the way, and it would have produced a false PASS.** The first real-key
run reported `TOKEN len=21`. A real Turnstile token is hundreds of characters (Cloudflare's documentation — no real token was minted in this round to measure it); 21 is exactly the length of
`XXXX.DUMMY.TOKEN.XXXX`, the test key's dummy. The control and treatment URLs differed only in their `#`
fragment, which the browser treats as a SAME-DOCUMENT navigation — the page never reloaded, and the driver
read the control's leftover result. Every cell above was then re-run in its own fresh browser with a query
string. **The token's length was the only thing that gave it away.**

### A structural fact that decides the remaining options

`Turnstile Gate` checks only `channel === 'widget'` and `turnstile.enabled === true` — **there is no
session memory**. Every widget message goes to `Verify Turnstile`, and a Turnstile token is single-use
(Cloudflare's documented behaviour; not separately measured here). **So every message needs a fresh token.**

### The routes, and why none is taken without a ruling

| Route | Status | Why |
|---|---|---|
| (a) real token from this machine | ❌ measured impossible | 600010 bot detection, both hostnames |
| (b) a signed test lane in production (HMAC bypasses Turnstile) | ⛔ **security-model change** | replaces a verification layer on the PUBLIC endpoint for signed requests — a declared stop condition; it would also never exercise `Verify Turnstile` itself |
| (c) human-minted tokens (Yigitcan's real browser) | ◐ a sliver only | one token per message × the harness's own header estimate of "~44 requests" (a comment in `tests/run-regression.sh`, not a count), each single-use and short-lived — workable for two or three targeted drills, not for a suite |
| (d) lower the gate for the run | ⛔ forbidden | NOT-build here, and a declared stop condition |
| (e) **PROPOSED, not adopted:** a drill COPY of Main behind `/webhook/owner-*` with Turnstile off in the copy only | ◐ needs a ruling | production's gate never moves and its security model is untouched; the copy is behind Access Service Auth and active only during a drill. ⚠ The cost is a second truth — a copy that drifts tests something that is not production, the exact defect this repo keeps paying for — so it is viable ONLY with a parity check (every node equal to Main except the Turnstile flag) run immediately before each drill, and it does not prove `Verify Turnstile` itself |

### ✅ RESOLVED — the conflict that stopped 7-0 (ruled by the 2026-10-18 window protocol below; re-confirmed as premise 2, 2026-10-24)

K-1 says: if 7-0 cannot be solved, "tested" closes as *"run only with the gate down"* and the real-token run
becomes **ship gate 21**. But this plan's NOT-build also says **✗ lowering Turnstile for a drill**. Read
together, they leave 7-1 with **no live route at all**: the gate up fails on bot detection, the gate down
is forbidden. Which of these governs 7-1 is Yigitcan's to rule — it decides how 7-1 runs, which is exactly
why 7-0 stops here instead of flowing into it.


---

## WINDOW PROTOCOL — Yigitcan's ruling, 2026-10-18

**The NOT-build line above changed.** Turnstile MAY be lowered **only for the duration of a regression/drill
run**, under this protocol, and for no other purpose. This is the security-model stop condition's
pre-approval **for this scope only**: Turnstile only · the widget lane only · the run's duration only. Any
other security change is still a STOP.

**Why, as ruled:** there is no paying customer; a window lasts minutes; the exposure is "findable but not
being looked for", not hidden. **K-1's label is now the accurate description:** *"tested — gate lowered for
the duration of each run, restored and measured after each."* Ship gate **21** (a run with the gate UP =
Yigitcan's real-browser E2E) stays as K-1 set it.

**Every window, inside ONE turn:** lower → run → restore → **measure that it is restored** (published graph
`enabled:true` AND behaviour: a dummy token → `403 turnstile_failed`). A window never crosses a turn
boundary. Open and close times and the duration are recorded. **Every turn begins by measuring the gate;**
found lowered → restore first, measure, and report it as an INCIDENT at the top.

**How a window is executed (designed 2026-10-18, NOT yet run):** a pre-window raw backup of Main; the flip
changes exactly one token (`turnstile: { enabled: true }` → `false` inside `Load Config`), and the diff is
asserted to be that one token before the PUT; the run sits under a hard timeout; restoration PUTs the
BACKUP's own body (not a re-edit) from a shell `trap`, so it happens even if the run fails or is killed; then
both measurements, then `exports-parity` + `live-parity` to prove Main is byte-equal to the commit again.

## CP 7-0 · STATUS 2026-10-18 — protocol designed, window NOT opened

**The window was not opened, and the reason is not the gate.** Declaring the call budget (step 1) found
that **Airtable has refused every API call since 2026-10-06 22:00 UTC** — the monthly quota is exhausted
(`docs/OPERATIONAL-INCIDENTS.md` OPS-5). With the data layer down, every regression turn fails at
`Load State`: all assertions would go red for the quota, not for the behaviour under test. Control and
treatment cannot separate, which is a declared stop condition — and a window with no evidential value is
pure exposure. **The gate stayed UP the whole turn.**

**Step 1 — measured:**
- **LLM cost cap:** `llmCostCapUsd: 10.00` in the PUBLISHED config (`maxTurnsPerConversation: 12`,
  `killSwitch: false`). The brake reads spend from Airtable; on a read error its path goes only to an owner
  alert and never reaches `Build LLM Request` — **it fails closed**, read from the published graph. ⚠ Its
  BEHAVIOUR (a turn refused at the cap) was NOT measured: that needs Airtable, and lowering the cap is outside
  the approved scope.
- **Call budget — declared, and the declaration is what found the outage:** one window ≈ 52 requests
  (the 46-request suite + 4 for the race drill + 2 for a DST booking), each making several Airtable calls,
  plus counting and K-3 cleanup. Against that, the scheduled jobs' OWN cost — measured from real executions on
  a day with nothing to remind or purge, so a floor — already takes **the large majority of the free plan's
  monthly allowance**. *(The per-turn estimate and the window's total are an ESTIMATE from the graph, not a
  measurement. Exact counts are deliberately kept out of this public repo — combined, they let a stranger
  compute how few widget messages would take the data layer down for a month. Figures are in the round
  report.)*

## 7-1 · WINDOW PLAN (v3) — SUPERSEDED by v4 §4 (7-1); kept as the record of the Airtable-era budget, never run

**First criterion, as asked: the fewest windows and the shortest total time.** Answer: **ONE window, ~7
minutes**, plus everything else outside it.

**Inside the window — only what genuinely needs the widget lane with the gate down:**

| Work | Requests | Feeds |
|---|---|---|
| the full regression suite | 46 | CRT 1a (idempotency #3) · 2 (book / cancel / reschedule) · 5 (handoff, clarify ×2, lock) · 12 (past / invalid / pre-hours dates) · part of 6 |
| the race drill — two bookings fired in parallel into one slot, then both "yes" | 4 | CRT 1b, asserted on the M2 expectation (`race_other_count >= 1`, no orphan) |
| one DST-boundary booking | 2 | CRT 12 |

~52 requests at `PACE=4` (the edge rate limit is 20/min/IP; the pace is not a workaround, it keeps us under
our own rule) ≈ 3.5 minutes of pacing + model latency ≈ **6–7 minutes, one window.**

**Outside the window — gate UP, no exposure:** `run-d11` (owner path, not the widget lane) · the unit
suites (`resolve-date`, `validate-intent`, `locked-once-parity`) · error visibility on the scheduled
workflows (OPS-5 is itself a live demonstration of it) · reading executions for MUST-RUN / MUST-NOT-RUN
nodes · the K-3 cleanup counts · both parity gates.

**A saving to rule on:** CP 7-0's remaining deliverable — "prove the protocol end to end once" — is the
SAME act as 7-1's window. Running them as ONE window instead of two halves the exposure and the quota cost.

**Preconditions for that window, all measured at the start of its turn:** (1) Airtable answering again —
quota reset or plan change (Yigitcan) — AND the remaining allowance, read from the workspace usage page,
measured above the window's declared budget with margin, since background jobs keep consuming daily; (2) the gate measured UP; (3) baseline row counts
taken for K-3's arithmetic.
