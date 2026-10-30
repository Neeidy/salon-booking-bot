# Operational incidents

> **WHAT BELONGS HERE — and what does not.**
> This file records **OPERATIONAL ACCIDENTS**: something the operator (Claude, or a subagent) did to the
> environment that was not the intended work — a command that hit the wrong target, a process left running,
> a step that broke a live system, a control that could not do its job.
>
> **PRODUCT defects do NOT belong here.** A wrong reply, a missing guard, a false claim in a document, a
> booking bug — those stay in [`ARCHITECTURE-DECISIONS.md`](ARCHITECTURE-DECISIONS.md), which is where the
> system's own reasoning lives. We are not opening a second copy of that log.
>
> The dividing question: *did the SYSTEM misbehave, or did the HAND on the keyboard?* System → ARCH-DEC.
> Hand → here.
>
> **Why the file exists at all:** four of these happened in the Phase-6b session and all four lived only in
> chat. They were narrated, acknowledged, and evaporated. A near-miss nobody can find is a near-miss that
> gets repeated.

---

## OPS-10 · 2026-10-30 · A local `next build` in the repo broke the LIVE owner dashboard, which runs from the same directory

**What happened (public demo R2g).** The `next` 16.4.1 upgrade was installed and built IN the repository — `npm install`
in `web/` (about 22:58 Vienna), then `next build` for the site and for `web/dashboard` (`.next/BUILD_ID` 23:00:11). But
the owner dashboard's service (`ops/systemd/salon-dashboard.service`) runs `next start` with
`WorkingDirectory=…/web/dashboard`: its `.next/` and the shared `web/node_modules` are the ones that were just replaced.
The running 16.3.4 server could no longer load its own chunks — the next request to `/` returned **500** with a
`ChunkLoadError` / `MODULE_NOT_FOUND` for a chunk of the old build.

**What it cost:** the service log shows **0 errors from 2026-10-26 20:00 to 22:59 and exactly one failed request after
the build — the 500 of the measuring request itself (23:00:36)**; no other request is logged as failed. The broken window
ran from the install (about 22:58) to the restart (23:01:24), about three minutes. `systemctl --user restart
salon-dashboard.service` brought it back on the build that was on disk: `/` 200 two seconds later, `next-server
(v16.4.1)`, bound to `127.0.0.1`, no error since. **So the live dashboard now runs `next` 16.4.1** — the approved version,
tested (`check-all` 0, `next build` green) and committed in `6a19a06` — but it got there by this accident, not by a
deployment decision.

**Why it happened:** R2e and R2f built in a scratchpad COPY of the deploy set, so they never touched it; R2g built in
place. Nothing in the repo said that `web/` is the dashboard's live directory — the unit file says it, the build
instructions do not. **The habit, changed:** an install or build in `web/` changes the running dashboard; build a
dependency change in a copy, or restart the dashboard straight after and measure it (`docs/RUNBOOK.md` §8). **How it
was noticed:** reading the unit's `WorkingDirectory` after the build, then measuring `/` before touching anything.

## OPS-9 · 2026-10-26 · A commit landed after a RED `check-all`, because the command chain did not gate on it

**What happened (7-2 R4).** One shell command ran `check-all`, printed its exit code, and then committed — the commit
was joined with `;`-style sequencing to the echo, not with `&&` to the check. `check-all` came back **1** and the commit
(`b0f16c5`, the seed tool's review fixes) was made anyway.

**What it cost: nothing reached the remote, by luck of order.** The red step was `guards-tur2`'s extraction-failure
case, broken by an UNCOMMITTED scanner change sitting in the same working tree, not by the commit. The commit's own tree
was then measured alone — the two in-progress files set aside to the scratchpad, HEAD's versions in their place,
`check-all` → **0** — and the work restored. It was local; the pre-push audit had not run.

**The habit, changed:** the commit is chained to the check with `&&` (or the check's exit code is tested before any
`git commit`), and a working tree carrying another unit's changes is measured as a tree, not taken as the commit's
evidence. **How it was noticed:** reading the command's own output (`check-all rc=1` above the commit line).

## OPS-8 · 2026-10-26 · Mutant runners left test artefacts in the repo and in /tmp, and later runs read them

**What happened (7-2 Tur 2 R1d).** Mutant runs of `tests/unit/workflow-step.test.py` that crashed or were cut short left
`n8n/staged/.wstest-snap.json` (a snapshot file inside the repo, gitignored) and 22 `/tmp/workflow-step-rehearsal-*`
directories behind. Later runs found the leftover snapshot path taken (the tool creates snapshots O_EXCL) and read red
for a reason that had nothing to do with the mutant. Nothing was committed: the name is gitignored and the guards saw
nothing staged.

**Fix:** the leftovers were moved to the scratchpad, inspected, and deleted by literal path; the test now removes its own
files in `finally`, and every mutant runner sets its own `TMPDIR` under the scratchpad. **How it was noticed:** not recorded at the
time; written here in R4 from the session's own record, so the detection step is not claimed.

## OPS-7 · 2026-10-26 · An installer test installed the pre-push gate into THIS repository's `.git/hooks`

**What happened (7-2 Tur 2 R1c).** A case of `tests/unit/guards-tur2.test.py` passed `PRE_PUSH_TARGET` to the hook
installer to aim it at a throwaway repo; the installer had just been confined and ignores that variable by design, so it
installed into its canonical target — this repo's `.git/hooks` — once. The installed files were the gate itself, so no
push went unscanned, but a test had written where a real push from this repo reads.

**Fix:** the installed copies were moved out and re-installed from HEAD (`check-hook-drift.sh` 0); the case was rewritten
to run a COPY of the installer placed inside its temp repo (`install_into()`, which refuses any path under this repo), and
the test file's header records it. Rule kept: tests never write the real `.git/hooks`. **How it was noticed:** not recorded at
the time; the account above is the test file's own header (R1c), so the detection step is not claimed.

---

## OPS-6 · 2026-10-19 · A process listing printed part of the tunnel credential

**What happened.** While measuring how the dashboard runs, I ran a process listing (`ps`) to find
it. The tunnel daemon's token was visible in the process listing, so the listing printed it.
The output went through the masker, but the masker only knew hex-shaped secrets; this token is a
base64/JWT shape, so it passed through. Because the line was cut at a fixed width, **only the first part
of the token reached the transcript.**

**What was exposed: DERIVED, not re-read.** Only lengths were printed: the line prefix, the token
length and the cut width. From those and the token's field order, the printed part is **derived** to
cover the account field and the start of the tunnel identifier, ending before the secret field. The
derivation rests on two things, neither confirmed by reading the value: that field order, and that this
line was the only place the token reached the transcript. Nothing reached the repo.

**The standing exposure, which matters more than the incident.** The listing showed that the full
credential is readable on this host more widely than intended, including by the account the agent runs
as. A rule says the agent never holds a production credential; this one was within the agent's reach,
and nobody had decided that. *The mechanism is deliberately not described here until it is fixed
(`remote-operator.md`: no service inventory of a reachable host). It is added back, in the past tense,
once the fix lands.*

**What changed immediately.** The masker now also redacts JWT-shaped tokens, long base64 runs and the
value after `--token`/`--password`/`--secret`/`--key`, self-tested on fake strings only. ⚠ *The masker
lives in the session scratchpad, not in the repo, so this protection is rebuilt with it each session.*
Process listings from now on print process NAMES, never arguments.

**Decision (Yigitcan, 2026-10-19).** No rotation, on the derivation above. The fix moves the token into a
root-only file (mode 0600) and closes the wider read path. It is done in the **final security pass together with ship-gate #17**,
following his ruling to defer security work to the end. **Open until then.**

---

## OPS-5 · 2026-10-06 → STILL OPEN at 2026-10-18 · The Airtable monthly API quota ran out and the bot has had no data layer for 12 days

**What happened.** Airtable began refusing every API call from this workspace with
`PUBLIC_API_BILLING_LIMIT_EXCEEDED` — *"You've reached the maximum number of requests allowed for this month
… wait until usage resets."* The free plan allows **1,000 API calls per month per workspace** (measured
2026-09-12, ARCH-DEC). Every workflow that reads or writes state has been failing since. For the live bot
that means `Load State` / `Check Processed` / `Save State` cannot run: a real conversation could not be
served for the whole period.

**When — measured, not estimated.** A binary search over the hourly Reminders executions (n8n keeps 14
days of them): last successful Airtable call **2026-10-06 21:00 UTC**, first refused **2026-10-06 22:00
UTC**, still refused **2026-10-18 18:00 UTC**. Confirmed by a second, independent instrument the same day
— the Airtable connector outside n8n returned the identical billing-limit error.

**How it was noticed.** Not by anyone reading the alerts. It surfaced on 2026-10-18 while declaring a call
budget for CP 7-0: the latest Purge run's `Count Leads Total` returned an empty item on its success output
and an error item on its error output, and the error said billing limit. **The alerting itself worked:**
250 of the last 250 blocked Reminders runs sent an owner alert, and all 250 were delivered (`ok:true`) —
those 250 cover about ten days (2026-10-08 08:00 → 10-18 18:00); the first ~1.5 days of the block were not
checked. "Failures are visible" held for every run that was examined. What did not exist was anything that
turned roughly one identical alert per hour into one escalation — **a visible failure nobody acts on is the same outcome as a silent one,
reached more slowly.**

**Impact.** The data layer — therefore the bot — down for the whole measured window — 11 days 20 hours (2026-10-06 22:00 → 2026-10-18 18:00 UTC). No paying customer exists
(Yigitcan, 2026-10-18), so the impact is the demo, not a client. The LLM spend brake reads spend from
Airtable, but its error path routes only to an owner alert and never reaches `Build LLM Request` (read from
the published graph), so the outage did not open an unbounded-spend path.

**Cause — NOT established, and it is written as unknown rather than guessed.** What was measured: the scheduled jobs' own
per-run Airtable cost, from real executions — on a day with nothing to remind or purge, so it is a FLOOR.
On that floor the housekeeping alone consumes **the large majority of the monthly allowance before any test
or any customer** — and it still does not reach the limit by October 6 on a calendar-month cycle. *(Exact call counts are deliberately kept OUT of this public repo: per-turn cost combined with the remaining headroom is enough for a stranger to compute how few widget messages would take the data layer down for a month — and OPS-5 shows such an outage can go unacted on for days. Same reasoning as the firewall-inventory rule in `remote-operator.md`. The figures are in the round report.)* The hypothesis tested here — that Purge was deleting September's drill
rows one call each as they aged past 30 days — was **NOT supported**: the visible October 5 and 6 runs
deleted nothing. Unmeasurable from this machine: October 1–4 (pruned from n8n), the workspace's billing-cycle
start date, and any OTHER base or integration sharing the same workspace quota. **Yigitcan can read the exact
usage and reset date in Airtable's workspace settings — that is the one reading that settles it.**

**How it is being reverted.** Not by this build: waiting for the reset or upgrading the plan is money and a
workspace setting, both Yigitcan's. **Nothing was changed** in response — no workflow was paused to save
quota, because that is a production change outside the approved scope.

**What prevents a repeat — proposed, not built.** (1) An escalation rule: the same alert class firing N
times without a change in state becomes one louder message, not N quiet ones. (2) A quota line in the
call-budget declaration — background jobs alone take most of the plan, so every test budget must be
declared against what is LEFT, not against the headline allowance. (3) The data-layer migration that ARCH-DEC 2026-09-12 shelved now
has a trigger: on the measured floor, the housekeeping leaves too little for even one regression window in a
month (the window's cost is an ESTIMATE, not a measurement).

---

## OPS-1 · 2026-09-09 · A resync step sanitized the LIVE workflow — production broke, and the parity guard stayed GREEN

**What happened.** A resync pushed committed node bodies to the live n8n instance and swept up `Load Config`
along with the intended nodes, replacing the real Google Calendar id and Airtable ids with the committed
`REPLACE_WITH_…` placeholders. The production bot was broken.

**How it was noticed.** Not by a guard. `check-content-parity.py` ran **green** throughout, and it could not
have done otherwise: `build_smap()` derives its mask FROM live, so once live held the placeholder it mapped
to itself and both sides compared equal. **A parity guard that only compares two artefacts is satisfied by
breaking both.**

**Impact.** The live bot could not reach the calendar or the base. Duration was not measured at the time.

**How it was reverted.** Restored byte-for-byte from a pre-change backup, then verified: the real calendar id
present, no `REPLACE_WITH` remaining, and exactly the intended node edits differing from the pre-round live.

**What prevents a repeat.** `check_live_not_sanitised()` — the LIVE workflow must contain NONE of the
committed placeholders, the opposite direction of the existing check. Fail-ability proven both ways by
replaying the incident against a captured copy. *(The guard's design rationale is in ARCH-DEC 2026-09-09f;
the operational fact was only ever recorded inside that product row, which is why it is restated here as an
incident and not left there alone.)*

---

## OPS-2 · 2026-09-11 · `pkill -f` matched its own shell and killed it mid-script; a server survived 2h37m

**What happened.** A cleanup line used `pkill -f <pattern>` where the pattern also appeared in the command
line of the bash process running it. `pkill` killed its own shell.

**How it was noticed.** Exit code **144**, and the lines after the `pkill` never ran. The consequence was
found much later, while writing this file: `ss -ltnp` showed port **8789** still listening.

**Impact.** An orphaned `python3 -m http.server 8789` (the E2E fallback host page) kept a port bound for
**9,417 seconds — 2 h 37 m** — long after the drill it belonged to. Harmless in itself; a port collision
waiting to happen, and exactly the class of leftover that cost this project five wasted turns once before
(`remote-operator.md` → Why).

**How it was reverted.** Resolved the PID (`ss -ltnp`) and killed it directly. Verified: zero listeners on
8789. Port 8788 was deliberately left alone — it belongs to another session and is the documented drill
server in `tests/snippet/DRILLS.md`.

**What prevents a repeat.** **Never `pkill -f` with a pattern that can occur in the invoking command's own
argv.** Resolve PIDs first (`ss -ltnp`, `ps -eo pid,args`), then `kill` by PID — which is what every other
cleanup in that session did correctly. And: a drill that starts a server owns stopping it, verified by a
listener check rather than by the absence of an error.

---

## OPS-3 · 2026-09-11 · `git clone --local` failed silently, so a subagent's negative control ran in the REAL repo

**What happened.** `security-auditor` set out to prove the push guard could go red, in an isolated clone.
The `git clone --local` failed, the following `cd` failed too, and the remaining commands therefore executed
**in the real repository**. A file containing a fake `sk-ant-`-shaped key was created, staged, and committed
to `main` as `dc28e31 "planted"`. The local `user.name` / `user.email` were also set to a throwaway identity.

**How it was noticed.** The agent noticed and **reported it against itself**, unprompted, at the top of its
report — before the verdict, not buried in it.

**Impact.** A commit containing a fake secret sat on `main`. **It was never pushed**; nothing left the
machine. The planted value was not a real credential.

**How it was reverted.** `git reset --hard` + removing the file + `git reflog expire --expire-unreachable=now
--all` + `git gc --prune=now`, then the local identity unset. **Independently verified afterwards rather than
taken on trust:** `git cat-file -e dc28e31` → *fatal: Not a valid object name* · `git status --porcelain -uall`
empty · `git fsck` silent · zero reflog references · `git config user.name` back to Neeidy · the commit about
to be pushed exactly the intended 5-file change.

**What prevents a repeat.** Two things. (1) **A failed `cd` must abort the script, not continue in whatever
directory happens to be current** — chain with `&&`, or check the clone and the `cd` before any step that
writes. (2) **A plant belongs outside the repo.** Negative controls that create fake secrets run in the
scratchpad, never in a working tree that has a remote. *(And the reason the agent was planting at all is
sound and stays: an exit code of 0 from a guard means nothing until the guard has been shown going red.)*

---

## OPS-4 · 2026-09-11 · The auditor could not read the body of the guard it was judging

**What happened.** While auditing whether `scripts/secret-scan.sh` actually protects a push,
`security-auditor` was **denied read access to the script itself** by the permission layer. It did not try to
work around the denial.

**How it was noticed.** The agent declared it in its own UNVERIFIED CLAIMS block: everything it said about the
guard rested on **behaviour measurement, not code inspection**.

**Impact.** Evidence loss, not a broken system. The verdict was still useful — the guard was driven with a
valid payload (exit 0) and with a planted fake key (exit 2), so it demonstrably measures something. But
nobody could say what the rules were, only what they did on two inputs.

**How it was reverted.** Nothing to revert. The gap was in the audit, not the repo.

**What prevents a repeat — and the first answer written here was WRONG, measured within the hour.**
This entry originally said the fix was `permissions.defaultMode: "bypassPermissions"`. It is not, and the
sentence was written without running the one test that would check it. `security-auditor` ran that test
during the pre-push audit of this very file: **under bypass mode the read is STILL denied.** Bypass does not
override a `deny` rule. Measured again here, from the main session, and the picture is sharper still:

| Measurement | Result |
|---|---|
| `cat scripts/secret-scan.sh` from the MAIN session | **allowed** |
| the same read from the SUBAGENT | **denied** — which is where OPS-4 happened |
| `cat scripts/check-no-host-leak.sh` (same directory) | **allowed** → the denial keys on the FILE NAME, not the directory |
| `git show HEAD:scripts/secret-scan.sh` | **allowed** → the deny is **porous**: it closes the honest route and leaves an indirect one open |

So the real cause is a **name-shaped `deny` glob in the user-level settings** that happens to catch
`scripts/secret-scan.sh` (and `.claude/rules/security-secrets.md` — the auditor cannot read its own job
description), applied to subagents, and unaffected by the project's permission mode. **The real fix is to
narrow that glob or except those two paths; it is NOT done and is an open item.**

A deny that blocks `cat` while `git show` sails past is not a boundary — it is friction that costs evidence
and buys nothing. And the original sentence here is the reason this file has a "how it was noticed" field:
**a control declared closed while it is open is worse than one openly listed as open.**

*(The mode change still stands on its own merits — Yigitcan cannot evaluate the commands the prompt showed
him, and the replacement control is
[`.claude/rules/irreversible-actions.md`](../.claude/rules/irreversible-actions.md). It simply does not fix
OPS-4, which is what this entry wrongly claimed.)*
