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
