# Phase 7-2 R2 — Codex recheck prompts

The exact text each Codex run of the 7-2 recheck received. A run's prompt is the `common` block followed by its target
block, with `{PIN}` replaced by the commit the runs audit (`815ddd7`, the push that closed 7-2 Tur 2). Nothing else is
sent. The question of every run is the R2 scope ruled by Yigitcan (2026-10-26): did each fix close its own finding
without opening a new defect — nothing else.

**How each run is made:** the containment of Tur 1b — one throwaway container per run that sees only a read-only
export of the repository and a temporary Codex home holding a copy of the auth file; a mount check inside the
container before Codex starts (a failure stops the round). For R2 the export is a single-branch clone of `main` at the
pin (the fix range needs history; only pushed commits are in it), the image carries the dependencies installed from
the committed lockfiles at build time, and the container copies the export to a writable working directory so the
suites can run. `scripts/codex-containment.py` reads each run's logs afterwards, as information (ruling R1).

**Lanes (no shared files), each sequential, the two in parallel:** A = `1a` → `1b` → `2` → `6` → `12` ·
B = `4` → `9` → `11` → `5` → `deploy`.

<!-- prompt:common -->
You are re-auditing a public repository: an n8n-based salon booking chatbot (the engine is exported n8n workflow
JSON; the owner dashboard is a Next.js app; the store is Postgres). Your working directory is a writable copy of the
repository at commit {PIN}, with the git history of `main` up to it and the dependencies installed from the committed
lockfiles. You may run the repository's own tests and offline commands there; anything you change in the copy is
discarded and is not a fix.

This is a RECHECK. An earlier audit of this target recorded findings in the report named below
(`docs/codex/7-2/<target>.md`, audited at commit `f1a47eb`). Changes made since are in the commit range
`8ddf452..{PIN}`. Answer exactly two questions:
1. For EACH finding in the earlier report: is it closed at {PIN}? Answer closed / not closed / partly closed, with
   evidence (the code at {PIN}, or an offline command you ran and what it showed).
2. Did any change in `8ddf452..{PIN}` open a NEW defect? Look at the changed code and at what it touches.
Do not re-audit code the range did not change, and do not report style or refactors.

Rules for this run:
- Read only files inside this working directory. Do not access any path outside it, environment variables or
  /proc. Use only git history reachable from HEAD: no `--all`, reflog, branch or stash listing.
- No network.
- The workflow exports: `n8n/workflow.*.copy.sanitized.json` are the versions in production. `n8n/staged/` holds
  prepared edits of the Main and Owner Actions copies (each with a declared delta file beside it) that are NOT
  deployed. When a finding concerns one of those two workflows, judge it on the staged export, and say whether the
  fix exists only there.
- Sanitised values (credential ids, hosts, calendar ids) appear as placeholders. That is intended, not a finding.
- Recorded limits: the repository records open items and accepted limits with their stated bounds (`docs/ROADMAP.md`,
  including its "7-2 Tur 2 — CONVERGE list"; `docs/PHASE-7-PLAN.md`; the target's rule files). Such an item is not a
  finding unless its stated bound or scope is wrong; if it is, say so with evidence.
- Some suites need what this environment does not have (Docker, the live n8n instance). Say which you could not run.
- Do not quote any value that looks like a credential, a host name or personal data; refer to it by file and line.

Report, in Markdown:
1. A table of the earlier findings: finding (as the earlier report titled it) · its severity there · closed / not
   closed / partly closed · evidence.
2. New findings, most severe first. Each: severity (CRITICAL / HIGH / MEDIUM / LOW) · location (file:line, or
   workflow + node name) · whether it is inside a change of `8ddf452..{PIN}` or in code the range did not touch · a
   concrete failure scenario · evidence.
3. What you ran (commands and their results, briefly).
4. A verdict on the last line: `VERDICT: pass`, `VERDICT: revise` or `VERDICT: block`.
<!-- /prompt -->

<!-- prompt:1a -->
Target — Critical-Review Target 1a: idempotency (the same inbound message delivered twice must produce one booking,
never two). Earlier report: `docs/codex/7-2/1a.md`. Main workflow; its rule file is `.claude/rules/booking-integrity.md`.
<!-- /prompt -->

<!-- prompt:1b -->
Target — Critical-Review Target 1b: concurrency / no double booking (two customers, one slot, about the same time;
write-then-verify, no atomic lock). Earlier report: `docs/codex/7-2/1b.md`. Main workflow; rule file
`.claude/rules/booking-integrity.md`.
<!-- /prompt -->

<!-- prompt:2 -->
Target — Critical-Review Target 2: Google Calendar writes (external, hard to undo). Earlier report:
`docs/codex/7-2/2.md`. Main workflow; rule files `.claude/rules/spend-safety.md`, `.claude/rules/booking-integrity.md`.
<!-- /prompt -->

<!-- prompt:6 -->
Target — Critical-Review Target 6: error visibility (a failure must reach the owner; never silent). Earlier report:
`docs/codex/7-2/6.md`. Main, Purge and Reminders workflows; rule files `.claude/rules/handoff.md`,
`.claude/rules/n8n-conventions.md`, `.claude/rules/spend-safety.md`.
<!-- /prompt -->

<!-- prompt:12 -->
Target — Critical-Review Target 12: date resolution (a wrong-day booking is irreversible). Earlier report:
`docs/codex/7-2/12.md`. Main workflow; `schemas/intent.schema.json`, `tests/unit/resolve-date.test.cjs`.
<!-- /prompt -->

<!-- prompt:4 -->
Target — Critical-Review Target 4: secret and PII handling in a PUBLIC repository, including the git pre-push
secret-scan gate. Earlier report: `docs/codex/7-2/4.md`. In scope for the recheck: `scripts/secret-scan.sh`,
`scripts/pre-push.sh`, `scripts/install-pre-push.sh`, `scripts/check-hook-drift.sh`, `scripts/secret-scan-ignore`,
`scripts/check-no-host-leak.sh`, `scripts/check-content-parity.py`, `tests/unit/guards-tur2.test.py`,
`tests/unit/staged-sanitised.test.py`; rule file `.claude/rules/security-secrets.md`. The gate's own header comments
state what it covers and its known limits. Run any throwaway-repository test in a temporary directory inside your
working copy; never install a hook anywhere else.
<!-- /prompt -->

<!-- prompt:9 -->
Target — Critical-Review Target 9: dashboard auth, the owner CSV export route and ship gate 18, including the PII
masking of free text and names. Earlier report: `docs/codex/7-2/9.md`. In scope for the recheck: `web/dashboard/`
(routes, `lib/mask.ts` with its golden table `lib/mask.golden.ts`, `lib/exportCsv.ts`, `lib/ownerAction.ts`,
`lib/releaseReason.ts`, components) and their tests. `lib/mask.ts` states its own mechanism and its RECORDED BOUNDS
(it is data minimisation for an owner's screen, not a security boundary).
<!-- /prompt -->

<!-- prompt:11 -->
Target — Critical-Review Target 11: the D11 owner write path (release a handoff lock from the dashboard through an
n8n webhook). Earlier report: `docs/codex/7-2/11.md`. Owner Actions workflow, `web/dashboard/lib/ownerAction.ts`,
`web/dashboard/app/api/release/route.ts`, `tests/run-d11.sh`, `tests/db/claim-race.test.sh` (needs Docker).
<!-- /prompt -->

<!-- prompt:5 -->
Target — Critical-Review Target 5: the human-handoff threshold (low confidence must lead to a human, never to a
guessed action). Earlier report: `docs/codex/7-2/5.md`. Main workflow; rule files `.claude/rules/handoff.md`,
`.claude/rules/prompt-injection.md`.
<!-- /prompt -->

<!-- prompt:deploy -->
Target — the deploy tool for engine edits: `scripts/workflow-step.py` with `scripts/diff-workflow-copy.py`
(`APPROVED_DELTAS`, `approved_errs`, `compare`) and `tests/unit/workflow-step.test.py`; the procedure in
`docs/n8n-rollback.md`. There is no earlier Codex report for this target: in question 1, take the tool's own stated
contract instead (the docstring of `scripts/workflow-step.py`) and say whether the code meets it. Its stated threat
model (the THREAT paragraph of that docstring) is OUR OWN MISTAKES, not an adversary: judge it on (a) it applies only
the approved deltas, by exact identity of nodes, edges and settings; (b) it never weakens a security gate; (c) it
undoes reliably — the pre-edit live snapshot taken immediately before each PUT and restored by `rollback`, proven
GET == snapshot; and the Owner Actions setting applied by the separate `settings` command as the last step, after the
probes. A finding that needs a delta nobody approved is LOW under that threat model; say so when it is the case. The
tool calls the n8n API; this environment has no instance, so use the offline test's fake.
<!-- /prompt -->
