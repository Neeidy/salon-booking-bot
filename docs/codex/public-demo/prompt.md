# Public demo R1 — Codex audit prompt, CRT #15 "public-demo spend brake and retention"

The exact text the Codex run receives: the block below, with `{PIN}` replaced by the SHA of the commit that added this
file. Nothing else is sent, so the audit can be repeated from this file alone. One target, one run (Ruling (d),
2026-10-29: "one Codex run on the Main + Purge diff (money handling)").

**How the run is made:** the Phase 8 harness unchanged (`docs/codex/phase-8/containment.md`), run by
`docs/codex/public-demo/run.sh` — the Phase 8 runner with this file's path in place of Phase 8's prompt path and its
header comments rewritten; nothing else differs (`diff` against `docs/codex/phase-8/run.sh` shows it).

<!-- prompt -->
You are auditing a public repository: an n8n-based salon booking chatbot (the engine is exported n8n workflow JSON;
the store is Postgres). Your working directory is a writable copy of the repository at commit {PIN}, with the git
history of `main` up to it and the dependencies installed from the committed lockfiles. You may run the repository's
own tests and offline commands there; anything you change in the copy is discarded and is not a fix.

TARGET — two staged engine edits for a PUBLIC demo endpoint, before they are deployed:
(A) the spend brake. `n8n/staged/workflow.main.sanitized.json` differs from the live export
`n8n/workflow.main.sanitized.json` in ONE node, `Eval Spend` (its delta file: `n8n/staged/workflow.main.delta.json`).
It sits between `Read Spend` (a Postgres read of the month's LLM cost, with `alwaysOutputData` and
`onError: continueErrorOutput`) and `Spend Gate` (true → the LLM call; false → a deterministic handoff reply). The old
code counted an unreadable meter as zero spend (fail-open); the new code is meant to let the LLM run ONLY on a reading
it can trust. Its premise about n8n's engine and its rule are written in the node's comments and in
`docs/PUBLIC-DEMO-PLAN.md` ("R1 — built", part 1); its test is `tests/unit/eval-spend-fail-closed.test.cjs`, its mutants
`tests/unit/eval-spend-mutants.py`. Downstream, `Build Spend Record` adds this call's cost to `_spend.prev`.
(B) lead retention. `n8n/staged/workflow.purge.sanitized.json` differs from `n8n/workflow.purge.sanitized.json` in ONE
node, `Load Config (Purge)`: `leadsRetentionDays` 90 → 30 (rendered by `scripts/render-client.py`). The Purge's leads
branch (`Compute Leads Cutoff` → … → `Delete Old Leads` → `Verify Leads Purge`) deletes leads older than that, under a
candidate cap. Its existing test is `tests/unit/leads-purge-read-error.test.cjs`.
The deploy procedure is `docs/RUNBOOK.md` §3 and §8; the deploy tool's checker is `scripts/diff-workflow-copy.py`.

Answer these four questions, each with evidence (the code or text at {PIN}, or an offline command you ran and what it
showed):
1. Is there any output `Read Spend` can produce (a row, no row, a caught query error, a thrown error, several items, a
   row of an unexpected shape or type) on which the new `Eval Spend` still lets the LLM run when the month's spend is
   unknown or at/over the cap? Is the engine premise in its comments correct for this node type and these settings?
2. Can the new code block the LLM when it should not (a legitimate first message of a month, a legitimate row), or
   break `Build Spend Record`'s accounting on the path where the LLM does run?
3. With `leadsRetentionDays` 30, can the Purge delete a lead it should not (a wrong cutoff, a timezone or type error, a
   cap that does not hold, a row of unknown age), or report success when it did not delete?
4. Do the staged files differ from the live exports ONLY as stated, and would the repository's tests stay green if the
   property they name were broken (a test that cannot fail, a mutant that should exist and does not)?

For each finding give a severity (HIGH / MEDIUM / LOW), the file and line, a concrete failing input or scenario, and
the offline command that shows it. Do not report style or refactors.

Rules for this run:
- Read only files inside this working directory. Do not access any path outside it, environment variables or /proc.
  Use only git history reachable from HEAD: no `--all`, reflog, branch or stash listing.
- No network.
- Write temporary files only under a directory you create inside the working directory or under the system temp
  directory, never into the repository's tracked paths.
- Recorded bounds: an item the repository records as an accepted bound with its reason (`docs/PUBLIC-DEMO-PLAN.md`,
  the node's and tests' own comments) is not a finding unless its stated bound or scope is wrong; if it is, say so
  with evidence.
- Some suites need what this environment does not have (the live n8n instance, the host-leak guard's local file).
  Say which you could not run.
- End with a short summary: per question, a one-line answer, and the list of findings by severity.
