# 7-2 R2b — how the seven recheck runs were contained

Same harness as R2 (`docs/codex/7-2-r2/containment.md`): one throwaway container per run (label `c72=run`, all
capabilities dropped, no new privileges), the dependency image built from the committed lockfiles, a read-only
single-branch export of the pushed `main` at the pin `5577533` (no remote, no reflog, no hooks) copied inside to a
writable working directory, and a temporary Codex home with a copy of the auth file (deleted after the round). The
mount check ran before Codex in every run and passed in all seven; every run finished on its first attempt.
`scripts/codex-containment.py` read each run's logs afterwards, as information: no command touched the auth copy, the
Codex home, `/proc` or a network address; the lines it lists are `env -i` invocations and one `grep` pattern that
contains the word `curl`.

| Target | Container seconds | Containment checker (information) |
|---|---|---|
| deploy | 215 | commands 25 · passed 24 · search patterns that name no path 0 · flags 13 |
| 11 | 201 | commands 20 · passed 17 · search patterns that name no path 0 · flags 18 |
| 1b | 150 | commands 17 · passed 15 · search patterns that name no path 4 · flags 4 |
| 5 | 161 | commands 35 · passed 35 · search patterns that name no path 1 · flags 0 |
| 4 | 171 | commands 14 · passed 12 · search patterns that name no path 0 · flags 12 |
| 12 | 240 | commands 19 · passed 18 · search patterns that name no path 2 · flags 1 |
| 9 | 173 | commands 31 · passed 25 · search patterns that name no path 0 · flags 18 |
