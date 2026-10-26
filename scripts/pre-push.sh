#!/usr/bin/env bash
# git pre-push hook — THE secret-scan gate (7-2 Tur 2, replacing command-form parsing; docs/codex/7-2/4.md H4).
# Canonical copy: scripts/pre-push.sh. scripts/install-pre-push.sh installs the version COMMITTED AT HEAD as
# `.git/hooks/pre-push`, TOGETHER WITH HEAD's scripts/secret-scan.sh and scripts/secret-scan-ignore beside it; it refuses
# while any of the three is untracked or differs from HEAD. scripts/check-hook-drift.sh reports when an installed copy
# differs from its HEAD blob, is a symlink, or (hook and scanner) is not executable.
#
# WHY A GIT HOOK: the Claude Code hook sees a command STRING and has to guess whether it pushes — `git -C <dir> push`
# and `git -c k=v push` walked past it. git runs this hook for every push, whatever the command looked like, and
# tells it on stdin exactly what is being pushed: one line per ref, `<local ref> <local sha> <remote ref> <remote sha>`,
# with the remote's NAME (or its URL, when the push names no configured remote) as $1.
#
# WHICH SCANNER: the copy BESIDE THIS FILE, never the working tree's scripts/secret-scan.sh. The hook used to run the
# working-tree copy, so an uncommitted (or checked-out, or pulled) edit to the scanner changed the gate without
# anyone installing or reviewing anything (R1 security review H2). The installed copy changes only through the
# installer, and check-hook-drift.sh says when it differs from the file committed at HEAD. A SYMLINK there would bring
# that class straight back (a link to scripts/secret-scan.sh follows the working tree), so a symlinked scanner or
# exception file is refused, and so is running this hook through a symlink (R1d LOW-3). That last check stops an honest
# `ln -s` install; it cannot stop an edited working-tree hook, which would simply not contain it — check-hook-drift.sh
# reports the link either way.
#
# WHAT IS SCANNED, per pushed ref: `<local sha> [^<remote sha>] [--not --remotes=<$1>]` — every commit that the
# REMOTE BEING PUSHED TO does not already have, merges included, plus the text of every annotated tag on the way.
#   - Only THIS remote's tracking refs are excluded. `--not --remotes` (all remotes) skipped a commit that sat on a
#     second remote but not on the target, and that commit then reached the target unscanned (R1 code review H1).
#   - $1 is a URL (no remote of that name), or a name that has another remote nested under it (`--remotes=a` also
#     matches the tracking refs of a remote called `a/b`): nothing is excluded by tracking refs.
#   - `^<remote sha>`: the remote's current tip for this ref, when non-zero and present locally — its history is on
#     the target already. It goes BEFORE `--not`, which would otherwise flip it into a positive tip.
# A deleted ref (all-zero local sha) carries no content and is skipped. A commit the TARGET already has is not
# re-scanned; one that is public ELSEWHERE but absent from the target IS — a push to a new or empty remote, or to a URL,
# scans the whole history from the root commit. A known historical fixture would block that forever, which is what
# the fingerprint exceptions in secret-scan-ignore (installed beside the scanner) are for; for a real secret that
# has already left, the remedy is rotation, not an exception.
#
# FAILS CLOSED: no repository, no scanner beside this file, a scanner without the API 3 marker (an older copy), a
# symlinked scanner or exception file, a hook run through a symlink, or any non-zero scan → the push is refused. A
# gate that passes when it could not look is the defect this repo keeps finding.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || {
  echo "pre-push: BLOCKED — cannot locate the hook's own directory." >&2; exit 1; }
SCAN="$HERE/secret-scan.sh"
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "pre-push: BLOCKED — not inside a git repository, nothing could be scanned." >&2; exit 1
fi
if [[ -L "${BASH_SOURCE[0]}" ]]; then
  echo "pre-push: BLOCKED — this hook is running through a symlink (${BASH_SOURCE[0]}); install a copy with" >&2
  echo "  scripts/install-pre-push.sh so that a working-tree edit cannot change the gate." >&2; exit 1
fi
for f in "$SCAN" "$HERE/secret-scan-ignore"; do
  if [[ -L "$f" ]]; then
    echo "pre-push: BLOCKED — $f is a symlink; the gate runs only regular files installed beside it." >&2
    echo "  Remove the link and re-run scripts/install-pre-push.sh." >&2; exit 1
  fi
done
if [[ ! -f "$SCAN" ]]; then
  echo "pre-push: BLOCKED — $SCAN is missing; re-run scripts/install-pre-push.sh." >&2; exit 1
fi
if ! grep -q '^SECRET_SCAN_API=3' "$SCAN"; then
  echo "pre-push: BLOCKED — $SCAN is not an API 3 scanner (SECRET_SCAN_API=3); re-run scripts/install-pre-push.sh." >&2
  exit 1
fi

# Exclude only what the target already has (see the header).
REMOTE="${1:-}"
EXCL=()
known=0
nested=0
if [[ -n "$REMOTE" && "$REMOTE" != *[\*\?\[]* ]]; then
  while IFS= read -r r; do
    [[ "$r" == "$REMOTE" ]] && known=1
    [[ "$r" == "$REMOTE/"* ]] && nested=1
  done < <(git remote)
fi
if [[ "$known" -eq 1 && "$nested" -eq 0 ]]; then
  EXCL=(--not "--remotes=$REMOTE")
else
  echo "pre-push: '${REMOTE:-?}' is not a plainly named remote — no tracking refs excluded, the whole new range is scanned." >&2
fi

rc=0
refs=0
while read -r lref lsha rref rsha || [[ -n "${lref:-}" ]]; do
  [[ -n "${lref:-}" ]] || continue
  if [[ "${lsha:-}" =~ ^0+$ ]]; then
    echo "pre-push: ${rref:-?} is being deleted — no content to scan." >&2
    continue
  fi
  refs=$((refs + 1))
  args=("$lsha")
  if [[ -n "${rsha:-}" && ! "$rsha" =~ ^0+$ ]] && git cat-file -e "${rsha}^{commit}" 2>/dev/null; then
    args+=("^$rsha")
  fi
  if ! bash "$SCAN" --revs "${args[@]}" ${EXCL[@]+"${EXCL[@]}"} </dev/null; then
    echo "pre-push: BLOCKED — ${lref} → ${rref:-?} failed the secret scan." >&2
    rc=1
  fi
done
[[ "$refs" -gt 0 ]] || echo "pre-push: no ref with content to scan." >&2
exit "$rc"
