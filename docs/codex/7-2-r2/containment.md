# 7-2 R2 — how the ten recheck runs were contained

**Harness (Tur 1b's containment, ruling R1, with two changes measured necessary for R2):** one throwaway container
per run (label `c72=run`, all capabilities dropped, no new privileges), mounting only a read-only export at `/audit`
and a temporary Codex home holding a copy of the auth file (deleted after the round). Inside, before Codex starts, a
mount check (the mounts are exactly `/`, `/audit` read-only, `/codexhome` and Docker's three `/etc` files; `/audit`
holds the expected file count and is not writable); a failure stops the round. `scripts/codex-containment.py` reads
each run's logs afterwards, as information.

**Change 1 — the image.** The brief's precondition said the dependencies were installed at image build. Measured, the
Tur 1b image had no npm, no `node_modules` and no git. The R2 image (`c72-codex-audit:r2`) adds git, npm, jq, curl
and the GNU tools, and installs the dependencies with `npm ci` from the two committed lockfiles (`web/`, `scripts/`) at
the pin. Before any Codex run, a probe container (no network) ran every `check-all` step: 45 of 48 green; not run:
the host-leak guard (no `CLAUDE.local.md`, by design), the snippet build (no webhook URL, by design), and one
guards-tur2 case whose setup the container's newer git rejects (a nested remote name).

**Change 2 — the export.** A single-branch fetch of `origin/main` at the pin into an empty repository (the fix range
needs history; only pushed commits are in it; no remote, no reflog, no hooks), mounted read-only; the container copies
it to a writable working directory with the dependencies, so the suites can run.

**Per run:** mount check OK in all ten. Target 1a's first attempt ended on a provider error ("Selected model is at
capacity"); its one declared re-run passed. The information scan of every command found none touching the auth copy,
the Codex home, `/proc` or a network address; the lines it lists are `env -i` invocations (clearing the environment)
and a synthetic URL inside a test probe.

| Target | Attempt | Container seconds | Containment checker (information) |
|---|---|---|---|
| 1a | 2 | 143 | commands 21 · passed 21 · search patterns that name no path 0 · flags 0 |
| 1b | 1 | 265 | commands 14 · passed 14 · search patterns that name no path 3 · flags 0 |
| 2 | 1 | 273 | commands 19 · passed 18 · search patterns that name no path 2 · flags 1 |
| 6 | 1 | 182 | commands 14 · passed 14 · search patterns that name no path 0 · flags 0 |
| 12 | 1 | 313 | commands 21 · passed 21 · search patterns that name no path 2 · flags 0 |
| 4 | 1 | 389 | commands 26 · passed 19 · search patterns that name no path 0 · flags 31 |
| 9 | 1 | 302 | commands 24 · passed 19 · search patterns that name no path 0 · flags 29 |
| 11 | 1 | 401 | commands 27 · passed 20 · search patterns that name no path 2 · flags 33 |
| 5 | 1 | 195 | commands 16 · passed 15 · search patterns that name no path 0 · flags 1 |
| deploy | 1 | 535 | commands 31 · passed 30 · search patterns that name no path 0 · flags 1 |
