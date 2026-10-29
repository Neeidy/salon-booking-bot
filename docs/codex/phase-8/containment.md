# Phase 8 R2 — how the CRT #14 run was contained

**Harness:** the 7-2 R2 one (`docs/codex/7-2-r2/containment.md`), re-built for this run because its runner script
was not committed. **This run's runner IS committed:** `docs/codex/phase-8/run.sh` — the file that ran attempt 2, with
the session scratch directory and the repository path turned into parameters; its body is otherwise byte-identical.
One throwaway container (label `c72=run`, all capabilities dropped, no new privileges) from the image
`c72-codex-audit:r2` (its dependencies come from the committed lockfiles, unchanged since it was built); a read-only
single-branch export of the pushed `main` at the pin `35df5cc` (no remote, no reflog, no hooks; 326 files), copied
inside to a writable working directory; a temporary Codex home holding only a copy of the CLI's login file and the
prompt; these Codex features off: apps, browser use (three), computer use, hooks, image generation, the in-app browser,
multi-agent, plugins, remote plugins, plugin sharing, shell snapshot.

**The network was OPEN for the Codex run, and that is stated rather than implied.** The run container used Docker's
default network with `--dns 1.1.1.1`, because the Codex CLI reaches its model API over it. "No network" in the prompt
is an INSTRUCTION to the auditor, not a control. Only the mount-check probes ran with `--network none`. What there is
instead of a control: the scan of all 22 command lines below found no network tool — evidence about what was RUN,
not a boundary on what COULD be.

**Mount check, before Codex starts:** every mount whose mount point is not under `/proc`, `/dev` or `/sys` must be
exactly `/`, `/audit` (read-only, 326 files, refuses a write), `/codexhome` and the three `/etc` files Docker writes.
**Its bound:** the exclusion is by mount POINT, so a bind mount placed anywhere under `/proc`, `/dev` or `/sys` would
pass it. The run's own `docker run` line (in the runner) names only `/audit` and `/codexhome`.

- **Attempt 1 failed the check, and the defect was the check's.** It selected mounts by filesystem TYPE and dropped
  `tmpfs`; the session scratchpad that holds the export and the Codex home is on tmpfs, so `/audit` and `/codexhome`
  were dropped with it and the check saw only `/` and the three `/etc` files. Measured with the full mount table of the
  same container (no Codex, no network): the six intended mounts and nothing else. The check did its job — exit 97,
  Codex never started, nothing ran. It now selects by mount POINT. Attempt 1's export and Codex home (the login copy
  and the prompt; Codex never ran, so nothing else) were deleted by their literal paths before attempt 2 — the runner
  refuses to start while either exists, and attempt 2 started.
- **Before attempt 2 the corrected check was shown able to fail and to pass:** one extra host directory mounted →
  exit 97 before Codex; the intended mounts → exit 0.
- **Attempt 2 is the run `crt14.md` records:** mount check OK; Codex exit 0; 468 container seconds. Its export and
  Codex home (the login copy, the prompt, the logs and the answer — the answer is committed verbatim as `crt14.md`)
  were deleted after the run.

**Declared, against this repo's own habit (`.claude/rules/remote-operator.md`, "`rm` only with literal, absolute
scratchpad paths"):** the runner removes the export's `.git/hooks` and `.git/logs` by a path built from a variable.
It is reached only after `git init` has created that export new in the same run (the runner stops if the path already
exists, and the `&&` chain stops if the fetch fails), so it cannot reach anything else — but it is the form the habit
forbids, and it is recorded rather than smoothed over.

**Containment checker (`scripts/codex-containment.py`, information):** commands 22 · passed 18 · flags 6. The six
read one by one: two `environment dump: set` (a Python heredoc calling `set(...)`), two "absolute path" `//` (a URL
regular expression inside a Python heredoc), one unparseable multi-line shell script (three commands joined), and
"the logs disagree" with 22 commands in both logs. A separate scan of all 22 command lines for the login copy, the
Codex home, the environment, `/proc`, `$HOME` and network tools found none.
