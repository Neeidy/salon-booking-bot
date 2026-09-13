#!/usr/bin/env bash
# check-deploy-separation — the repo's half of "the dashboard never ships with the public site".
#
# WHY IT EXISTS. `web/dashboard` holds the only Airtable PAT and renders customer PII; `web/site` is a
# public deployment. Keeping them apart is Phase 6 decision D-1 and the third line of CRT #10. On
# 2026-09-12 that separation got WEAKER without anyone deciding it should: the dashboard joined the
# `web/` npm workspace, so it stopped being outside the site's tree and the whole guarantee collapsed
# onto one root-directory value in a web panel — a setting no clone can audit and no review can see.
#
# ⚠ THE BOUND, STATED FIRST SO IT IS NOT OVERSOLD: this script cannot prove Vercel honours anything. It
# proves the REPO's half in two ways, and that is all it claims:
#   A. the exclusion is DECLARED in git (`.vercelignore` names the dashboard), so the intent is
#      reviewable instead of living in a panel;
#   B. no publicly-deployed package REACHES the dashboard by import, which is the route by which a
#      bundler would pull it in even with the directory excluded.
# The platform half stays an operator fact. A config file alone could not be drilled in either
# direction — delete it and nothing turns red — which is precisely why this guard exists beside it.
#
# Usage: bash scripts/check-deploy-separation.sh
set -u -f
cd "$(dirname "$0")/.."

PRIVATE='web/dashboard'
PUBLIC_PKGS='web/site web/snippet web/shared'
fail=0

# ⚠ THE EXTENSION LIST IS PART OF THE GUARD, NOT DECORATION. The first version listed ts/tsx/js/mjs/cjs
# and `security-auditor` walked a dashboard import straight past it as `.jsx` and as `.mts` — and `.mts`
# is not hypothetical: `web/site/tsconfig.json` lists `**/*.mts` in its own `include`, so the repo calls
# it live source while the guard could not read it. Same failure class as the missing `-p` a day earlier:
# the control did not consume what the real world produces.
sources() {
  find "$1" -type d -name node_modules -prune -o -type d -name .next -prune -o \
    -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.mts' -o -name '*.cts' \
              -o -name '*.js' -o -name '*.jsx' -o -name '*.mjs' -o -name '*.cjs' \) -print
}

# ---- A. the declaration -------------------------------------------------------------------------
if [ ! -f .vercelignore ]; then
  echo "✗ .vercelignore is missing — the site/dashboard split would rest entirely on a panel setting."
  fail=1
elif ! grep -qE "^[[:space:]]*${PRIVATE}[[:space:]]*/?$" .vercelignore; then
  echo "✗ .vercelignore does not exclude '${PRIVATE}'. The split is then undeclared in git."
  fail=1
elif grep -qE "^[[:space:]]*!.*${PRIVATE}" .vercelignore; then
  # A NEGATION UNDOES THE EXCLUSION and the first version of this check could not see it: it asked only
  # whether the exclude line EXISTS. `!web/dashboard/lib` three lines below re-includes exactly the
  # directory holding the PAT, and the guard said OK (`security-auditor` M1, 2026-09-13).
  echo "✗ .vercelignore re-includes part of '${PRIVATE}' with a '!' negation — the exclusion is undone:"
  grep -nE "^[[:space:]]*!.*${PRIVATE}" .vercelignore | sed 's/^/      /'
  fail=1
else
  echo "  declared: .vercelignore excludes ${PRIVATE}, with no negation re-including it"
fi

# ---- B. the import graph ------------------------------------------------------------------------
# Source files only — a build artefact under .next legitimately contains many strings, and scanning it
# here would make the guard fail for a reason that is not a defect.
hits=0
for pkg in $PUBLIC_PKGS; do
  # ⚠ THIS WAS `|| continue`, AND THAT IS THIS FILE'S OWN DEFECT ONE LEVEL UP. `PUBLIC_PKGS` is a
  # hand-written list, and a hand-written list going stale is precisely what happened when
  # `web/dashboard` joined the workspace. With `continue`, moving or renaming `web/site` left the sweep
  # scanning the two small packages, printing "11 source files, 0 reach the dashboard" and exiting 0 —
  # the 26 files that actually matter had simply stopped existing as far as it was concerned
  # (`code-reviewer`, 2026-09-13). A package that is not there is NOT MEASURED, never clean.
  if [ ! -d "$pkg" ]; then
    echo "✗ NOT MEASURED — declared public package '$pkg' does not exist. Either the list is stale or"
    echo "  the tree moved; either way this sweep did not look where it claims to look."
    exit 2
  fi
  while IFS= read -r f; do
    # a real module reference to the private package: an import/require whose specifier reaches it
    if grep -nE "(from|require\(|import\(|^[[:space:]]*import)[[:space:]]*['\"][^'\"]*(@salon/dashboard|\.\./dashboard|/dashboard/(lib|components|app)/)" "$f" >/dev/null 2>&1; then
      echo "✗ ${f}: a publicly-deployed package imports from ${PRIVATE}"
      grep -nE "(from|require\(|import\(|^[[:space:]]*import)[[:space:]]*['\"][^'\"]*(@salon/dashboard|\.\./dashboard|/dashboard/(lib|components|app)/)" "$f" | sed 's/^/      /'
      hits=$((hits + 1))
    fi
  done <<EOF
$(sources "$pkg")
EOF
done

# THE INSTRUMENT CHECK (reporting.md: an empty result is a claim about the instrument). Zero hits is
# only meaningful if the sweep actually read files.
# Counted PER PACKAGE, never as a total: a total hides an empty package behind a healthy-looking number.
scanned=0
for pkg in $PUBLIC_PKGS; do
  n=$(sources "$pkg" | grep -c '')
  if [ "$n" -eq 0 ]; then
    echo "✗ NOT MEASURED — '$pkg' yielded 0 source files. A zero here is a broken sweep, not a clean one."
    exit 2
  fi
  scanned=$((scanned + n))
done
if [ "$scanned" -eq 0 ]; then
  echo "✗ NOT MEASURED — scanned 0 source files across: $PUBLIC_PKGS. A zero here is a broken sweep, not a clean one."
  exit 2
fi
[ "$hits" -eq 0 ] && echo "  import graph: $scanned source file(s) scanned, 0 reach ${PRIVATE}"
[ "$hits" -eq 0 ] || fail=1

# ---- C. symlinks out of the public tree -----------------------------------------------------------
# A text scan of import specifiers cannot see this: `web/site/lib/x -> ../../dashboard/lib` makes
# `./x/airtable` a perfectly ordinary-looking relative import. It is the same bypass as BULGU-3, which
# `check-client-imports.cjs` closed for its own rule class in CP 6c-1 and which reappeared here in a new
# file the day it was written (`security-auditor` M1, 2026-09-13).
PRIVATE_REAL="$(cd "$PRIVATE" 2>/dev/null && pwd -P || echo '/nonexistent')"
for pkg in $PUBLIC_PKGS; do
  [ -d "$pkg" ] || continue
  while IFS= read -r link; do
    [ -n "$link" ] || continue
    # ⚠ The first version read the link AFTER cd-ing into its directory, so the RELATIVE path in `$link`
    # no longer resolved, `readlink` returned empty, and every symlink looked like it pointed at its own
    # parent — the check ran, printed nothing, and passed. A guard that walks its own feet: exactly the
    # shape this file's header warns about, committed inside the fix for it. Resolve first, then compare.
    tgt="$(readlink -f "$link" 2>/dev/null || true)"
    case "${tgt:-}" in
      "$PRIVATE_REAL"|"$PRIVATE_REAL"/*)
        echo "✗ ${link}: a symlink from a publicly-deployed package reaches ${PRIVATE}"
        fail=1 ;;
    esac
  done <<EOF
$(find "$pkg" -type d -name node_modules -prune -o -type l -print)
EOF
done

# ---- D. hardlinks -------------------------------------------------------------------------------
# ⚠ THE OTHER HALF OF BULGU-3, and it was left open in the same file that names BULGU-3 in section C.
# `realpath` does NOT resolve a hardlink — a hardlink has its own genuine path, so a dashboard source
# hardlinked into `web/site` is, by every path-based test, an ordinary file of the site. It reaches the
# deployment without ever appearing in the import graph. `check-client-imports.cjs` closed exactly this
# for its own rule class with a `(dev, inode)` identity; the same method, here (`code-reviewer`,
# 2026-09-13). A class closed in one guard is not closed in the next one.
if [ -d "$PRIVATE" ]; then
  priv_ids="$(find "$PRIVATE" -type d -name node_modules -prune -o -type f -printf '%D:%i\n' 2>/dev/null | sort -u)"
  if [ -z "$priv_ids" ]; then
    echo "✗ NOT MEASURED — could not read any inode under ${PRIVATE}; the hardlink check did not run."
    exit 2
  fi
  for pkg in $PUBLIC_PKGS; do
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      pid="${line%% *}"; pfile="${line#* }"
      case "$priv_ids" in
        *"$pid"*)
          # printf %D:%i is the same (device, inode) pair the sibling guard keys on.
          echo "✗ ${pfile}: shares an inode with a file under ${PRIVATE} — a HARDLINK, which no path"
          echo "      test can see. The dashboard's bytes would ship inside the public package."
          fail=1 ;;
      esac
    done <<EOF
$(find "$pkg" -type d -name node_modules -prune -o -type d -name .next -prune -o -type f -links +1 -printf '%D:%i %p\n' 2>/dev/null)
EOF
  done
fi

if [ "$fail" -ne 0 ]; then
  echo "deploy-separation: FAILED"
  exit 1
fi
echo "deploy-separation: OK — the split is declared in git and no public package imports the dashboard."
echo "  NOT PROVEN HERE: that Vercel honours it. That is the project's root-directory setting, which"
echo "  lives in a web panel and is an operator fact, not a repo fact."
