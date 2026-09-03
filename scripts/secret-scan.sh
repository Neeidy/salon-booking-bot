#!/usr/bin/env bash
# PreToolUse hook: block `git push` when the COMMITS BEING PUSHED contain a likely secret.
# Runs even under bypassPermissions.
#
# ── INSTALL (this file is the CANONICAL copy; the hook runs from ~/.claude/hooks/) ──────────────
#   cp scripts/secret-scan.sh ~/.claude/hooks/secret-scan.sh && chmod +x ~/.claude/hooks/secret-scan.sh
# and wire it in ~/.claude/settings.json as a PreToolUse hook for the Bash tool:
#   {"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[
#     {"type":"command","command":"/home/<you>/.claude/hooks/secret-scan.sh"}]}]}}
# Verify the installed copy has not drifted from this one:  bash scripts/check-hook-drift.sh
#
# WHY THIS LIVES IN THE REPO (2026-09-03): a security control that exists only on one machine cannot be
# REVIEWED — Codex cannot see it, Cowork reviews from git and cannot see it, and it disappears with the
# machine. That is precisely how this hook stayed broken for the entire project: nobody could look at it,
# so nobody noticed it was scanning nothing.
#
# WHY THIS SHAPE — three defects found by drilling it, 2026-09-03:
#  1. SCOPE. v1 scanned `git diff --cached` — the STAGED area. By push time you have already committed,
#     so that area is empty: separate `git commit` and `git push` commands bypassed the hook entirely.
#     It was decor. A guard's scope must match the moment it runs → scan `<upstream>..HEAD`.
#  2. NOISE. v1 matched bare words (api_key|secret|password|bearer), so honest prose — "no secret found",
#     "NON-SECRET config" — blocked pushes. A guard that cries wolf gets switched off, and a switched-off
#     guard is worse than none because you think you are covered → match VALUE SHAPES, not words.
#  3. SILENT BREAKAGE. `grep -E '^\+'` is GNU-safe but ugrep (the grep on this machine) rejects it; the
#     pipeline errored, `|| true` swallowed it, and the hook approved everything while scanning nothing.
#     → portable character classes, plus a self-check that FAILS LOUD if the scan comes back empty while
#     commits are pending.
# Payload goes to a temp FILE, not a shell variable: re-piping ~1MB through bash printf once per rule
# took 15s for a single commit and timed out on five (measured) — and a slow hook is disabled like a
# noisy one.
set -uo pipefail

input="$(cat)"
tool="$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null || echo '')"
cmd="$(printf  '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || echo '')"

[[ "$tool" == "Bash" && "$cmd" == *"git push"* ]] || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# ── SCOPE: exactly what is about to leave this machine ────────────────────────
base=""
if up="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" && [[ -n "$up" ]] \
   && git rev-parse --verify -q "$up" >/dev/null 2>&1; then
  base="$up"
elif git rev-parse --verify -q 'HEAD~1' >/dev/null 2>&1; then
  base="HEAD~1"
fi

if [[ -n "$base" ]]; then
  git diff -U0 "$base..HEAD" 2>/dev/null | grep -E '^[+]' | grep -v -E '^[+][+][+]' > "$tmp/raw" || true
  git log "$base..HEAD" --format='%B' 2>/dev/null >> "$tmp/raw" || true
  ahead="$(git rev-list --count "$base..HEAD" 2>/dev/null || echo 0)"
else
  git show -U0 --format= HEAD 2>/dev/null | grep -E '^[+]' | grep -v -E '^[+][+][+]' > "$tmp/raw" || true
  git log -1 --format='%B' 2>/dev/null >> "$tmp/raw" || true
  ahead=1
fi

# Self-check: commits pending but nothing extracted = the scan itself broke. Never approve unscanned.
if [[ ! -s "$tmp/raw" ]]; then
  if [[ "${ahead:-0}" -gt 0 ]] && [[ -n "$(git log -1 --format=%H 2>/dev/null)" ]] \
     && [[ "$(git diff --shortstat "$base..HEAD" 2>/dev/null)" != "" ]]; then
    echo "BLOCKED: secret-scan could not read the ${ahead} commit(s) being pushed — it will not approve" >&2
    echo "a push it did not actually scan. Fix the hook; do not bypass it." >&2
    exit 2
  fi
  exit 0
fi

# ── EXCLUSIONS: shapes that look secret-ish but are not. Each is a real FP from this repo. ──
EXCLUDE='("integrity"|"resolved"|sha512-|sha1-|REPLACE_WITH_|PLACEHOLDER|__REDACTED__|example\.com|process\.env\.|os\.environ|\$\{?[A-Z_]{3,}\}?|\$credentials|<your-|xxxx)'
grep -Ev -- "$EXCLUDE" "$tmp/raw" > "$tmp/cand" || true
[[ -s "$tmp/cand" ]] || exit 0

# ── RULES: value SHAPES ──────────────────────────────────────────────────────
declare -a RULES=(
  "anthropic key|sk-ant-[A-Za-z0-9_-]{20,}"
  "openai key|(^|[^A-Za-z0-9])sk-[A-Za-z0-9]{32,}"
  "github token|(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}"
  "aws access key|AKIA[0-9A-Z]{16}"
  "google api key|AIza[0-9A-Za-z_-]{35}"
  "slack token|xox[baprs]-[A-Za-z0-9-]{10,}"
  "airtable pat|pat[A-Za-z0-9]{14}\.[0-9a-f]{64}"
  "telegram bot token|[0-9]{8,10}:AA[A-Za-z0-9_-]{32,}"
  "private key block|BEGIN [A-Z ]*PRIVATE KEY"
  "jwt|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
  "secret assigned a real value|(api[_-]?key|secret|token|password|passwd|auth[_-]?key)[\"' ]*[:=][\"' ]*[A-Za-z0-9/+_-]{24,}"
)

hits=0
for rule in "${RULES[@]}"; do
  name="${rule%%|*}"; pat="${rule#*|}"
  # `grep -c` prints the count AND exits 1 when the count is zero, so a naive `|| echo 0` produced
  # "0\n0" and broke the arithmetic test. Capture, then keep digits only.
  n="$(grep -Eic -- "$pat" "$tmp/cand" 2>/dev/null || true)"
  n="${n//[^0-9]/}"; n="${n:-0}"
  [[ "$n" -gt 0 ]] || continue
  hits=$((hits + n))
  # Report the rule and a masked excerpt — never echo the value itself.
  grep -Ei -- "$pat" "$tmp/cand" 2>/dev/null | head -3 \
    | cut -c1-60 | sed -E 's/[A-Za-z0-9_-]{12,}/<redacted>/g' | sed "s/^/  ✗ ${name}: /" >&2
done

if (( hits > 0 )); then
  echo "BLOCKED: the commits about to be pushed contain ${hits} possible secret(s) (see above)." >&2
  echo "Scope scanned: ${base:-HEAD}..HEAD. Remove it, ROTATE it if it ever left this machine, then push." >&2
  exit 2
fi
exit 0
