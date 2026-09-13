#!/usr/bin/env bash
# run-d11 — the eight cases that decide whether the D11 owner write path is real.
#
# WHAT MAKES A CASE EVIDENCE, and the reason it is stated before any code: a case counts only when the
# CONTROL and the TREATMENT differ. In CP 6d-0 a token-bearing request and an unauthenticated one both
# returned 404 while the Access application was inert, and that was briefly written down as a pass. Two
# rows with the same result are a broken instrument, not a proof. Every case below therefore prints both
# sides, and the discriminating pair is checked, not just the expected code.
#
# AND STATUS CODES ARE HALF THE TEST. Cases 4 and 5 must also show that Airtable did NOT change; a refusal
# that still wrote is the failure this whole path exists to prevent.
#
# Usage:
#   set -a; . ~/.n8n-api.env; set +a
#   OWNER_ACTION_URL="https://<n8n-host>/webhook/owner-release" \
#   STATE_URL="https://<n8n-host>/webhook/<a read endpoint>"   # OR the two AIRTABLE_* vars below
#   OWNER_HMAC_SECRET="…" AIRTABLE_PAT_READONLY="…" AIRTABLE_BASE_ID="app…" \
#   TARGET_RECORD="rec…" bash tests/run-d11.sh
#
# Nothing here prints a secret, a host, a full record id or any conversation content.
set -u -o pipefail

URL="${OWNER_ACTION_URL:?set OWNER_ACTION_URL}"
SEC="${OWNER_HMAC_SECRET:?set OWNER_HMAC_SECRET}"
CID="${CF_OWNER_ACCESS_CLIENT_ID:?set CF_OWNER_ACCESS_CLIENT_ID (from ~/.n8n-api.env)}"
CSE="${CF_OWNER_ACCESS_CLIENT_SECRET:?set CF_OWNER_ACCESS_CLIENT_SECRET}"
TGT="${TARGET_RECORD:?set TARGET_RECORD — the Airtable record id of a conversation in stage=handoff}"
PAT="${AIRTABLE_PAT_READONLY:-}"; BASE="${AIRTABLE_BASE_ID:-}"
# ⚠ STATE_URL is not a standing endpoint: the 2026-09-13 7/7 run used a TEMPORARY n8n workflow that
# returned "stage|last_intent" for a posted record_id, created for the drill and deleted after it. Recreate
# it (or supply AIRTABLE_PAT_READONLY + AIRTABLE_BASE_ID) before re-running, or cases 4/5/6 have no way to
# read the DATA — and this file's whole premise is that a status code is only half the test.

RUN="$(date +%s)"
PASS=0; FAIL=0

say()  { printf '%-58s %s\n' "$1" "$2"; }
ok()   { PASS=$((PASS+1)); say "$1" "✓ $2"; }
bad()  { FAIL=$((FAIL+1)); say "$1" "✗ $2"; }

sign() { printf '%s' "$1" | openssl dgst -sha256 -hmac "$SEC" -r | cut -d' ' -f1; }

# post <body> <signature> [--no-token]
post() {
  local body="$1" sig="$2" notok="${3:-}"
  if [ "$notok" = "--no-token" ]; then
    curl -s -4 -o /dev/null -m 25 -w '%{http_code}' -X POST "$URL" \
      -H 'Content-Type: application/json' -H "X-Owner-Signature: $sig" --data "$body"
  else
    curl -s -4 -o /dev/null -m 25 -w '%{http_code}' -X POST "$URL" \
      -H 'Content-Type: application/json' -H "X-Owner-Signature: $sig" \
      -H "CF-Access-Client-Id: $CID" -H "CF-Access-Client-Secret: $CSE" --data "$body"
  fi
}

body_for() { # body_for <action> <sender> <messageId> <ts>
  printf '{"action":"%s","record_id":"%s","messageId":"%s","ts":%s}' "$1" "$2" "$3" "$4"
}

# Reading the STATE is half the test: cases 4/5/6 must show what the DATA did, not what a status code
# said. Two routes, because the credential you have depends on where you are standing:
#   · AIRTABLE_PAT_READONLY + AIRTABLE_BASE_ID — a standalone read token.
#   · STATE_URL — an endpoint that returns "stage|last_intent" for a posted record_id. A machine that
#     holds the ENGINE's credentials but no separate PAT has this route and not the first one; that was
#     exactly the situation on 2026-09-13, and without it cases 4/5/6 degrade to comparing "NO-AIRTABLE"
#     with "NO-AIRTABLE" — two equal readings from an instrument that measured nothing, which this file's
#     own header calls a broken instrument rather than a pass.
# With NEITHER configured it still returns NO-AIRTABLE and case 6 still FAILS loudly. That is deliberate:
# the fallback adds a route, it does not add a way to pass without evidence.
state_of() { # state_of [messageId]  -> "stage|last_intent|markerCount"
  local mid="${1:-zz-no-such-message-id}"
  if [ -n "${STATE_URL:-}" ]; then
    local body sig
    body="$(printf '{"action":"read_drill_state","record_id":"%s","messageId":"%s"}' "$TGT" "$mid")"
    sig="$(printf '%s' "$body" | openssl dgst -sha256 -hmac "$SEC" -r | cut -d' ' -f1)"
    curl -s -4 -m 25 -X POST "$STATE_URL" -H 'Content-Type: application/json' \
      -H "X-Owner-Signature: $sig" \
      ${CF_OWNER_ACCESS_CLIENT_ID:+-H "CF-Access-Client-Id: $CF_OWNER_ACCESS_CLIENT_ID"} \
      ${CF_OWNER_ACCESS_CLIENT_SECRET:+-H "CF-Access-Client-Secret: $CF_OWNER_ACCESS_CLIENT_SECRET"} \
      --data "$body"
    return
  fi
  [ -n "$PAT" ] && [ -n "$BASE" ] || { echo "NO-AIRTABLE"; return; }
  curl -s -4 -m 25 -G "https://api.airtable.com/v0/$BASE/conversations/$TGT" \
    -H "Authorization: Bearer $PAT" \
  | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('READ-FAILED'); sys.exit()
if 'fields' not in d: print('NOT-FOUND'); sys.exit()
f=d['fields']
print('%s|%s|?' % (f.get('stage',''), f.get('last_intent','')))"
}

# A REFUSAL THAT STILL WROTE is the failure this endpoint exists to prevent, and checking only the status
# code cannot see it: "write, then return 403" passes a status-only assertion. Every rejected request is
# therefore followed by this.
assert_unchanged() { # assert_unchanged <case label> <expected state>
  local now; now="$(state_of)"
  if [ "$now" = "$2" ]; then
    ok "  ↳ $1" "target row UNCHANGED after the refusal"
  else
    bad "  ↳ $1" "the refusal still MOVED the row: '$2' -> '$now'"
  fi
}

echo "run-d11 — eight cases, tag $RUN"
echo "target record: ${TGT:0:3}…  (masked — security-secrets.md redacts record ids to a bare rec…)"
BEFORE="$(state_of)"; echo "airtable before: $BEFORE"
echo

NOW=$(date +%s)
B_OK="$(body_for release_handoff "$TGT" "d11-$RUN" "$NOW")"
S_OK="$(sign "$B_OK")"

# 1 — no service token. CONTROL for every later case.
c1="$(post "$B_OK" "$S_OK" --no-token)"
[ "$c1" = "403" ] && ok "1 no service token" "403 (Access refused)" \
                  || bad "1 no service token" "got $c1, expected 403"
assert_unchanged "1 no service token" "$BEFORE"

# 2 — token present, signature wrong.
c2="$(post "$B_OK" "$(sign "${B_OK}tampered")")"
[ "$c2" = "403" ] && ok "2 token OK, HMAC wrong" "403" \
                  || bad "2 token OK, HMAC wrong" "got $c2, expected 403"
assert_unchanged "2 token OK, HMAC wrong" "$BEFORE"

# 3 — signed correctly, action outside the allow-list.
B3="$(body_for delete_everything "$TGT" "d11-$RUN-3" "$NOW")"
c3="$(post "$B3" "$(sign "$B3")")"
[ "$c3" = "400" ] && ok "3 action off the allow-list" "400" \
                  || bad "3 action off the allow-list" "got $c3, expected 400"
assert_unchanged "3 action off the allow-list" "$BEFORE"

# 7 — stale ts (run before the real release so it cannot be masked by an already-released target).
B7="$(body_for release_handoff "$TGT" "d11-$RUN-7" "$((NOW-3600))")"
c7="$(post "$B7" "$(sign "$B7")")"
[ "$c7" = "401" ] && ok "7 ts older than the window" "401" \
                  || bad "7 ts older than the window" "got $c7, expected 401"
assert_unchanged "7 ts older than the window" "$BEFORE"

# 4 — a target that is not in handoff (or does not exist) — AND Airtable must not change.
# ⚠ The fixture used to be `recZZnonexistent99`, which is 18 characters. Once `Validate Owner Action`
# tightened its pattern to the REAL Airtable shape (`rec` + exactly 14) that id stopped being a
# nonexistent-record test and became a malformed-input test: it returns 400 at the allow-list and never
# reaches the lookup. Two different refusals were wearing one case. They are separate now — 4 proves the
# 404 path with a WELL-FORMED id that does not exist, 4b proves the 400 path on purpose.
S4="recZZZZZZZZZZZZZZ"
B4="$(body_for release_handoff "$S4" "d11-$RUN-4" "$NOW")"
c4="$(post "$B4" "$(sign "$B4")")"
A4="$(state_of)"    # same shape as BEFORE, so the comparison below is a real one
if { [ "$c4" = "404" ] || [ "$c4" = "409" ]; } && [ "$A4" = "$BEFORE" ]; then
  ok "4 wrong target (well-formed, nonexistent)" "$c4 and the target row is UNCHANGED"
else
  bad "4 wrong target (well-formed, nonexistent)" "got $c4, state ${BEFORE} -> ${A4}"
fi

# 4b — a MALFORMED record id must be refused by the allow-list, before any lookup, and write nothing.
B4b="$(body_for release_handoff "recNOPE" "d11-$RUN-4b" "$NOW")"
c4b="$(post "$B4b" "$(sign "$B4b")")"
[ "$c4b" = "400" ] && ok "4b malformed record id" "400 at the allow-list, before the lookup" \
                   || bad "4b malformed record id" "got $c4b, expected 400"
assert_unchanged "4b malformed record id" "$BEFORE"

# 5 + 6 — the real release, then the replay.
# ⚠ THE COUNTER, NOT THE STATE. An earlier version compared AFTER2 with AFTER1 and called that a replay
# proof. It is not: `stage='new'` written twice leaves the row IDENTICAL, so two writes and one write are
# indistinguishable by state — the assertion could not go red for the defect it existed to catch (Codex
# CRT #11, 2026-09-13). One complete pass writes exactly ONE dedupe marker, so the MARKER COUNT is what
# actually discriminates. State equality is kept as a second, weaker check, not as the proof.
c5a="$(post "$B_OK" "$S_OK")"
AFTER1="$(state_of "d11-$RUN")"
c5b="$(post "$B_OK" "$S_OK")"
AFTER2="$(state_of "d11-$RUN")"
M1="${AFTER1##*|}"; M2="${AFTER2##*|}"

# 6 — write-then-verify, from the DATA not the status code.
if [ "$AFTER1" = "NO-AIRTABLE" ]; then
  bad "6 released state" "Airtable not configured — cannot verify the DATA, only the code ($c5a)"
elif [ "${AFTER1%|*}" = "new|" ]; then
  ok "6 released state" "stage='new' AND last_intent empty"
else
  bad "6 released state" "expected 'new|…', got '$AFTER1'"
fi

# 5 — the replay must not write a second time. The discriminator is the WRITE COUNT.
if [ "$AFTER1" = "NO-AIRTABLE" ]; then
  bad "5 replay (same messageId)" "no state route — cannot count writes, only statuses ($c5a/$c5b)"
elif [ "$M1" = "?" ] || [ "$M2" = "?" ]; then
  bad "5 replay (same messageId)" "the state route returned no marker count; the PAT route cannot count writes"
elif [ "$M1" = "1" ] && [ "$M2" = "1" ]; then
  ok "5 replay (same messageId)" "codes $c5a/$c5b · dedupe markers 1 -> 1, so the second call wrote NOTHING"
else
  bad "5 replay (same messageId)" "marker count moved $M1 -> $M2 (expected 1 -> 1): the replay wrote again"
fi

echo
echo "DISCRIMINATION CHECK — the reason this file exists:"
echo "  case 1 (no token) = $c1   ·   case 5a (full valid request) = $c5a"
if [ "$c1" != "$c5a" ]; then
  echo "  ✓ control and treatment DIFFER — the service token is doing something"
else
  echo "  ✗ control and treatment are IDENTICAL — this run proves nothing, whatever the counts say"
  FAIL=$((FAIL+1))
fi
echo
echo "run-d11: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
