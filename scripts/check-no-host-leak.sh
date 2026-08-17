#!/usr/bin/env bash
# Host-leak guard — the real production n8n host must NEVER appear in a tracked (PUBLIC) file.
#
# The literal host is deliberately NOT stored in this script (that would itself leak it). It is read from:
#   1) $N8N_HOST, or
#   2) a line "N8N_HOST=<host>" in the gitignored CLAUDE.local.md.
# Then it git-greps all TRACKED files for it (working tree). Any hit = FAIL.
# git grep ignores untracked files, so CLAUDE.local.md's own N8N_HOST line never false-positives.
#
# Exit: 0 = clean · 1 = LEAK (host found in a tracked file) · 2 = not configured (cannot check).
# Run at every refactor step's close gate, before commit/push. Part of L2 (with the security-auditor agent).
set -u

HOST="${N8N_HOST:-}"
if [ -z "$HOST" ] && [ -f CLAUDE.local.md ]; then
  HOST="$(grep -oE '^N8N_HOST=.+' CLAUDE.local.md | head -1 | cut -d= -f2- | tr -d '[:space:]')"
fi

if [ -z "$HOST" ]; then
  echo "host-leak guard: NOT CONFIGURED — set \$N8N_HOST or add 'N8N_HOST=<host>' to CLAUDE.local.md"
  exit 2
fi

if git grep -nF -- "$HOST" >/dev/null 2>&1; then
  echo "HOST LEAK — the production host appears in tracked (public) files:"
  git grep -nF -- "$HOST"
  exit 1
fi

echo "host-leak guard: clean — the production host is not present in any tracked file"
exit 0
