#!/bin/bash
# demo-offline.sh — take the public demo offline in one step, and MEASURE that it is (public demo plan §4, ruling D6).
#
# Pausing the Vercel project makes Vercel answer the demo with 503 and DEPLOYMENT_PAUSED in the body: the site and the chat widget
# are gone. It does NOT stop the engine: its webhook stays up, bounded by the LLM cap, the edge rate limit (30 requests
# per 10 s per IP and Cloudflare data centre; shown blocking in R2c) and the per-conversation turn cap — stopping the
# engine is the kill-switch or deactivating Main (⚠ ONAY, not this script).
# D6: a STANDING approval covers this pause in an emergency; unpausing and deactivating Main are not covered by it.
#
#   measure   GET the demo's front page: 200 → "online", exit 0 · Vercel's PAUSED answer — 503 with DEPLOYMENT_PAUSED in
#             the body, the form Vercel documents (vercel.com/docs/errors/DEPLOYMENT_PAUSED) → "offline", exit 3 · no
#             answer at all (000: timeout, DNS, network) → "NOT measured", exit 4 · ANY other answer (a 401 from deployment
#             protection, a 404 from a wrong domain, a redirect, a 503 without the marker) → "unexpected", exit 5 — it is
#             not counted as offline (R2a: the convergence residue of code-reviewer MEDIUM-5). Needs no token.
#   pause     POST Vercel's pause endpoint, then poll until the page gives Vercel's paused answer → exit 0 (else 1).
#   unpause   POST Vercel's unpause endpoint, then poll until the page answers 200 → exit 0 (else 1).
#
# The token: VERCEL_TOKEN, VERCEL_PROJECT_ID (and VERCEL_TEAM_ID when the project is in a team) come from an env
# file (--env FILE, default ~/.vercel-demo.env) that must be a regular file owned by this user with no group/other
# permission bits. The token is written into a 0600 temporary header file that curl reads with -H @file, so it is
# never on a command line, never printed, never in a log; the file is removed on exit. The script prints HTTP
# statuses and states only — never the token, the project id or the hostname.
# The hostname: "demo." + APEX_HOST from CLAUDE.local.md (the parse scripts/check-no-host-leak.sh uses), or DEMO_URL.
# Test seams: VERCEL_API_URL (https://…, or http://127.0.0.1:… only — the token goes where it points), DEMO_URL,
# POLL_S (tests/unit/demo-offline.test.py runs it against a local stand-in).
#
# Usage: bash scripts/demo-offline.sh measure|pause|unpause [--env FILE]
# Exit: 0 the asked-for state was measured · 1 refused by the API or the state was not reached · 2 usage or setup ·
#       3 (measure only) offline: Vercel's paused answer · 4 (measure only) no answer — nothing was measured ·
#       5 (measure only) an answer that is neither online nor Vercel's paused answer.
set -uo pipefail
set +x
unset VERCEL_TOKEN VERCEL_PROJECT_ID VERCEL_TEAM_ID   # drop any value (and export) the caller's environment carried

ACTION=${1:-}
ENV_FILE="$HOME/.vercel-demo.env"
case "$#:${2:-}" in
  1:) ;;
  3:--env) [ -n "$3" ] || { echo "demo-offline: --env needs a file"; exit 2; }; ENV_FILE=$3 ;;
  *) echo "usage: bash scripts/demo-offline.sh measure|pause|unpause [--env FILE]"; exit 2 ;;
esac
API=${VERCEL_API_URL:-https://api.vercel.com}
# No userinfo (`@`): `http://127.0.0.1:1@elsewhere` would send the token to `elsewhere` (code-reviewer, measured).
if [[ "$API" == *@* ]] || ! [[ "$API" =~ ^https://[^/]+(/|$) || "$API" =~ ^http://127\.0\.0\.1:[0-9]+(/|$) ]]; then
  echo "demo-offline: VERCEL_API_URL must be https:// (or http://127.0.0.1:<port> for the test), with no user part"; exit 2
fi
POLL_S=${POLL_S:-90}
ROOT=$(cd "$(dirname "$0")/.." && pwd)

demo_url() {
  if [ -n "${DEMO_URL:-}" ]; then echo "$DEMO_URL"; return; fi
  local apex
  apex=$(sed -n 's/^APEX_HOST=[[:space:]]*\([^[:space:]]*\).*/\1/p' "$ROOT/CLAUDE.local.md" 2>/dev/null | head -1 \
         | sed -E "s/^[\"']+//; s/[\"']+\$//")
  [ -n "$apex" ] || return 1
  echo "https://demo.$apex/"
}

# Prints 200, "paused" (503 + DEPLOYMENT_PAUSED in the body), another status code, or 000 for no answer.
measure_state() {
  local out code
  out=$(curl -4 -s -m 15 -w '\n%{http_code}' "$1" 2>/dev/null || true)
  code=${out##*$'\n'}
  if [ "$code" = 503 ] && [[ "${out%$'\n'*}" == *DEPLOYMENT_PAUSED* ]]; then echo paused; else echo "${code:-000}"; fi
}

case "$ACTION" in
  measure|pause|unpause) ;;
  *) echo "usage: bash scripts/demo-offline.sh measure|pause|unpause [--env FILE]"; exit 2 ;;
esac

URL=$(demo_url) || { echo "demo-offline: no DEMO_URL and no APEX_HOST line in CLAUDE.local.md"; exit 2; }

if [ "$ACTION" = measure ]; then
  code=$(measure_state "$URL")
  if [ "$code" = 200 ]; then echo "demo: online (200)"; exit 0; fi
  if [ "$code" = paused ]; then echo "demo: offline (503 DEPLOYMENT_PAUSED)"; exit 3; fi
  if [ -z "$code" ] || [ "$code" = 000 ]; then echo "demo: NOT measured (no answer)"; exit 4; fi
  echo "demo: unexpected answer ($code) — neither online nor Vercel's paused answer; NOT counted as offline"; exit 5
fi

# ── pause / unpause: the env file, checked before it is read ──
[ -f "$ENV_FILE" ] && [ ! -L "$ENV_FILE" ] || { echo "demo-offline: the env file is missing or not a regular file"; exit 2; }
[ "$(stat -c %u "$ENV_FILE")" = "$(id -u)" ] || { echo "demo-offline: the env file is not owned by this user"; exit 2; }
[ $(( 8#$(stat -c %a "$ENV_FILE") & 077 )) = 0 ] || { echo "demo-offline: the env file is readable by others (chmod 600)"; exit 2; }
VERCEL_TOKEN=; VERCEL_PROJECT_ID=; VERCEL_TEAM_ID=
. "$ENV_FILE"
export -n VERCEL_TOKEN VERCEL_PROJECT_ID VERCEL_TEAM_ID   # even if the file says `export`: no child process sees them
[ -n "$VERCEL_TOKEN" ] && [ -n "$VERCEL_PROJECT_ID" ] || { echo "demo-offline: VERCEL_TOKEN and VERCEL_PROJECT_ID must both be set"; exit 2; }

HDR=$(mktemp) || exit 2
trap 'rm -f "$HDR"' EXIT
chmod 600 "$HDR"
printf 'Authorization: Bearer %s\n' "$VERCEL_TOKEN" > "$HDR"
unset VERCEL_TOKEN
Q=; [ -n "$VERCEL_TEAM_ID" ] && Q="?teamId=$VERCEL_TEAM_ID"
status=$(curl -4 -s -o /dev/null -m 30 -w '%{http_code}' -X POST -H @"$HDR" -H 'Content-Type: application/json' \
         "$API/v1/projects/$VERCEL_PROJECT_ID/$ACTION$Q" 2>/dev/null || true)
echo "vercel $ACTION: HTTP ${status:-000}"
[ "$status" = 200 ] || { echo "demo-offline: the API did not accept the $ACTION — nothing changed on our side"; exit 1; }

deadline=$(( $(date +%s) + POLL_S ))
while :; do
  code=$(measure_state "$URL")
  if [ "$ACTION" = pause ] && [ "$code" = paused ]; then echo "demo: offline (503 DEPLOYMENT_PAUSED) — measured"; exit 0; fi
  if [ "$ACTION" = unpause ] && [ "$code" = 200 ]; then echo "demo: online (200) — measured"; exit 0; fi
  [ "$(date +%s)" -ge "$deadline" ] && break
  sleep 3
done
echo "demo: still ${code:-000} after ${POLL_S}s — the $ACTION was accepted but its effect was NOT measured"
exit 1
