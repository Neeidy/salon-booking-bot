#!/usr/bin/env bash
# Host-leak guard — the real production n8n host must NEVER reach this PUBLIC repo.
#
# The literal host is deliberately NOT stored in this script (that would itself leak it). It is read from:
#   1) $N8N_HOST, or
#   2) a line "N8N_HOST=<host>" in the gitignored CLAUDE.local.md.
#
# THREE SCANS, because no single one covers what a commit can carry. Each was MEASURED, and the third
# was found only because the second was drilled against a real file that legitimately contains the host
# (the built snippet bundle) — see ARCH-DEC §5, 2026-08-17 row, "selection scope":
#
#   1. --cached  → the INDEX. This is the authority: a commit is built from the index, not the working
#      tree. Measured in an isolated repo: `git add -f <ignored file with the host>` followed by cleaning
#      the working copy left BOTH other scans green while the index still carried the host — the commit
#      would have shipped it. --cached also sees force-added ignored files, so it is the broadest of the
#      three for anything actually on its way into a commit.
#   2. plain      → TRACKED working-tree content. Catches an edit that is not staged yet.
#   3. --untracked→ brand-new files not yet added (a secret typed into a new file must not sail through;
#      added in CP5). NOTE its trap: --untracked applies ignore rules to its ENTIRE selection, so it
#      SKIPS a .gitignore'd file even when that file is tracked. Widening coverage on one axis had
#      silently narrowed it on another, and that axis had never been drilled.
#
# A file that is ignored AND unstaged is correctly NOT a finding — it is not going anywhere near git.
#
# KNOWN LIMITS, stated rather than implied:
#   · CURRENT TREE ONLY. History is not scanned; a host already committed in an earlier commit is not
#     this guard's job (see the forward-only redaction decision, ARCH-DEC §5).
#   · COMMIT MESSAGES are not scanned. Writing the host into a message would reach GitHub with this
#     guard green. Named, not fixed.
#   · A second `git worktree` has its own index and working tree; this guard only sees its own.
#   · On a hit it PRINTS the matching lines, host included. That is the point locally, but it means the
#     output must not be pasted into a public CI log.
#
# Exit: 0 = clean · 1 = LEAK · 2 = cannot check (not configured, or not a git work tree).
# "Cannot check" is deliberately NOT 0: a guard that reports clean when it scanned nothing is the exact
# failure this repo has already been burned by three times.
set -u

# Fail CLOSED if this is not a git work tree — otherwise every git command below quietly errors and the
# script would print "clean". Measured: run from outside a repo, the old version exited 0.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "host-leak guard: CANNOT CHECK — not inside a git work tree"
  exit 2
fi

HOST="${N8N_HOST:-}"
if [ -z "$HOST" ] && [ -f CLAUDE.local.md ]; then
  HOST="$(grep -oE '^N8N_HOST=.+' CLAUDE.local.md | head -1 | cut -d= -f2- | tr -d '[:space:]')"
fi

if [ -z "$HOST" ]; then
  echo "host-leak guard: NOT CONFIGURED — set \$N8N_HOST or add 'N8N_HOST=<host>' to CLAUDE.local.md"
  exit 2
fi

leak=0

# git grep exit codes: 0 = found, 1 = not found, >1 = ERROR. Collapsing >1 into "not found" would turn a
# broken scan into a green report, so each scan separates the three.
scan() {
  local label="$1"; shift
  local out rc
  out="$(git grep -nF "$@" -- "$HOST" 2>/dev/null)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "HOST LEAK — the production host appears in ${label}:"
    # file:line only, and the matched line is TRUNCATED with the host masked. Printing the full match
    # re-leaks the very value this guard protects — which is not hypothetical: drilling it against a
    # minified bundle dumped the host AND the Turnstile site key across the terminal (2026-09-09).
    printf '%s\n' "$out" | sed "s#${HOST}#<N8N_HOST>#g" | cut -c1-160 | sed 's/^/  /'
    leak=1
  elif [ "$rc" -gt 1 ]; then
    echo "host-leak guard: CANNOT CHECK — the ${label} scan failed (git grep exit ${rc})"
    exit 2
  fi
}

scan "STAGED content (the index — this is what a commit ships)" --cached
scan "a TRACKED working-tree file"
scan "a new/untracked file" --untracked

if [ "$leak" -ne 0 ]; then exit 1; fi

echo "host-leak guard: clean — index, tracked files and new files all free of the production host"
exit 0
