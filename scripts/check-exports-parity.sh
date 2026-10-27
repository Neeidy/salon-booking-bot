#!/usr/bin/env bash
# check-exports-parity — run the CONTENT-parity guard over EVERY committed n8n export, not just the main one.
#
# WHY THIS FILE EXISTS (measured 2026-09-13, CP 6d-1). `check-content-parity.py` defaults to the main
# workflow and takes the other one from two env vars, so for months it ran against exactly ONE of the
# committed exports. `workflow.reminders.sanitized.json` and `workflow.purge.sanitized.json` were committed,
# were never compared with the instance, and the gate still printed a reassuring green. When the fourth
# export arrived the same gap would have swallowed it too. All four pass now — but the point is that the
# PAIRING is data in this file instead of something a person has to remember.
#
# Same defect family as the hand-listed `.gitignore` exceptions and `check-deploy-separation.sh`'s
# PUBLIC_PKGS: a guard whose SCOPE is maintained by memory narrows silently and stays green while it does.
#
# Exit: 0 every listed workflow matches · 1 one drifted, or the active set is wrong · 2 NOT MEASURED (no credentials — never reported as a pass).
set -u
cd "$(dirname "$0")/.."

# workflow id : committed export, one line per production workflow (D6c, 2026-10-27: the migration's PAIRS/ROLES —
# original and copy, and which of the two was live — ended when the originals were archived; scripts/workflows.py is the
# parser and holds the rules). The export's file name gives the key of the workflow's spec, db/copies/<key>.json. ADD A
# LINE when a workflow is added — and the gate below fails if a committed export has no line, so "forgot to add it"
# cannot look like a clean run.
WORKFLOWS=(
  "GyvhZH79DxC1LpTx:n8n/workflow.main.sanitized.json"
  "TgXeN8HAJ2BkiJWO:n8n/workflow.owner-actions.sanitized.json"
  "snVOpMe3dn52LVp4:n8n/workflow.purge.sanitized.json"
  "whpyb2MZKzViQGr8:n8n/workflow.reminders.sanitized.json"
  "QJcFVLIkZlc71scP:n8n/workflow.drill-state.sanitized.json"
)

if [ -z "${N8N_API_KEY:-}" ] || [ -z "${N8N_HOST:-}" ]; then
  echo "check-exports-parity: NOT MEASURED — N8N_HOST / N8N_API_KEY not set."
  echo "  (set -a; . ~/.n8n-api.env; set +a, and export N8N_HOST from CLAUDE.local.md)"
  exit 2
fi

# A committed export with no WORKFLOWS line would otherwise be silently unguarded — the exact failure above.
# n8n/staged/ is excluded BY NAME: it holds engine edits PREPARED for the next deploy (7-F1), which by design match no
# live workflow until they are promoted into the listed export above. Their sanitisation is checked by
# tests/unit/staged-sanitised.test.py. (The first Round A push committed them without this line and turned this guard
# red: the pre-commit run had seen them untracked, and `git ls-files` lists tracked files only.)
missing=0
while IFS= read -r f; do
  case " ${WORKFLOWS[*]} " in *":$f "*) ;; *) echo "  ✗ committed export with NO WORKFLOWS line: $f"; missing=1;; esac
done < <(git ls-files -- 'n8n/*.sanitized.json' ':(exclude)n8n/staged/')
[ "$missing" -eq 0 ] || { echo "check-exports-parity: FAIL — an export is not covered."; exit 1; }

rc=0
for p in "${WORKFLOWS[@]}"; do
  id="${p%%:*}"; file="${p##*:}"
  out="$(N8N_WORKFLOW_ID="$id" SANITIZED_PATH="$file" python3 scripts/check-content-parity.py 2>&1)"; e=$?
  if [ "$e" -eq 0 ]; then
    printf '  ✓ %-44s %s\n' "$(basename "$file")" "$(printf '%s' "$out" | grep -o 'content parity OK — [0-9]* executable nodes' | tail -1)"
  else
    printf '  ✗ %-44s exit %s\n' "$(basename "$file")" "$e"
    printf '%s\n' "$out" | grep -E 'DRIFT|only in|SANITISE' | head -4
    rc=1
  fi
done
# The active set: content parity above reads one listed workflow at a time and cannot see an UNLISTED active one (a
# second holder nobody reviews — a schedule trigger has no path to collide on). This reads every workflow n8n lists.
python3 scripts/check-active-set.py || rc=1
[ "$rc" -eq 0 ] && echo "check-exports-parity: OK — ${#WORKFLOWS[@]} committed exports, all match the live instance; the active set is exactly the listed workflows."
exit "$rc"
