# Public demo R1 — how the CRT #15 run was contained

**Harness:** the Phase 8 one, unchanged (`docs/codex/phase-8/containment.md`), run by `docs/codex/public-demo/run.sh` —
the committed Phase 8 runner with one line changed (the prompt path) and its header comments rewritten; `diff
docs/codex/phase-8/run.sh docs/codex/public-demo/run.sh` shows exactly that. One throwaway container (label `c72=run`,
all capabilities dropped, no new privileges) from the image `c72-codex-audit:r2`; a read-only single-branch export of
the pushed `main` at the pin `4210208` (no remote, no reflog, no hooks; 347 files, `.git` included), copied inside to a writable working
directory; a temporary Codex home holding only a copy of the CLI's login file and the prompt (48 lines); the same Codex
features off as in Phase 8.

**The network was OPEN for the Codex run, as in Phase 8:** Docker's default network with `--dns 1.1.1.1`, because the
Codex CLI reaches its model API over it. "No network" in the prompt is an instruction to the auditor, not a control;
only the mount-check probes ran with `--network none`.

**One attempt.** The mount check's two controls first — one extra host directory mounted → exit 97, the intended mounts →
exit 0 — then the run: mount check OK, Codex exit 0, container exit 0, 243 container seconds. The answer is committed
verbatim as `crt15.md`. The export and the Codex home are deleted after this record is
committed (they hold the login copy).

**What the run did** — read from its own logs afterwards, as information:
- `scripts/codex-containment.py` (the run's events and session log): commands 14 · passed 12 · flags 3, read one by one:
  two "absolute path" flags are a JavaScript comment (`/*`, `//`) inside a heredoc that wrote a probe file, and one ".."
  flag is a `require('../scripts/node_modules/luxon')` from the run's own `.audit/` directory — inside the working copy.
- A separate scan of all 14 command lines for the login file, the Codex home, `/proc`, `$HOME`, the environment, network
  tools and history-widening git options: 0 hits. The scan was shown able to match first (a positive control of five
  lines: the four forbidden shapes matched, an ordinary test command did not).
- Codex wrote its probes under `.audit/` in the working copy and reported "tracked files were unchanged".

**Declared, as in Phase 8:** the runner removes the export's `.git/hooks` and `.git/logs` by a path built from a variable,
reached only after `git init` created that export new in the same run.
