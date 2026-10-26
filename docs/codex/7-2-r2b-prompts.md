# Phase 7-2 R2b — Codex recheck of the last fixes (changed code only)

The exact text each Codex run of the R2b recheck received: the `common` block followed by its target block, with
`{PIN}` replaced by the SHA of the commit that added this file (the fixes are in the commits before it, from
`e5c5636`). Ruling R2b (Yigitcan, 2026-10-26): this is each item's LAST fix; a target still "not closed" goes to
Yigitcan for a one-line ruling, not to another round.

**How each run is made:** as in R2 (`docs/codex/7-2-r2/containment.md`): one throwaway container per run, the image
`c72-codex-audit:r2` (dependencies from the committed lockfiles), a read-only single-branch export of the pushed
`main` at the pin copied to a writable working directory, a temporary Codex home with a copy of the auth file, a mount
check before Codex starts.

**Lanes (sequential each, in parallel):** A = `deploy` → `11` → `1b` → `5` · B = `4` → `12` → `9`.

<!-- prompt:common -->
You are re-auditing a public repository: an n8n-based salon booking chatbot (the engine is exported n8n workflow
JSON; the owner dashboard is a Next.js app; the store is Postgres). Your working directory is a writable copy of the
repository at commit {PIN}, with the git history of `main` up to it and the dependencies installed from the committed
lockfiles. You may run the repository's own tests and offline commands there; anything you change in the copy is
discarded and is not a fix.

This is the LAST recheck of this target. Earlier audits recorded findings in the reports named below; changes made
since the most recent one are in the commit range `e5c5636..{PIN}`. Answer exactly two questions:
1. For EACH finding the target block names: is it closed at {PIN}? Answer closed / not closed / partly closed, with
   evidence (the code or text at {PIN}, or an offline command you ran and what it showed).
2. Did any change in `e5c5636..{PIN}` open a NEW defect? Look only at the changed code and at what it touches.
Do not re-audit code the range did not change, and do not report style or refactors.

Rules for this run:
- Read only files inside this working directory. Do not access any path outside it, environment variables or
  /proc. Use only git history reachable from HEAD: no `--all`, reflog, branch or stash listing.
- No network.
- The workflow exports: `n8n/workflow.*.copy.sanitized.json` are the versions in production. `n8n/staged/` holds
  prepared edits of the Main and Owner Actions copies (each with a declared delta file beside it) that are NOT
  deployed. Judge a finding about one of those two workflows on the staged export.
- Recorded limits: an item the repository records as an accepted limit or bound, with its reason (`docs/ROADMAP.md`,
  including its "7-2 Tur 2 — CONVERGE list"; the target's rule files; the code's own comments), is not a finding unless
  its stated bound or scope is wrong; if it is, say so with evidence.
- Some suites need what this environment does not have (the live n8n instance; Docker is absent here, so the
  Postgres concurrency test `tests/db/claim-race.test.sh` cannot run). Say which you could not run.
- Do not quote any value that looks like a credential, a host name or personal data; refer to it by file and line.

Report, in Markdown:
1. A table of the named findings: finding · its severity in the report that raised it · closed / not closed / partly
   closed · evidence.
2. New findings, most severe first. Each: severity (CRITICAL / HIGH / MEDIUM / LOW) · location · whether it is inside
   a change of `e5c5636..{PIN}` · a concrete failure scenario · evidence.
3. What you ran (commands and their results, briefly).
4. A verdict on the last line: `VERDICT: pass`, `VERDICT: revise` or `VERDICT: block`.
<!-- /prompt -->

<!-- prompt:deploy -->
Target — the deploy tool for engine edits (`scripts/workflow-step.py`, `scripts/diff-workflow-copy.py`,
`tests/unit/workflow-step.test.py`, `docs/n8n-rollback.md`). Findings to recheck: every row of
`docs/codex/7-2-r2/deploy.md` that is not "closed", and its new findings 1 (HIGH, rollback can restore weaker admission
logic) and 2 (MEDIUM, edge comparison drops the connection type). Its new finding 3 (LOW, settings before the probes)
is recorded in ROADMAP's CONVERGE list. The tool's stated threat model (the THREAT paragraph of the
`scripts/workflow-step.py` docstring) is our own mistakes, not an adversary; a finding that needs a delta nobody
approved is LOW under it. The tool calls the n8n API; this environment has no instance, so use the offline test's fake.
<!-- /prompt -->

<!-- prompt:11 -->
Target — Critical-Review Target 11, the D11 owner write path. Findings to recheck, from `docs/codex/7-2-r2/11.md`: the
two earlier findings it rated partly closed, and its new findings 1 (MEDIUM, a refused release leaves a marker that
turns its retry into a false success), 2 (MEDIUM, the execution counter certifies one release from incomplete
evidence) and 3 (LOW, a correct duplicate refusal fails the concurrency drill). In scope: the staged Owner Actions
export, `tests/run-d11.sh`, `tests/db/claim-race.test.sh`, `tests/unit/owner-actions-tur2.test.cjs`,
`web/dashboard/lib/ownerAction.ts`.
<!-- /prompt -->

<!-- prompt:4 -->
Target — Critical-Review Target 4, secret handling and the git pre-push gate. Findings to recheck, from
`docs/codex/7-2-r2/4.md`: its new findings 1 (MEDIUM, valid key characters deleted before detection) and 2 (LOW, the
guard suite fails during remote-name setup on a newer git). In scope: `scripts/secret-scan.sh`,
`tests/unit/guards-tur2.test.py`. Run any throwaway-repository test in a temporary directory inside your working copy;
never install a hook anywhere else.
<!-- /prompt -->

<!-- prompt:1b -->
Target — Critical-Review Target 1b, no double booking. Finding to recheck: the HIGH of `docs/codex/7-2/1b.md` ("the
stated no-double-booking bound excludes a reachable outcome"), rated not closed in `docs/codex/7-2-r2/1b.md`. Is the
bound now stated correctly, in `.claude/rules/booking-integrity.md` §2, for what the staged Main export does?
<!-- /prompt -->

<!-- prompt:12 -->
Target — Critical-Review Target 12, date resolution. Findings to recheck, from `docs/codex/7-2-r2/12.md`: "the accepted
confirmation gap exceeds its recorded bound" (partly closed there) and "round-5 evidence still describes the wrong
placeholder implementation" (not closed there). The records are the ACCEPTED GAP entry in `docs/ROADMAP.md` and the
2026-09-09h row of `docs/ARCHITECTURE-DECISIONS.md`; the behaviour is in the staged Main export and
`scripts/check-content-parity.py`.
<!-- /prompt -->

<!-- prompt:9 -->
Target — Critical-Review Target 9, dashboard auth and ship gate 18. Finding to recheck, from `docs/codex/7-2-r2/9.md`:
"ship gate 18 contradicts the deployment record" (not closed there). The record is ship gate 18 in `docs/ROADMAP.md`
against the K-6 measurement (`docs/MIGRATION-PLAN.md` §3t, "K-6 after the cutover"; `docs/PHASE-7-PLAN.md`).
<!-- /prompt -->

<!-- prompt:5 -->
Target — Critical-Review Target 5, the human-handoff threshold. Finding to recheck, from `docs/codex/7-2-r2/5.md`:
"documented action scope is wrong" (not closed there). The record is `.claude/rules/prompt-injection.md`; the
behaviour is in `schemas/intent.schema.json` and the staged Main export.
<!-- /prompt -->
