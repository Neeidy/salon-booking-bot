#!/usr/bin/env bash
# Install the git pre-push secret-scan gate into THIS repository's own hooks directory, FROM HEAD: the blobs committed
# at HEAD for scripts/pre-push.sh, scripts/secret-scan.sh and scripts/secret-scan-ignore become .git/hooks/pre-push,
# .git/hooks/secret-scan.sh and .git/hooks/secret-scan-ignore (the hook runs the scanner beside it and the scanner reads
# the exceptions beside itself — never the working tree; see scripts/pre-push.sh).
#
#   bash scripts/install-pre-push.sh            install (refuses to replace a DIFFERENT existing file)
#   bash scripts/install-pre-push.sh --force    replace it; the old one is kept beside it as <name>.bak.<epoch>
#
# FROM HEAD, NOT THE WORKING TREE (R1d M-A). Until R1d this copied the working-tree files while every comment said
# "committed", so an uncommitted, unreviewed edit was what got installed. Now it REFUSES, writing nothing, unless each of
# the three is tracked (`git ls-files --error-unmatch`) AND identical to HEAD (`git diff --quiet HEAD`); and even then
# the bytes come from the HEAD blob (`git cat-file blob`, raw: no textconv, no smudge filter), because a clean/smudge
# filter or an eol attribute can make the working-tree bytes differ while `git diff` calls them identical.
# Consequence, intended: commit the scripts before installing.
#
# CONFINED (R1 code review M3), and each refusal writes nothing:
#   - the target is `<git common dir>/hooks` of the repository this script lives in — there is no path override;
#   - if git would run hooks from somewhere else (core.hooksPath, local or global), it REFUSES: writing into
#     .git/hooks would install a hook that never runs, and writing into the other directory is outside this repo.
#     Since R1d it refuses ANY core.hooksPath, even one naming .git/hooks, because check-hook-drift.sh reports any;
#   - it refuses a hooks directory that is a symlink, and a target file that is a symlink or not a regular file;
#   - with --force, the backup name <name>.bak.<epoch> must not exist at all — not as a file, not as a symlink, not as a
#     dangling one (R1d LOW-2: `cp -p` onto a pre-placed link at that predictable name wrote THROUGH it). Every target
#     and every backup name is checked before anything is written, and the backup is a hard link made with `ln`, which
#     does not replace an existing name (it can follow a name that turns into a symlink to a directory AFTER that check —
#     a race, recorded as CONVERGE), so a refusal never leaves half an install;
#   - each file is written to a temp file in the hooks directory and renamed over the target, so it never writes
#     THROUGH a link, then verified: a regular file, not a symlink, byte-identical to its HEAD blob (`git hash-object
#     --no-filters` equals the blob id), and executable for pre-push and secret-scan.sh. secret-scan-ignore is data, not
#     code: it is installed 0644 and is not required to be executable.
# A COPY, not a symlink, so check-hook-drift.sh can say when the running hook is not the reviewed one.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

die() { echo "install-pre-push: REFUSED — $*" >&2; exit 1; }

# Install order: the hook (pre-push.sh) LAST, so it never exists without its scanner and exceptions beside it.
FILES=(secret-scan-ignore secret-scan.sh pre-push.sh)
declare -A NAME=([secret-scan-ignore]=secret-scan-ignore [secret-scan.sh]=secret-scan.sh [pre-push.sh]=pre-push)
declare -A MODE=([secret-scan-ignore]=0644 [secret-scan.sh]=0755 [pre-push.sh]=0755)
declare -A BLOB=()

git -C "$ROOT" rev-parse --verify -q HEAD >/dev/null || die "$ROOT has no HEAD commit; commit the scripts first"
for f in "${FILES[@]}"; do
  rel="scripts/$f"
  git -C "$ROOT" ls-files --error-unmatch -- "$rel" >/dev/null 2>&1 || die "$rel is not tracked; commit it first"
  git -C "$ROOT" diff --quiet HEAD -- "$rel" || die "$rel differs from HEAD (uncommitted or staged change); commit it first"
  BLOB[$f]="$(git -C "$ROOT" rev-parse --verify -q "HEAD:$rel")" || die "$rel is not in HEAD; commit it first"
  [[ "$(git -C "$ROOT" cat-file -t "${BLOB[$f]}")" == blob ]] || die "HEAD:$rel is not a blob (a symlink in HEAD is also a blob: its target text would be installed and then fail the API marker)"
done

COMMON="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)" || die "$ROOT is not a git repository"
HOOKS="$COMMON/hooks"
if [[ -L "$HOOKS" ]]; then
  die "$HOOKS is a symlink; the hooks would land outside this repository's git directory"
fi
if [[ -e "$HOOKS" && ! -d "$HOOKS" ]]; then
  die "$HOOKS exists and is not a directory"
fi
EFFECTIVE="$(git -C "$ROOT" rev-parse --path-format=absolute --git-path hooks)" || die "git could not name its hooks directory"
REAL_HOOKS="$(cd "$COMMON" && pwd -P)/hooks"
# Resolve through the PARENT so a not-yet-created hooks directory compares correctly.
REAL_EFFECTIVE="$( (cd "$(dirname "$EFFECTIVE")" 2>/dev/null && pwd -P) || printf '%s' "$(dirname "$EFFECTIVE")")/$(basename "$EFFECTIVE")"
if [[ "$REAL_EFFECTIVE" != "$REAL_HOOKS" ]]; then
  die "git runs hooks from $EFFECTIVE, not $HOOKS (core.hooksPath is set, or the hooks directory resolves elsewhere).
  A hook in .git/hooks would never run, and this installer does not write outside the repository."
fi
# A core.hooksPath that happens to name .git/hooks today is still a redirect one setting away from moving, and
# check-hook-drift.sh reports ANY core.hooksPath as drift — so it is refused here too, rather than installing a gate
# that the drift check calls broken the moment it runs.
if git -C "$ROOT" config --get-all core.hooksPath >/dev/null 2>&1; then
  die "core.hooksPath is set ($(git -C "$ROOT" config --show-origin --get-all core.hooksPath | tr '\n' ' ')); unset it first"
fi

# Same blob? `--no-filters`: compare raw bytes, whatever .gitattributes says about the path.
same_as_blob() {   # <file> <blob id>
  [[ "$(git -C "$ROOT" hash-object --no-filters -- "$1" 2>/dev/null)" == "$2" ]]
}

# Check EVERY target and EVERY backup name before writing ANY, so a refusal never leaves half an install.
EPOCH="$(date +%s)"
declare -A BACKUP=()
for f in "${FILES[@]}"; do
  t="$HOOKS/${NAME[$f]}"
  if [[ -L "$t" ]]; then die "$t is a symlink; refusing to write through it"; fi
  if [[ -e "$t" && ! -f "$t" ]]; then die "$t exists and is not a regular file"; fi
  if [[ -e "$t" ]] && ! same_as_blob "$t" "${BLOB[$f]}"; then
    if [[ "$FORCE" -ne 1 ]]; then
      die "a different ${NAME[$f]} already exists at $t. Read it first; re-run with --force to replace it (kept as ${NAME[$f]}.bak.<epoch>)."
    fi
    b="$t.bak.$EPOCH"
    if [[ -e "$b" || -L "$b" ]]; then
      die "the backup name $b already exists (or is a symlink, dangling or not); refusing to write through or over it"
    fi
    BACKUP[$f]="$b"
  fi
done

mkdir -p "$HOOKS"
put() {   # <file>
  local f="$1" t="$HOOKS/${NAME[$1]}" tmpf
  if [[ -n "${BACKUP[$f]:-}" ]]; then
    ln -- "$t" "${BACKUP[$f]}" || die "could not keep the old $t as ${BACKUP[$f]}"
  fi
  tmpf="$(mktemp "$HOOKS/.${NAME[$f]}.XXXXXX")" || die "could not create a temp file in $HOOKS"
  if ! { git -C "$ROOT" cat-file blob "${BLOB[$f]}" > "$tmpf" && chmod "${MODE[$f]}" "$tmpf" && mv -f "$tmpf" "$t"; }; then
    rm -f "$tmpf"; die "could not write $t"
  fi
  if [[ -L "$t" || ! -f "$t" ]] || ! same_as_blob "$t" "${BLOB[$f]}"; then
    die "the copy at $t is not a regular file byte-identical to HEAD:scripts/$f"
  fi
  if [[ "${MODE[$f]}" == 0755 && ! -x "$t" ]]; then
    die "the copy at $t is not executable"
  fi
}
for f in "${FILES[@]}"; do put "$f"; done
echo "install-pre-push: installed and verified from HEAD ($(git -C "$ROOT" rev-parse --short HEAD)) — $HOOKS/pre-push,"
echo "  $HOOKS/secret-scan.sh (both executable) and $HOOKS/secret-scan-ignore are byte-identical to their HEAD blobs"
