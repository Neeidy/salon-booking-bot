# 7-2 baseline exports

The Main and Owner Actions copy exports exactly as committed before 7-2 R3 (`n8n/workflow.{main,owner-actions}.copy.sanitized.json`
at `a0a337d`): the state the two approved deltas (`scripts/diff-workflow-copy.py` `APPROVED_DELTAS`, the delta files in
`n8n/staged/`) were reviewed against. R3 promotes the staged edits into the committed exports, after which the committed
exports no longer show the BEFORE side; `tests/unit/workflow-step.test.py` and `diff-workflow-copy.py --selftest` read
it from here, so they keep testing the deltas on the graph they were written for. Sanitised like the exports they copy.
