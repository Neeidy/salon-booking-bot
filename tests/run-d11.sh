#!/usr/bin/env bash
# run-d11 — the seven cases that decide whether the D11 owner write path is real.
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

# Airtable read helper — returns "stage|last_intent" for TGT, or "NO-AIRTABLE" when unconfigured.
state_of() {
  [ -n "$PAT" ] && [ -n "$BASE" ] || { echo "NO-AIRTABLE"; return; }
  curl -s -4 -m 25 -G "https://api.airtable.com/v0/$BASE/conversations/$TGT" \
    -H "Authorization: Bearer $PAT" \
  | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('READ-FAILED'); sys.exit()
if 'fields' not in d: print('NOT-FOUND'); sys.exit()
f=d['fields']
print('%s|%s' % (f.get('stage',''), f.get('last_intent','')))"
}

echo "run-d11 — seven cases, tag $RUN"
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

# 2 — token present, signature wrong.
c2="$(post "$B_OK" "$(sign "${B_OK}tampered")")"
[ "$c2" = "403" ] && ok "2 token OK, HMAC wrong" "403" \
                  || bad "2 token OK, HMAC wrong" "got $c2, expected 403"

# 3 — signed correctly, action outside the allow-list.
B3="$(body_for delete_everything "$TGT" "d11-$RUN-3" "$NOW")"
c3="$(post "$B3" "$(sign "$B3")")"
[ "$c3" = "400" ] && ok "3 action off the allow-list" "400" \
                  || bad "3 action off the allow-list" "got $c3, expected 400"

# 7 — stale ts (run before the real release so it cannot be masked by an already-released target).
B7="$(body_for release_handoff "$TGT" "d11-$RUN-7" "$((NOW-3600))")"
c7="$(post "$B7" "$(sign "$B7")")"
[ "$c7" = "401" ] && ok "7 ts older than the window" "401" \
                  || bad "7 ts older than the window" "got $c7, expected 401"

# 4 — a target that is not in handoff (or does not exist) — AND Airtable must not change.
S4="recZZnonexistent99"
B4="$(body_for release_handoff "$S4" "d11-$RUN-4" "$NOW")"
c4="$(post "$B4" "$(sign "$B4")")"
A4="$(state_of)"
if { [ "$c4" = "404" ] || [ "$c4" = "409" ]; } && [ "$A4" = "$BEFORE" ]; then
  ok "4 wrong target" "$c4 and the target row is UNCHANGED"
else
  bad "4 wrong target" "got $c4, state ${BEFORE} -> ${A4}"
fi

# 5 + 6 — the real release, then the replay.
c5a="$(post "$B_OK" "$S_OK")"
AFTER1="$(state_of)"
c5b="$(post "$B_OK" "$S_OK")"
AFTER2="$(state_of)"

# 6 — write-then-verify, from the DATA not the status code.
if [ "$AFTER1" = "NO-AIRTABLE" ]; then
  bad "6 released state" "Airtable not configured — cannot verify the DATA, only the code ($c5a)"
elif [ "$AFTER1" = "new|" ]; then
  ok "6 released state" "stage='new' AND last_intent empty"
else
  bad "6 released state" "expected 'new|', got '$AFTER1'"
fi

# 5 — the replay must not write a second time. The discriminator is the STATE, not the status.
if [ "$AFTER2" = "$AFTER1" ]; then
  ok "5 replay (same messageId)" "codes $c5a/$c5b, state unchanged by the second call"
else
  bad "5 replay (same messageId)" "state moved on the replay: '$AFTER1' -> '$AFTER2'"
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
