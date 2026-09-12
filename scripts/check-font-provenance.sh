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

# MIRROR surfaces — any second public/ that serves the same faces. One PROVENANCE record, checked in
# every place, because a second copy with no guard is how a vetted font becomes an unvetted one.
#
# ⚠ There is NO mirror today, and the honest history is why this stays: during CP 6c-1 the fonts were
# copied into web/dashboard/public/fonts to reproduce the mockup, and THIS GUARD PRINTED OK over the
# new, unrecorded surface. The extension was written, drilled red four ways, and then the copy turned
# out to be unnecessary — `web/site` uses `next/font/google`, which self-hosts at build time, so the
# dashboard needs no font files of its own. The directory was removed; the check was not, because the
# thing that made it necessary was one `cp` and that `cp` can happen again. It costs one `[ -d ]` per
# run and it is proven fail-able.
MIRRORS="web/dashboard/public/fonts"
MIRROR_PUBLIC="web/dashboard/public"

[ -f "$REC" ] || { echo "font-provenance: CANNOT CHECK — $REC not found"; exit 2; }
command -v sha256sum >/dev/null 2>&1 || { echo "font-provenance: CANNOT CHECK — sha256sum unavailable"; exit 2; }

fail=0
checked=0
mirrored=0
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
  # Same file, same record, second deployment. A mirror that EXISTS must match; a tree with no
  # dashboard is a valid tree, so an absent mirror is not an error. A mirror that is PRESENT and
  # DIFFERENT is the supply-chain shape this guard is for. ⚠ Written AFTER the fonts were copied and
  # this guard still printed OK — measured, not imagined: the copy created an unrecorded font surface
  # and the guard could not see it, which is the exact defect it was extended to close.
  for m in $MIRRORS; do
    [ -d "$m" ] || continue
    if [ ! -f "$m/$file" ]; then
      echo "font-provenance: MISSING mirror $m/$file — the directory exists, so the face must too"
      fail=1; continue
    fi
    mactual=$(sha256sum "$m/$file" | cut -d' ' -f1)
    mirrored=$((mirrored + 1))
    if [ "$mactual" != "$sum" ]; then
      echo "font-provenance: MIRROR MISMATCH $m/$file"
      echo "  recorded: $sum"
      echo "  actual:   $mactual"
      fail=1
    fi
  done
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

# ⚠ This sweep sits BEFORE the fail gate, and it did not on the first cut: it set `fail=1` AFTER
# `[ "$fail" -eq 0 ] || exit 1` had already run, so the guard printed "UNRECORDED font" and then
# printed OK and exited 0 in the same breath. Detect-then-discard — the same shape as a bound that
# drops the very thing it detected. Caught by its own negative control, not by reading it.
# The mirror gets the same EQUALITY sweep: an unrecorded face dropped into the dashboard's public/
# ships from the dashboard exactly as it would from the site.
for mp in $MIRROR_PUBLIC; do
  [ -d "$mp" ] || continue
  while IFS= read -r rel; do
    # ⚠ PATH, not basename. The first cut compared `basename`, so `fonts/sub/fraunces-variable.woff2`
    # matched the record and passed — while the SAME file under web/site/public was caught, because
    # that sweep compares the path relative to public/. Next serves both identically. This is the
    # "four silent passes" defect documented above, reborn in the copy: a second implementation of one
    # rule drifts (security-auditor S5, 2026-09-12).
    case "$rel" in
      fonts/*/*) echo "font-provenance: UNRECORDED font served from $mp — $rel (in a SUBDIRECTORY)"; fail=1; continue ;;
    esac
    base="${rel#fonts/}"
    case "$rel" in
      fonts/*) ;;
      *) echo "font-provenance: UNRECORDED font served from $mp — $rel (outside fonts/)"; fail=1; continue ;;
    esac
    if ! grep -qiE "^- stored: *$base\$" "$REC"; then
      echo "font-provenance: UNRECORDED font served from $mp — $rel"
      fail=1
    fi
  done < <(find "$mp" -type f \( -iname '*.woff2' -o -iname '*.woff' -o -iname '*.ttf' -o -iname '*.otf' \) -printf '%P\n' 2>/dev/null)
done

# ⚠ THE FAIL GATE. It was deleted by accident while the mirror sweep was being rewritten, and for
# one run this script printed OK and exited 0 over a leak it had just detected and announced —
# the SECOND time this exact shape appeared in this file. Its own negative control caught it both
# times. Nothing between the last `fail=1` and this line may print a verdict.
[ "$fail" -eq 0 ] || exit 1

# ⚠ `${mirrored:+…}` expands on the STRING "0" too — it tests set-and-non-empty, not non-zero — so the
# verdict line claimed "+0 mirror copy verified" and named a directory the sweep had SKIPPED with
# `[ -d ]`. A verdict that counts a check it did not run is the failure class this whole file is
# about (`code-reviewer` #7, 2026-09-12). Both halves are now conditioned on what actually happened.
mirror_note=''
[ "$mirrored" -gt 0 ] && mirror_note=" (+$mirrored mirror copy verified)"
mirror_scope=''
[ -n "${MIRROR_PUBLIC:-}" ] && [ -d "$MIRROR_PUBLIC" ] && mirror_scope=" or $MIRROR_PUBLIC"
echo "font-provenance: OK — $checked recorded font(s) match their checksums$mirror_note, and no unrecorded .woff2/.woff/.ttf/.otf is served from $PUBLIC$mirror_scope"

# KNOWN LIMIT, stated rather than implied: this proves the bytes on disk are the bytes we RECORDED, and
# that nothing unrecorded ships. It does NOT prove the recorded bytes are the upstream author's — a
# coordinated change to both the file and its checksum passes. Comparing against the upstream blob is a
# named open item, deliberately not done in this round.
exit 0
