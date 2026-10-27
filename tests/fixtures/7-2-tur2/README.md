# 7-2 Tur 2 exports and delta files

The two approved 7-2 Tur 2 edits as they stood in `n8n/staged/` (`workflow.{main,owner-actions}.copy.sanitized.json`
and `.copy.delta.json`) until D6c (2026-10-27). R3 promoted both edits, so the staged exports were byte-identical to the
committed ones by then; D6c moved them here instead of deleting them, because `tests/unit/workflow-step.test.py`,
`tests/unit/guards-tur2.test.py` and `tests/unit/staged-sanitised.test.py` still test the approved deltas
(`scripts/diff-workflow-copy.py` `APPROVED_DELTAS`) on the graph they were written for: the BEFORE side is
`tests/fixtures/7-2-baseline/`, the AFTER side and the delta are here. Sanitised like the exports they copy; the
workflow names inside are the migration names of the time ("MIG COPY — …"), not the clean names D6c gave the live
workflows.
