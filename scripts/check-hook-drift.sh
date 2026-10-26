#!/usr/bin/env bash
# Guard: every INSTALLED push guard must match the copy of its canonical file COMMITTED AT HEAD.
#
# WHY: scripts/secret-scan.sh, scripts/pre-push.sh and scripts/secret-scan-ignore are the reviewable sources of truth,
# but the copies that actually RUN live elsewhere — ~/.claude/hooks/secret-scan.sh (the Claude Code first line), and the
# repo's git pre-push hook with the scanner and the exception file beside it (`.git/hooks/pre-push`,
# `.git/hooks/secret-scan.sh`, `.git/hooks/secret-scan-ignore` — the gate since 7-2 Tur 2, installed by
# scripts/install-pre-push.sh). Copies drift silently — you fix one, the other keeps running. This is the same class of
# problem .claude/rules/contract-integrity.md forbids for schemas, applied to a security control.
#
# AGAINST HEAD, NOT THE WORKING TREE (R1d M-A): "reviewed" means committed. Until R1d this diffed against the
# working-tree file, so an installed copy of an UNCOMMITTED edit read as OK. Each installed copy is now compared with
# `git cat-file blob HEAD:<canonical>`; an uncommitted edit to a canonical file is printed as a note, never as a match.
#
# WHERE GIT RUNS HOOKS FROM (R1d, security MEDIUM-3): a copy in .git/hooks proves nothing if git runs hooks from
# somewhere else. `core.hooksPath` set in any scope VISIBLE FROM THE WORKTREE THIS RUNS IN, or `git rev-parse --git-path
# hooks` resolving anywhere but `<git common dir>/hooks`, is HOOK DRIFT: until R1d, pointing core.hooksPath at an empty
# directory after an install left this check OK while no hook ran at all. NOT seen: a `--worktree` setting of another
# linked worktree (extensions.worktreeConfig) — run this from that worktree too (security R1d LOW-1, CONVERGE).
#
# SYMLINKS (R1d LOW-3): an installed copy that is a symlink is HOOK DRIFT, whatever it points at — `diff` and `-f`
# follow the link, so a `.git/hooks/secret-scan.sh` linked to the working-tree scanner passed and quietly brought back
# "a working-tree edit changes the gate". That covers all three git-hook files (the hook itself included: a linked
# pre-push follows scripts/pre-push.sh in the working tree) and the Claude Code copy.
#
# Exit 1 = a running guard is not the reviewed guard: it differs from HEAD, is a symlink or not a regular file, an
# installed git hook or scanner is not executable (git skips a pre-push hook it cannot execute, so the gate is simply
# OFF), the hook is installed without its scanner or exception file, a canonical file is not committed at HEAD, or git
# runs hooks from somewhere other than .git/hooks.
# NOT INSTALLED is informational (exit 0): a fresh clone has not installed them yet; that is not a repo defect,
# and the line says the guard is not active rather than staying quiet.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! tmp="$(mktemp -d)" || [[ -z "$tmp" || ! -d "$tmp" ]]; then
  echo "HOOK DRIFT: could not create a temp directory to read the HEAD blobs into — nothing was compared."; exit 1
fi
trap 'rm -rf "$tmp"' EXIT

rc=0
check_pair() {   # <label> <canonical, repo-relative> <installed> <install hint> <must be executable 0|1> <required 0|1>
  local label="$1" rel="$2" installed="$3" hint="$4" need_x="$5" required="$6" canon="$tmp/canon"
  if ! git -C "$ROOT" cat-file blob "HEAD:$rel" > "$canon" 2>/dev/null; then
    echo "HOOK DRIFT: $rel is not committed at HEAD — there is no reviewed copy for the ${label} to match."
    rc=1; return
  fi
  if ! git -C "$ROOT" diff --quiet HEAD -- "$rel" 2>/dev/null; then
    echo "hook drift check: note — $rel has uncommitted changes; installed copies are compared with HEAD, not with them."
  fi
  if [[ -L "$installed" ]]; then
    echo "HOOK DRIFT: the installed ${label} at $installed is a SYMLINK (to $(readlink -- "$installed")) — it runs"
    echo "  whatever it points at, so an edit there changes the gate without an install. Replace it with a copy: $hint"
    rc=1; return
  fi
  if [[ ! -e "$installed" ]]; then
    if [[ "$required" -eq 1 ]]; then
      echo "HOOK DRIFT: ${label} is missing at $installed, but the pre-push hook that runs it is installed —"
      echo "  the installed gate is not the reviewed one (a missing scanner refuses every push; a missing exception file"
      echo "  runs strict, so a push to a new remote blocks on the recorded fixture). install: $hint"
      rc=1; return
    fi
    echo "hook drift check: NOT INSTALLED — ${label} at $installed; that guard is not active on this machine."
    echo "  install: $hint"
    return
  fi
  if [[ ! -f "$installed" ]]; then
    echo "HOOK DRIFT: the installed ${label} at $installed is not a regular file. install: $hint"
    rc=1; return
  fi
  local ok=1
  if ! cmp -s "$canon" "$installed"; then
    echo "HOOK DRIFT: the RUNNING ${label} differs from the reviewed one (HEAD:$rel)."
    diff -u --label "HEAD:$rel" --label "$installed" "$canon" "$installed" | head -20
    echo "  → reconcile before pushing: the guard that runs must be the guard that was reviewed."
    ok=0; rc=1
  fi
  if [[ "$need_x" -eq 1 && ! -x "$installed" ]]; then
    echo "HOOK DRIFT: the installed ${label} at $installed is NOT EXECUTABLE — git skips a pre-push hook it cannot"
    echo "  execute, so the gate is off. install: $hint"
    ok=0; rc=1
  fi
  [[ "$ok" -eq 1 ]] && echo "hook drift check: OK — the installed ${label} matches HEAD:$rel"
  return 0
}

CC_INSTALLED="${SECRET_SCAN_INSTALLED:-$HOME/.claude/hooks/secret-scan.sh}"
check_pair "Claude Code push guard (secret-scan.sh)" scripts/secret-scan.sh "$CC_INSTALLED" \
  "git cat-file blob HEAD:scripts/secret-scan.sh > \"$CC_INSTALLED\" && chmod +x \"$CC_INSTALLED\"" 0 0

# The git hook files. PRE_PUSH_INSTALLED (tests) names the hook file; the scanner and the exception file it uses are
# ALWAYS the files beside it, exactly as scripts/pre-push.sh and scripts/secret-scan.sh resolve them.
COMMON="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || COMMON=""
PP_INSTALLED="${PRE_PUSH_INSTALLED:-}"
if [[ -z "$PP_INSTALLED" ]]; then
  PP_INSTALLED="${COMMON:-$ROOT/.git}/hooks/pre-push"
fi
HOOKDIR="$(dirname "$PP_INSTALLED")"
pp_present=0
[[ -e "$PP_INSTALLED" || -L "$PP_INSTALLED" ]] && pp_present=1
check_pair "git pre-push hook" scripts/pre-push.sh "$PP_INSTALLED" "bash scripts/install-pre-push.sh" 1 0
check_pair "git pre-push scanner copy (secret-scan.sh beside the hook)" scripts/secret-scan.sh \
  "$HOOKDIR/secret-scan.sh" "bash scripts/install-pre-push.sh" 1 "$pp_present"
check_pair "git pre-push exception file (secret-scan-ignore beside the hook)" scripts/secret-scan-ignore \
  "$HOOKDIR/secret-scan-ignore" "bash scripts/install-pre-push.sh" 0 "$pp_present"

# Where git ACTUALLY runs hooks from (MEDIUM-3). Resolved through `pwd -P` exactly as the installer resolves them.
if [[ -z "$COMMON" ]]; then
  echo "HOOK DRIFT: $ROOT is not a git repository — cannot tell where git runs hooks from."
  rc=1
else
  EFFECTIVE="$(git -C "$ROOT" rev-parse --path-format=absolute --git-path hooks 2>/dev/null)" || EFFECTIVE="(unknown)"
  REAL_HOOKS="$(cd "$COMMON" && pwd -P)/hooks"
  REAL_EFFECTIVE="$( (cd "$(dirname "$EFFECTIVE")" 2>/dev/null && pwd -P) || printf '%s' "$(dirname "$EFFECTIVE")")/$(basename "$EFFECTIVE")"
  HOOKS_PATH="$(git -C "$ROOT" config --show-origin --get-all core.hooksPath 2>/dev/null)"
  if [[ -n "$HOOKS_PATH" || "$REAL_EFFECTIVE" != "$REAL_HOOKS" ]]; then
    echo "HOOK DRIFT: git runs hooks from $EFFECTIVE, not $REAL_HOOKS — whatever is installed in .git/hooks does not run."
    [[ -n "$HOOKS_PATH" ]] && echo "  core.hooksPath is set: ${HOOKS_PATH//$'\n'/ · }"
    echo "  Unset core.hooksPath if it is set (git config [--global] --unset core.hooksPath), or replace a symlinked"
    echo "  .git/hooks with a real directory; then re-run bash scripts/install-pre-push.sh."
    rc=1
  fi
fi
exit "$rc"
