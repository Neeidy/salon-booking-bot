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

# EVERY redaction target, not just one. This guard read a single N8N_HOST until 2026-09-12, when a
# SECOND target had to be recorded — the machine's ORIGIN IP, needed for ssh because the Cloudflare
# hostname cannot carry it. Adding a value to CLAUDE.local.md while the guard still scanned only one
# would have created a secret with no control, which is the exact failure this repo keeps finding: a
# guard whose SCOPE does not match what it is asked to protect. Any `<NAME>_HOST=<value>` line counts.
# ⚠ Per-line trimming, deliberately. The first cut piped the whole multi-line list through
# `tr -d '[:space:]'`, which deletes the NEWLINES too: two targets became one mashed string that
# appears nowhere, so the guard went green on both of them. Caught by its own negative control, which
# is the only reason it was caught at all — the run said "clean" and looked exactly like a pass.
set -f   # a target containing a glob metacharacter must never expand against the working directory:
         # measured, an unquoted `*.x.test` became a FILENAME and the declared target went unscanned
         # while the guard still said clean (security-auditor, 2026-09-12).

TARGETS=""
if [ -n "${N8N_HOST:-}" ]; then TARGETS="$N8N_HOST"; fi
DECLARED=0
if [ -f CLAUDE.local.md ] && [ ! -r CLAUDE.local.md ]; then
  # Bulgu 3: `grep -c … || true` left DECLARED empty when the file could not be read, the numeric test
  # errored, and the guard fell through to its full green sentence with exit 0 — a FAIL-OPEN inside the
  # logic added to prevent fail-open. Unreadable is now an error, before any of that can happen.
  echo "host-leak guard: CANNOT CHECK — CLAUDE.local.md exists but is not readable"
  exit 2
fi
if [ -f CLAUDE.local.md ]; then
  # Count the lines that DECLARE a target and the values actually parsed out of them, then compare.
  # ⚠ Without this the guard drops a target in SILENCE — an empty `N8N_HOST=`, a lower-case name or an
  # indented line yields no value, the line disappears, and as long as one other target survives the
  # guard prints its full green sentence and exits 0 over a real leak (measured). A guard that cannot
  # say HOW MANY things it checked cannot distinguish "clean" from "checked nothing".
  DECLARED="$(grep -cE '^[[:space:]]*[A-Za-z0-9_]*[Hh][Oo][Ss][Tt][[:space:]]*=' CLAUDE.local.md || true)"
  more="$(sed -n 's/^[A-Z0-9_]*HOST=[[:space:]]*\([^[:space:]]*\).*/\1/p' CLAUDE.local.md)"
  TARGETS="$(printf '%s\n%s\n' "$TARGETS" "$more" | sed '/^$/d' | sort -u)"
  PARSED="$(printf '%s\n' "$more" | sed '/^$/d' | wc -l | tr -d ' ')"
fi

# Bulgu 5: mask LONGEST FIRST. The apex is a substring of the n8n hostname, so masking the short one
# first would leave `sub.<REDACTED-HOST>` — the sub-domain label in clear. It happened to be correct
# only because `sort -u` put the longer value first; correctness by alphabet is not correctness.
if [ -n "$TARGETS" ]; then
  TARGETS="$(printf '%s\n' "$TARGETS" | awk '{ print length($0), $0 }' | sort -rn | cut -d' ' -f2-)"
  case "$DECLARED" in ''|*[!0-9]*) DECLARED=-1 ;; esac
  if [ "$DECLARED" -ne "$PARSED" ]; then
    echo "host-leak guard: CANNOT CHECK — CLAUDE.local.md declares ${DECLARED} *HOST= line(s) but only"
    echo "  ${PARSED} yielded a value. A dropped target is indistinguishable from a clean scan, so this"
    echo "  is an error, not a warning. Expected form: NAME_HOST=<value>, upper-case, no leading space."
    exit 2
  fi
fi

if [ -z "$TARGETS" ]; then
  echo "host-leak guard: NOT CONFIGURED — set \$N8N_HOST or add '<NAME>_HOST=<value>' to CLAUDE.local.md"
  exit 2
fi
COUNT="$(printf '%s\n' "$TARGETS" | wc -l | tr -d ' ')"

leak=0

# git grep exit codes: 0 = found, 1 = not found, >1 = ERROR. Collapsing >1 into "not found" would turn a
# broken scan into a green report, so each scan separates the three.
scan_one() {
  local label="$1"; local HOST="$2"; shift 2
  local out rc
  out="$(git grep -nF "$@" -- "$HOST" 2>/dev/null)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "HOST LEAK — the production host appears in ${label}:"
    # file:line only, and the matched line is TRUNCATED with the host masked. Printing the full match
    # re-leaks the very value this guard protects — which is not hypothetical: drilling it against a
    # minified bundle dumped the host AND the Turnstile site key across the terminal (2026-09-09).
    # Mask EVERY target, not just the one that matched: a line naming two of them printed the other in
    # clear (measured). And mask LITERALLY — the value was being interpolated into a sed regex, so a
    # `#` broke the expression and a `\` made the mask fail silently, printing the value itself. The one
    # line that must never leak cannot depend on what the value happens to contain.
    # Bulgu 1: `awk -v x="…"` PROCESSES escape sequences, so a target containing a backslash arrived
    # mangled and was printed in clear — while the comment above claimed literal masking. ENVIRON does
    # no such processing. Bulgu 2: the old loop re-scanned from position 1 after each substitution, so a
    # target that is a substring of the replacement (`-`, `HOST`, `RED`) matched inside the mask forever
    # — an infinite loop that fires ONLY on the leak path, i.e. the guard hangs exactly when it has
    # something to report. Text is consumed left to right now and the loop cannot revisit it.
    printf '%s\n' "$out" | TARGETS="$TARGETS" awk '
      BEGIN { n = split(ENVIRON["TARGETS"], T, "\n") }
      { line = $0
        for (i = 1; i <= n; i++) if (T[i] != "") {
          out = ""; rest = line
          while ((p = index(rest, T[i])) > 0) {
            out = out substr(rest, 1, p - 1) "<REDACTED-HOST>"
            rest = substr(rest, p + length(T[i]))
          }
          line = out rest
        }
        print line }' | cut -c1-160 | sed 's/^/  /'
    leak=1
  elif [ "$rc" -gt 1 ]; then
    echo "host-leak guard: CANNOT CHECK — the ${label} scan failed (git grep exit ${rc})"
    exit 2
  fi
}

# Scanned in THIS shell, never in a subshell: a `while read` pipeline runs in a subshell and its
# `leak=1` would be discarded, which is a silent green of the same family as the bug above.
for t in $TARGETS; do
  scan_one "STAGED content (the index — this is what a commit ships)" "$t" --cached
  scan_one "a TRACKED working-tree file" "$t"
  scan_one "a new/untracked file" "$t" --untracked
done

if [ "$leak" -ne 0 ]; then exit 1; fi

echo "host-leak guard: clean — ${COUNT} redaction target(s) scanned across index, tracked files and new files"
exit 0
