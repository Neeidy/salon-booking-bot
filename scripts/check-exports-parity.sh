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
  "sTn3xfa9qI6IyBNP:n8n/workflow.drill-state.sanitized.json"
  "QJcFVLIkZlc71scP:n8n/workflow.drill-state.copy.sanitized.json"   # D3a copy (MIGRATION-PLAN §3r), inactive until D6b
  "TgXeN8HAJ2BkiJWO:n8n/workflow.owner-actions.copy.sanitized.json"   # D3b copy (MIGRATION-PLAN §3r), inactive until D6b
  "snVOpMe3dn52LVp4:n8n/workflow.purge.copy.sanitized.json"   # D3d copy (MIGRATION-PLAN §3r), inactive until D3e/D6b
  "whpyb2MZKzViQGr8:n8n/workflow.reminders.copy.sanitized.json"   # D3c copy (MIGRATION-PLAN §3r), inactive except during D4's M7 window, until D6b
  "GyvhZH79DxC1LpTx:n8n/workflow.main.copy.sanitized.json"   # D4b copy (MIGRATION-PLAN §3s), inactive except during D4 drill blocks, until D6b
)

# WHICH WORKFLOW OF EACH PAIR HOLDS PRODUCTION (MIGRATION-PLAN §3t, decision 9): "ORIGINAL_ID:COPY_ID:LIVE", LIVE being
# `original` or `copy`. Every line says `original` until the cutover; D6b flips each pair to `copy` in a commit, and
# that commit is the DECLARATION the guards read (scripts/pair_roles.py holds the rules): exactly one of each pair is
# active, it is the declared one, and an inactive workflow is green only when ROLES declares the OTHER one live.
ROLES=(
  "SL142I47mK6SAz6p:GyvhZH79DxC1LpTx:copy"   # Main
  "EHsn2WocYqB2bYi1:whpyb2MZKzViQGr8:copy"   # Reminders
  "sdXropaqnNaOvIvs:snVOpMe3dn52LVp4:copy"   # Processed Purge
  "lTyYKxqyzumH2JMz:TgXeN8HAJ2BkiJWO:copy"   # Owner Actions
  "sTn3xfa9qI6IyBNP:QJcFVLIkZlc71scP:copy"   # Drill State Read
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
# The pair roles: content parity above reads one workflow at a time and cannot see that BOTH of a pair are active
# (or neither). This reads the pairs.
python3 scripts/check-pair-roles.py || rc=1
[ "$rc" -eq 0 ] && echo "check-exports-parity: OK — ${#PAIRS[@]} committed exports, all match the live instance; ${#ROLES[@]} pairs hold their declared roles."
exit "$rc"
