<!-- Codex final message, verbatim. Target deploy · prompt: docs/codex/7-2-r2b-prompts.md, pin 5577533 · 7-2 R2b: container run (image c72-codex-audit:r2), mount check OK, attempt 1 · 2026-10-26 -->

### 1. Named findings at `5577533`

Main and Owner Actions were assessed using their staged exports.

| Finding | Report severity | Status | Evidence |
|---|---|---|---|
| Applies only approved deltas, by exact identity | N/A — contract row | partly closed | Explicit connection-type changes are rejected, but deleting `type` still passes comparison and `put`. See finding 2 below. |
| Never weakens a security gate | N/A — contract row | closed | The new [pre-snapshot parity check](/home/auditor/work/scripts/workflow-step.py:421) rejects drifted admission logic. Tests for unconditional Main admission and unconditional Owner Actions signature acceptance both produced refusal, zero PUTs and no snapshot. Closure respects the recorded normalization and stale-snapshot limits. |
| Applies Owner Actions settings separately, last, after probes | N/A — contract row | partly closed | Settings remain separate and exact, but [settings_step](/home/auditor/work/scripts/workflow-step.py:534) does not require completed probes. This remaining gap is explicitly accepted in [ROADMAP](/home/auditor/work/docs/ROADMAP.md:55). |
| New finding 1: rollback can restore weaker admission logic | HIGH | closed | [put](/home/auditor/work/scripts/workflow-step.py:493) now checks parity before creating its snapshot. The original weakened-gate scenarios are rejected before any snapshot or PUT; the [regression cases](/home/auditor/work/tests/unit/workflow-step.test.py:829) passed. |
| New finding 2: edge comparison drops connection type | MEDIUM | partly closed | [_edge](/home/auditor/work/scripts/diff-workflow-copy.py:222) distinguishes `ai_tool` from `main`, but defaults a missing `type` to `main`. With each real approved delta unchanged, deleting `type` from Main’s `Turnstile Valid?` success edge or Owner Actions’ `Write Verified?` success edge yielded zero comparison errors, `put` exit 0 and one fake PUT retaining the omission. This still permits an undeclared connection change. [Reproduction](/home/auditor/work/.audit-recheck/repro.py). |
| New finding 3: settings before probes | LOW | not closed | The offline suite successfully runs `put → settings` without probes. This is the explicitly recorded CONVERGE limit, not an additional finding. |

### 2. New findings

**None identified in `e5c5636..5577533` within the deployment-tool changes and their dependencies.**

The missing-`type` case above is a remaining form of earlier finding 2, not a newly introduced regression. Real n8n acceptance or execution of that connection was not tested.

### 3. Commands and results

Offline suites used a nested checkout at the same HEAD, workspace-local temporary files, synthetic environment values and the repository’s fake n8n API.

| Command | Result |
|---|---|
| `git diff e5c5636..5577533 -- scripts/workflow-step.py scripts/diff-workflow-copy.py tests/unit/workflow-step.test.py docs/n8n-rollback.md` | Reviewed target changes; rollback document unchanged |
| `python3 .audit-recheck/run_suite.py .audit-recheck/repo/tests/unit/workflow-step.test.py` | 243 checks passed |
| `python3 .audit-recheck/run_suite.py .audit-recheck/repo/scripts/diff-workflow-copy.py --selftest` | 136 checks passed |
| Same wrapper: `tests/unit/staged-sanitised.test.py` | Both staged exports passed |
| Same wrapper: `tests/unit/settings-parity.test.py` | 23 cases passed |
| `python3 .audit-recheck/run_suite.py .audit-recheck/repro.py` | Explicit type changes rejected; missing types accepted for both workflows |
| `git diff --check e5c5636..5577533 --` target files | Passed |

Could not run live n8n PUT/GET checks, real webhook probes or the R3 scratch rehearsal: no instance is available. `tests/db/claim-race.test.sh` could not run because Docker is absent.

VERDICT: revise
