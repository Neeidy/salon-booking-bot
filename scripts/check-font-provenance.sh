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
PUBLIC="web/site/public"
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

# EQUALITY, not containment. Until 2026-09-11 this script walked the RECORD and verified each entry had a
# matching file — so it could only ever find a font it already knew about. A .woff2 dropped into the
# shipped directory with no provenance entry passed silently, which is the exact shape of the supply-chain
# problem the script exists to catch (Codex CRT #13, finding 8). The set of files on disk and the set of
# recorded entries must be IDENTICAL in both directions.
# ⚠ SCOPE, and the sentence below is written to match it — not the other way round. The first version of
# this block searched `-maxdepth 1 -name '*.woff2'` inside $DIR while CLAIMING "the shipped set equals the
# recorded set". Four silent passes were produced against that claim within the hour: a .woff2 in a
# SUBDIRECTORY, a .ttf/.woff beside the recorded files, an UPPERCASE .WOFF2, and a .woff2 in public/ but
# outside fonts/. All four are served by Next from public/, so all four ship. The claim was written in the
# same keystroke as the check, which is the one thing `reporting.md` forbids about guards.
# It now searches the WHOLE public tree, case-insensitively, for every font extension a browser will load.
ondisk=$(find "$PUBLIC" -type f \( -iname '*.woff2' -o -iname '*.woff' -o -iname '*.ttf' -o -iname '*.otf' \) \
  -printf '%P\n' 2>/dev/null | sed 's|^fonts/||' | sort -u)
recorded=$(grep -oE '^- stored: *.+\.woff2' "$REC" | sed 's/^- stored: *//' | sort -u)
unrecorded=$(comm -13 <(printf '%s\n' "$recorded") <(printf '%s\n' "$ondisk"))
if [ -n "$unrecorded" ]; then
  echo "font-provenance: UNRECORDED FONT SHIPPED — served from $PUBLIC with no entry in $REC:"
  printf '  %s\n' "$unrecorded"
  echo "  A font nobody recorded is a font nobody vetted. Add its origin, commit and sha256 to $REC."
  fail=1
fi

[ "$fail" -eq 0 ] || exit 1
echo "font-provenance: OK — $checked recorded font(s) match their checksums, and no unrecorded .woff2/.woff/.ttf/.otf is served from $PUBLIC"

# KNOWN LIMIT, stated rather than implied: this proves the bytes on disk are the bytes we RECORDED, and
# that nothing unrecorded ships. It does NOT prove the recorded bytes are the upstream author's — a
# coordinated change to both the file and its checksum passes. Comparing against the upstream blob is a
# named open item, deliberately not done in this round.
exit 0
