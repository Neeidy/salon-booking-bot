#!/usr/bin/env bash
# Guard: the INSTALLED secret-scan hook must match the committed canonical copy.
#
# WHY: scripts/secret-scan.sh is the reviewable source of truth, but the copy that actually RUNS lives at
# ~/.claude/hooks/secret-scan.sh. Two copies drift silently — you fix one, the other keeps running. This
# is the same class of problem .claude/rules/contract-integrity.md forbids for schemas, applied to a
# security control. Exit 1 = the running guard is not the reviewed guard.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANON="$ROOT/scripts/secret-scan.sh"
INSTALLED="${SECRET_SCAN_INSTALLED:-$HOME/.claude/hooks/secret-scan.sh}"

[[ -f "$CANON" ]] || { echo "HOOK DRIFT: canonical $CANON missing"; exit 1; }
if [[ ! -f "$INSTALLED" ]]; then
  echo "hook drift check: NOT INSTALLED at $INSTALLED — the push guard is not active on this machine."
  echo "  install: cp scripts/secret-scan.sh \"$INSTALLED\" && chmod +x \"$INSTALLED\""
  exit 0   # informational: a fresh clone has not installed it yet; that is not a repo defect
fi
if diff -q "$CANON" "$INSTALLED" >/dev/null; then
  echo "hook drift check: OK — the installed push guard matches the committed scripts/secret-scan.sh"
  exit 0
fi
echo "HOOK DRIFT: the RUNNING push guard differs from the reviewed one."
diff -u "$CANON" "$INSTALLED" | head -20
echo "  → reconcile before pushing: the guard that runs must be the guard that was reviewed."
exit 1
