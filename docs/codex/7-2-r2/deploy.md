<!-- Codex final message, verbatim. Target deploy · prompt: docs/codex/7-2-r2-prompts.md (2e7ff3d), pin 815ddd7 · 7-2 R2: container run (image c72-codex-audit:r2, deps from the committed lockfiles), mount check OK, attempt 1 · 2026-10-26 -->

No earlier report exists for this target; the table assesses the docstring contract. Main and Owner Actions checks used their committed **staged, undeployed** exports.

**1. Contract recheck at `815ddd7`**

| Finding / contract | Earlier severity | Status | Evidence |
|---|---|---|---|
| Applies only approved deltas, by exact identity | N/A | partly closed | `approved_errs` checks declared node/edge sets and settings. However, `compare` omits connection `type` when comparing edges from touched sources; an undeclared change passes. See finding 2. |
| Never weakens a security gate | N/A | not closed | Rollback validates the Turnstile literal and webhook identity, but does not validate admission-node logic against the committed gates. A fresh snapshot restoring unconditional admission returned success. See finding 1. |
| Takes a live snapshot immediately before editing and proves rollback GET == snapshot | N/A | closed | [workflow-step.py:464](/home/auditor/work/scripts/workflow-step.py:464) rereads live state before snapshot/write. Rollback compares complete nodes, credentials, connections, settings and name. The offline suite verifies restoration and rejects altered readbacks. The gate-safety defect remains separate. |
| Applies Owner Actions settings separately, last, after probes | N/A | partly closed | `put` preserves live settings; `settings` applies the exact approved value. The [runbook:24](/home/auditor/work/docs/n8n-rollback.md:24) specifies the correct order, but the command accepts an unprobed edit. See finding 3. |

**2. New findings**

1. **HIGH · Rollback can restore weaker admission logic**

   **Location:** [workflow-step.py:557](/home/auditor/work/scripts/workflow-step.py:557), calling `webhook_invariant_errs` at line 353. **Inside the specified change range.**

   An accidental live edit makes Main’s `Turnstile Valid?` condition unconditionally true while leaving the configuration literal enabled. The approved `put` repairs that condition and saves the actual pre-edit state. `rollback` then restores the unconditional condition and reports success; the documented following `activate` also succeeds. Invalid Turnstile results can consequently enter the forward path.

   **Evidence:** Using the repository fake, approved `put` returned `0` and repaired the gate; rollback of its freshly generated, unmodified snapshot returned `0` and restored unconditional acceptance. Activation returned `0`. The equivalent Owner Actions signature-check case also restored successfully.

   This requires **no unapproved delta**. It is independent of snapshot age, so the recorded stale-snapshot limit does not cover it. The runbook’s parity precheck would detect the initial drift, but rollback’s claimed protection against an already-wrong snapshot does not.

2. **MEDIUM · Edge comparison drops connection type**

   **Location:** [diff-workflow-copy.py:218](/home/auditor/work/scripts/diff-workflow-copy.py:218), used by the touched-source comparisons at lines 350 and 371. **Inside the specified change range.**

   A committed staged export can accidentally change an existing connection’s `type` while retaining its source, output, destination and input index. Comparison reduces both connections to the same four-part string, including when checking preserved gate edges.

   **Evidence:** With the real approved Main delta unchanged, I changed the existing successful output connection of `Turnstile Valid?` from `main` to `ai_tool`. `compare` returned no errors. Using the suite’s committed-file fixture mechanism, `put` returned `0`, and the fake retained the altered connection. This sends malformed routing toward the regular downstream node while reporting the edit as approved. Actual n8n execution of that malformed connection was not available to test.

   This requires **no unapproved delta**; the current staged exports themselves pass validation.

3. **LOW · Settings can remove probe evidence before probes run**

   **Location:** [workflow-step.py:500](/home/auditor/work/scripts/workflow-step.py:500). **Inside the specified change range.**

   An operator can accidentally run `put → settings` immediately, before activation or probing. The settings command checks that the edit is live, but has no check for completed probes. Successful execution saving is then disabled before the execution-count probe.

   **Evidence:** Both commands returned `0`, with zero activation or execution-list calls beforehand. After activation, a simulated probe receiving the expected response bodies returned `1` because no successful executions were saved. The runbook orders these steps correctly; the tool does not guard this ordering mistake.

**3. Commands and results**

Tests ran through a workspace-local wrapper using a nested checkout, workspace-local temporary files and synthetic test environment values.

| Command | Result |
|---|---|
| `git diff 8ddf452..815ddd7` scoped to target files and dependencies | Reviewed changed implementation, tests and procedure |
| `python3 .audit-recheck/run_suite.py .audit-recheck/repo/tests/unit/workflow-step.test.py` | Exit 0; 235 checks passed |
| Same wrapper: `scripts/diff-workflow-copy.py --selftest` | Exit 0; 134 checks passed |
| Same wrapper: `tests/unit/staged-sanitised.test.py` | Exit 0; both staged exports and negative controls passed |
| Same wrapper: `tests/unit/settings-parity.test.py` | Exit 0; 23 checks passed |
| `python3 .audit-recheck/run_suite.py .audit-recheck/repro.py` | All reproduction assertions passed; [results](/home/auditor/work/.audit-recheck/repro.py.log) |

Live n8n PUT/GET behavior, real webhook probes and the R3 scratch rehearsal could not be tested without an instance. Docker-dependent database suites were not run.

VERDICT: block
