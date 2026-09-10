#!/usr/bin/env bash
# Font provenance guard — the control for a class that scanning CANNOT cover.
#
# `scripts/secret-scan.sh` reads diffs as text and a binary blob has no text lines, so nothing this repo
# runs can look inside a committed .woff2. That is the limit of the tool class, not a bug to fix. For the
# fonts the honest control is PROVENANCE: each file was fetched from the authors' own repository at a
# pinned commit, and its size and sha256 were recorded. This script re-verifies that the bytes in the tree
# are still those bytes — so a swapped or tampered font fails the close gate instead of shipping silently.
#
# Exit: 0 = every recorded checksum matches · 1 = MISMATCH or a file is missing · 2 = cannot check.
set -u

DIR="web/site/public/fonts"
REC="$DIR/PROVENANCE.md"

[ -f "$REC" ] || { echo "font-provenance: CANNOT CHECK — $REC not found"; exit 2; }
command -v sha256sum >/dev/null 2>&1 || { echo "font-provenance: CANNOT CHECK — sha256sum unavailable"; exit 2; }

fail=0
checked=0
# Read the `- stored:` / `- sha256:` pairs straight out of the provenance record, so the record IS the
# expectation — a second hard-coded list here would be the drift contract-integrity.md forbids.
while read -r file; do
  sum=$(awk -v f="$file" '
    $0 ~ "stored: *" f "$" { found=1 }
    found && /sha256:/ { sub(/.*sha256: */, ""); print; exit }
  ' "$REC")
  [ -n "$sum" ] || { echo "font-provenance: no sha256 recorded for $file"; fail=1; continue; }
  [ -f "$DIR/$file" ] || { echo "font-provenance: MISSING file $DIR/$file"; fail=1; continue; }
  actual=$(sha256sum "$DIR/$file" | cut -d' ' -f1)
  checked=$((checked + 1))
  if [ "$actual" != "$sum" ]; then
    echo "font-provenance: MISMATCH $file"
    echo "  recorded: $sum"
    echo "  actual:   $actual"
    fail=1
  fi
done < <(grep -oE '^- stored: *.+\.woff2' "$REC" | sed 's/^- stored: *//')

[ "$checked" -gt 0 ] || { echo "font-provenance: CANNOT CHECK — no font entries found in $REC"; exit 2; }
[ "$fail" -eq 0 ] || exit 1
echo "font-provenance: OK — $checked font(s) match the checksums recorded in $REC"
exit 0
