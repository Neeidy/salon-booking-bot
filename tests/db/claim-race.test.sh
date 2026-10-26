#!/usr/bin/env bash
# claim-race.test.sh — Phase 7-2 Tur 2: the two claims a unit test cannot make, measured on a real Postgres.
#   F1 (Main, R-1a): `Check Processed`'s claim. Two sessions insert the SAME message id at once: exactly one gets the
#      row; the second WAITS for the first to commit and then gets none (it does not also read "absent").
#   O1 (Owner Actions): `Release Handoff Lock`'s one statement. A release, then a NEWER handoff written by Main, then a
#      delayed duplicate (same message id) and a stale request (other message id, old last_updated): neither writes;
#      each gets the sentinel row (`replay` / `state_changed`). Two different ids racing on one handoff: one release.
# The SQL is read from the STAGED exports and run verbatim (PREPARE … AS <query>), as `salon_app` (the n8n role,
# DML only), never as the superuser, on 001+002+003 applied to an empty database.
# Each scenario has a mutant that must go RED: the pre-Tur-2 read-then-insert (F1) and the release without the
# version token (O1). Not in check-all: it needs Docker. Run: bash tests/db/claim-race.test.sh [IMAGE]
#
# The container is throwaway: labelled, no network, local-socket `trust` auth, removed on exit. The role passwords
# 002 requires are generated at run time and passed by name (see below); nothing connects over a network.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${1:-${CLAIM_RACE_IMAGE:-}}"
if [ -z "$IMAGE" ]; then
  IMAGE="$(docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | awk '$1 ~ /^postgres:/ {print $2; exit}')"
fi
[ -n "$IMAGE" ] || { echo "claim-race: no local postgres image (pass one as \$1)"; exit 2; }

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "✓ $1"; }
bad() { FAIL=$((FAIL+1)); echo "✗ $1"; }

CID="$(docker run -d --rm --label c72=pgtest --network none -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=salon \
  -v "$ROOT/db/schema:/schema:ro" "$IMAGE")"
trap 'docker rm -f "$CID" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 60); do docker exec "$CID" pg_isready -U postgres -d salon >/dev/null 2>&1 && break; sleep 0.5; done
sleep 1   # the image restarts the server once after its init scripts
for _ in $(seq 1 60); do docker exec "$CID" pg_isready -U postgres -d salon >/dev/null 2>&1 && break; sleep 0.5; done

# The three role passwords 002 requires (24+ characters, all different) are generated HERE, at run time, never printed,
# and handed to the container by NAME only (`-e NAME`, no value on any command line), as 002's own runbook does.
read -r SALON_MIGRATOR_PASSWORD SALON_APP_PASSWORD SALON_RO_PASSWORD < <(python3 -c 'import secrets; print(*(secrets.token_hex(16) for _ in range(3)))')
export SALON_MIGRATOR_PASSWORD SALON_APP_PASSWORD SALON_RO_PASSWORD
docker exec -i -e SALON_MIGRATOR_PASSWORD -e SALON_APP_PASSWORD -e SALON_RO_PASSWORD "$CID" \
  sh -c 'cat /schema/001_init.sql /schema/002_roles.sql /schema/003_revoke_large_object_writes.sql | psql -q -v ON_ERROR_STOP=1 -U postgres -d salon' >/dev/null

app() { docker exec -i "$CID" psql -X -q -t -A -v ON_ERROR_STOP=1 -U salon_app -d salon "$@"; }
su()  { docker exec -i "$CID" psql -X -q -t -A -v ON_ERROR_STOP=1 -U postgres -d salon "$@"; }

q() { python3 - "$1" "$2" <<'EOF'
import json, sys
w = json.load(open(sys.argv[1], encoding='utf-8'))
print(next(n for n in w['nodes'] if n['name'] == sys.argv[2])['parameters']['query'])
EOF
}
CLAIM_Q="$(q "$ROOT/n8n/staged/workflow.main.copy.sanitized.json" 'Check Processed')"
REL_Q="$(q "$ROOT/n8n/staged/workflow.owner-actions.copy.sanitized.json" 'Release Handoff Lock')"
OLD_CHECK_Q="SELECT id FROM salon.processed_messages WHERE message_id = \$1"            # the pre-Tur-2 read
REL_NO_TOKEN_Q="${REL_Q//AND salon.at_ts(last_updated) = \$2 /}"                         # the O1 mutant
[ "$REL_NO_TOKEN_Q" != "$REL_Q" ] || { echo "claim-race: the O1 mutant did not apply (query text changed?)"; exit 2; }

# ── F1: two sessions claim the same id ───────────────────────────────────────────────────────────────────────
f1() { # f1 <message id> → "<A rows> <B rows> <B waited seconds>"
  local mid="$1" a b t0 t1
  a="$( { printf "PREPARE c(text,text,text) AS %s;\nBEGIN;\nEXECUTE c('%s','widget:w-claim-race','widget');\nSELECT pg_sleep(2);\nCOMMIT;\n" "$CLAIM_Q" "$mid"; } | app | grep -c '^rec' || true)" &
  local apid=$!
  sleep 0.5
  t0="$(date +%s.%N)"
  b="$(printf "PREPARE c(text,text,text) AS %s;\nEXECUTE c('%s','widget:w-claim-race','widget');\n" "$CLAIM_Q" "$mid" | app | grep -c '^rec' || true)"
  t1="$(date +%s.%N)"
  wait "$apid"
  a="$(su -c "SELECT count(*) FROM salon.processed_messages WHERE message_id = '$mid'")"
  echo "$a $b $(python3 -c "print(round($t1-$t0,1))")"
}
read -r rows b waited <<<"$(f1 cr-f1-a)"
[ "$rows" = 1 ] && [ "$b" = 0 ] && python3 -c "import sys; sys.exit(0 if $waited >= 1.0 else 1)" \
  && ok "F1: concurrent claims of one id → one row; the second session WAITED ${waited}s and got none" \
  || bad "F1: concurrent claims → markers $rows, second got $b row(s), waited ${waited}s (want 1, 0, ≥1.0)"
b2="$(printf "PREPARE c(text,text,text) AS %s;\nEXECUTE c('cr-f1-a','widget:w-claim-race','widget');\n" "$CLAIM_Q" | app | grep -c '^rec' || true)"
[ "$b2" = 0 ] && ok "F1: a sequential redelivery of the claimed id gets no row (duplicate)" || bad "F1: sequential redelivery got $b2 row(s)"
# Mutant: the pre-Tur-2 read-then-record. Both concurrent runs read "absent" before either records.
ma="$( { printf "PREPARE r(text) AS %s;\nBEGIN;\nEXECUTE r('cr-f1-m');\nSELECT pg_sleep(2);\nCOMMIT;\n" "$OLD_CHECK_Q"; } | app | grep -c '^rec' || true)" &
mp=$!
sleep 0.5
mb="$(printf "PREPARE r(text) AS %s;\nEXECUTE r('cr-f1-m');\n" "$OLD_CHECK_Q" | app | grep -c '^rec' || true)"
wait "$mp"
[ "$mb" = 0 ] && ok "F1 mutant (read-then-record): the second run ALSO reads absent → would process again (RED as expected)" \
  || bad "F1 mutant did not reproduce the race (second read found $mb)"

# ── O1: the delayed duplicate and the stale request ──────────────────────────────────────────────────────────
su -c "INSERT INTO salon.conversations (id, sender_key, stage, last_intent, last_updated) VALUES
       ('recCRTEST00000001','widget:w-claim-race','handoff','handoff','2030-01-01T10:00:00.000Z'),
       ('recCRTEST00000002','widget:w-claim-race2','handoff','handoff','2030-01-01T10:00:00.000Z')" >/dev/null
rel() { # rel <query> <record> <token> <message id> → "<id or NULL>|<fields>"
  printf "PREPARE x(text,text,text) AS %s;\nEXECUTE x('%s','%s','%s');\n" "$1" "$2" "$3" "$4" | app -F '|' \
    | python3 -c "import sys; l=[x for x in sys.stdin.read().splitlines() if x]; print(l[-1] if l else 'NO-ROW')" | cut -d'|' -f1,3
}
TOK='2030-01-01T10:00:00.000Z'
r1="$(rel "$REL_Q" recCRTEST00000001 "$TOK" cr-o1-A)"
[[ "$r1" == recCRTEST00000001\|* ]] && ok "O1: the first signed release writes and returns the row" || bad "O1: first release returned '$r1'"
su -c "UPDATE salon.conversations SET stage='handoff', last_intent='handoff', last_updated='2030-01-01T11:00:00.000Z' WHERE id='recCRTEST00000001'" >/dev/null
r2="$(rel "$REL_Q" recCRTEST00000001 "$TOK" cr-o1-A)"
r3="$(rel "$REL_Q" recCRTEST00000001 "$TOK" cr-o1-B)"
st="$(su -c "SELECT stage FROM salon.conversations WHERE id='recCRTEST00000001'")"
[[ "$r2" == *'"conflict": "replay"'* ]] && ok "O1: the delayed duplicate (same id) gets the sentinel 'replay'" || bad "O1: delayed duplicate returned '$r2'"
[[ "$r3" == *'"conflict": "state_changed"'* ]] && ok "O1: a stale request (old last_updated) gets the sentinel 'state_changed'" || bad "O1: stale request returned '$r3'"
[ "$st" = handoff ] && ok "O1: the NEWER handoff is still locked after both" || bad "O1: the newer handoff became '$st'"
[[ "${r2%%|*}" == "" ]] && [[ "${r3%%|*}" == "" ]] && ok "O1: the sentinel carries no id (Release Wrote? reads !!\$json.id)" || bad "O1: a sentinel carried an id ('$r2' / '$r3')"
# Mutant: no version token → the stale request releases the newer handoff.
m3="$(rel "$REL_NO_TOKEN_Q" recCRTEST00000001 "$TOK" cr-o1-C)"
[[ "$m3" == recCRTEST00000001\|* ]] && ok "O1 mutant (no last_updated condition): the stale request RELEASES the newer handoff (RED as expected)" \
  || bad "O1 mutant did not reproduce the defect ('$m3')"
# Two different ids racing on one handoff: one release, one 'state_changed'.
( { printf "PREPARE x(text,text,text) AS %s;\nBEGIN;\nEXECUTE x('recCRTEST00000002','%s','cr-o1-R1');\nSELECT pg_sleep(2);\nCOMMIT;\n" "$REL_Q" "$TOK"; } | app >/dev/null ) &
rp=$!
sleep 0.5
rB="$(rel "$REL_Q" recCRTEST00000002 "$TOK" cr-o1-R2)"
wait "$rp"
st2="$(su -c "SELECT stage FROM salon.conversations WHERE id='recCRTEST00000002'")"
[[ "$rB" == *'"conflict": "state_changed"'* ]] && [ "$st2" = new ] && ok "O1: two ids racing on one handoff → one release; the waiter re-checks and gets 'state_changed'" \
  || bad "O1: racing pair → second '$rB', row '$st2'"

echo "claim-race: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
