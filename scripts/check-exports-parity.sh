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
# Exit: 0 all pairs match · 1 a pair drifted · 2 NOT MEASURED (no credentials — never reported as a pass).
set -u
cd "$(dirname "$0")/.."

# workflow id : committed export. ADD A LINE when a workflow is added — and the gate below fails if a
# committed export has no line, so "forgot to add it" cannot look like a clean run.
PAIRS=(
  "SL142I47mK6SAz6p:n8n/workflow.sanitized.json"
  "EHsn2WocYqB2bYi1:n8n/workflow.reminders.sanitized.json"
  "sdXropaqnNaOvIvs:n8n/workflow.purge.sanitized.json"
  "lTyYKxqyzumH2JMz:n8n/workflow.owner-actions.sanitized.json"
)

if [ -z "${N8N_API_KEY:-}" ] || [ -z "${N8N_HOST:-}" ]; then
  echo "check-exports-parity: NOT MEASURED — N8N_HOST / N8N_API_KEY not set."
  echo "  (set -a; . ~/.n8n-api.env; set +a, and export N8N_HOST from CLAUDE.local.md)"
  exit 2
fi

# A committed export with no PAIRS line would otherwise be silently unguarded — the exact failure above.
missing=0
while IFS= read -r f; do
  case " ${PAIRS[*]} " in *":$f "*) ;; *) echo "  ✗ committed export with NO parity pair: $f"; missing=1;; esac
done < <(git ls-files 'n8n/*.sanitized.json')
[ "$missing" -eq 0 ] || { echo "check-exports-parity: FAIL — an export is not covered."; exit 1; }

rc=0
for p in "${PAIRS[@]}"; do
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
[ "$rc" -eq 0 ] && echo "check-exports-parity: OK — ${#PAIRS[@]} committed exports, all match the live instance."
exit "$rc"
