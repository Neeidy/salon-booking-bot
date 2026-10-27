#!/usr/bin/env bash
# run-d11 — the eight cases that decide whether the D11 owner write path is real.
#
# WHAT MAKES A CASE EVIDENCE, and the reason it is stated before any code: a case counts only when the
# CONTROL and the TREATMENT differ. In CP 6d-0 a token-bearing request and an unauthenticated one both
# returned 404 while the Access application was inert, and that was briefly written down as a pass. Two
# rows with the same result are a broken instrument, not a proof. Every case below therefore prints both
# sides, and the discriminating pair is checked, not just the expected code.
#
# AND STATUS CODES ARE HALF THE TEST. Cases 4 and 5 must also show that the store did NOT change; a refusal
# that still wrote is the failure this whole path exists to prevent.
#
# Usage:
#   set -a; . ~/.n8n-api.env; set +a
#   OWNER_ACTION_URL="https://<n8n-host>/webhook/owner-release" \
#   STATE_URL="https://<n8n-host>/webhook/<a read endpoint>"   # OR the read-only database env below
#   set -a; . <the salon_ro env file>; set +a                  # PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
#   OWNER_HMAC_SECRET="…" TARGET_RECORD="rec…" bash tests/run-d11.sh
#
# Nothing here prints a secret, a host, a full record id or any conversation content.
set -u -o pipefail

# A STATE ORACLE THAT COULD NOT LOOK IS NOT A READING (Q11, 2026-10-19). The drill-state endpoint now
# answers "STORE-ERROR|…" when a store read failed; it used to answer "NOT-FOUND|0", and two identical error
# readings made every "unchanged" check below pass for the wrong reason.
# The classifier is an ALLOW-LIST: only the known reading shapes count as a state ("stage|last_intent|count",
# "NOT-FOUND[|count]", "NO-STORE"). Everything else is a HARD failure: STORE-ERROR…, READ-FAILED, an empty
# body (curl failed), and anything unexpected (a REFUSED, an HTML error page, a 404 body), which a
# deny-list would have let through as a "reading" (pre-push audit, 2026-10-19).
# `--selftest-state` exercises it with no network and no credentials.
STATE_RE='^([a-z_]*\|[a-z_]*\|([0-9]+|\?)|NOT-FOUND(\|[0-9]+)?|NO-STORE)$'
# [[ =~ ]] anchors ^/$ to the WHOLE string; `grep` would have matched any ONE line of a multi-line body.
is_state_error() { [[ $1 =~ $STATE_RE ]] && return 1; return 0; }
unchanged_verdict() { # unchanged_verdict <before> <now> → ok | moved | error | unmeasured   (pure: the selftest checks it)
  if is_state_error "$2"; then echo error; return; fi
  # Two NO-STORE readings are EQUAL and prove nothing: no state route was configured, so nothing was read.
  if [ "$2" = "NO-STORE" ] || [ "$1" = "NO-STORE" ]; then echo unmeasured; return; fi
  if [ "$2" = "$1" ]; then echo ok; else echo moved; fi
}
# The direct-read route's parser, shared by state_of and the selftest so the selftest checks THIS code.
# Since D5 (MIGRATION-PLAN §3t) the direct route reads Postgres as salon_ro, not Airtable with a PAT. Its reader
# prints one JSON object: {"error": <code>} on any failure, else {"row": null|{stage, last_intent}, "markers": n}.
# Unlike the PAT route it can COUNT the replay markers, so case 5 no longer depends on STATE_URL.
DIRECT_PARSE='
import json,sys
try: d=json.load(sys.stdin)
except Exception: print("READ-FAILED"); sys.exit()
if not isinstance(d,dict) or "error" in d or not isinstance(d.get("markers"),int): print("READ-FAILED"); sys.exit()   # a store ERROR is not an empty read (Q11)
r=d.get("row")
if r is None: print("NOT-FOUND|%d" % d["markers"]); sys.exit()
print("%s|%s|%d" % (r.get("stage") or "", r.get("last_intent") or "", d["markers"]))'
# The reader itself: two constant, parameterised reads, nothing printed but the JSON above.
DIRECT_JS='
const {Client}=require(process.env.RUN_D11_PG);
(async()=>{const c=new Client();try{await c.connect();
const r=await c.query("SELECT stage, last_intent FROM salon.conversations WHERE id = $1",[process.env.RUN_D11_TGT]);
const m=await c.query("SELECT count(*)::int AS n FROM salon.processed_messages WHERE message_id = $1",[process.env.RUN_D11_MID]);
console.log(JSON.stringify({row:r.rows[0]||null,markers:m.rows[0].n}));}
catch(e){console.log(JSON.stringify({error:String(e.code||"unknown")}));}finally{await c.end().catch(()=>{});}})();'
# RELEASES ARE COUNTED WHERE THEY HAPPEN (7-2 Tur 2): the Owner Actions workflow's executions since the run started, in which
# `Release Handoff Lock` returned a REAL row (its sentinel carries no id). The parser lives here, once, so the selftest
# checks the same code the live run uses. Prints "COUNT n" or "ERROR <reason>"; never a body, never an id.
# FAIL-CLOSED on incomplete evidence (R2b D11; Codex R2, target 11): an execution inside the window whose run data is
# missing or empty counted ZERO, and a page with more results pending was read as complete — either way one release
# could certify "exactly one". Now: such an execution, or a further page while this page's oldest run is still inside
# the window, is ERROR. ASSUMES the API lists executions newest first (not measured here): a page that already reaches
# back past the window start leaves nothing in-window on the next one.
RELEASES_PY='
import json,sys,datetime
since=sys.argv[1]
def iso(x):
    try: datetime.datetime.fromisoformat(x); return True
    except (TypeError, ValueError): return False
try: d=json.load(sys.stdin)
except Exception: print("ERROR unreadable"); sys.exit()
if not isinstance(d,dict) or not isinstance(d.get("data"),list): print("ERROR no-executions-list"); sys.exit()
starts=[str(e.get("startedAt") or "")[:19] for e in d["data"] if isinstance(e,dict)]
if len(starts)!=len(d["data"]) or any(len(x)!=19 or x[10]!="T" or not iso(x) for x in starts): print("ERROR malformed-execution"); sys.exit()
if d.get("nextCursor") and (not starts or min(starts) >= since): print("ERROR more-pages"); sys.exit()
n=0
for e in d["data"]:
    if str(e.get("startedAt") or "")[:19] < since: continue
    run=((e.get("data") or {}).get("resultData") or {}).get("runData")
    if not isinstance(run,dict) or not run: print("ERROR missing-execution-data"); sys.exit()
    for r in run.get("Release Handoff Lock") or []:
        items=(((r.get("data") or {}).get("main") or [[]])[0]) or []
        if any(isinstance(i,dict) and (i.get("json") or {}).get("id") for i in items): n+=1
print("COUNT %d" % n)'
release_count() { # release_count <ISO start, UTC, no zone> → "COUNT n" | "ERROR …"
  local wid hdr host
  [ -n "${N8N_API_KEY:-}" ] || { echo "ERROR N8N_API_KEY not set"; return; }
  host="${N8N_HOST:-$(sed -n 's/^N8N_HOST=[[:space:]]*\([^[:space:]]*\).*/\1/p' "$(dirname "$0")/../CLAUDE.local.md" 2>/dev/null)}"
  [ -n "$host" ] || { echo "ERROR no n8n host"; return; }
  wid="$(cd "$(dirname "$0")/.." && python3 -c 'import importlib.util as u; s=u.spec_from_file_location("w","scripts/workflows.py"); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.id_for(m.load(), "owner-actions"))' 2>/dev/null)"
  [ -n "$wid" ] || { echo "ERROR no Owner Actions workflow in WORKFLOWS"; return; }
  hdr="$(mktemp)"; chmod 600 "$hdr"
  printf 'X-N8N-API-KEY: %s\nCF-Access-Client-Id: %s\nCF-Access-Client-Secret: %s\n' "$N8N_API_KEY" "${CF_ACCESS_CLIENT_ID:-}" "${CF_ACCESS_CLIENT_SECRET:-}" > "$hdr"
  curl -s -4 -m 30 -H "@$hdr" "https://$host/api/v1/executions?workflowId=$wid&includeData=true&limit=50" | python3 -c "$RELEASES_PY" "$1"
  rm -f "$hdr"
}
# A 200 IS NOT A CLEAN PASS WHEN ITS BODY SAYS "degraded" (ruling, 2026-10-20). At D3b a copy answered every
# successful release with {"ok":true,"degraded":"alert_undelivered"}, and this file stayed 13/13 because it read
# codes, state and the marker count but never a body. The classifier lives here, once, so the selftest below
# checks the same code the live run uses.
DEGRADED_PY='
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(1)
sys.exit(0 if isinstance(d,dict) and "degraded" in d else 1)'
is_degraded() { python3 -c "$DEGRADED_PY" < "$1"; }   # is_degraded <body file> -> 0 when the body declares itself degraded
clean_200() { [ "$1" = "200" ] && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get("ok") is True and "degraded" not in d else 1)' "$2" 2>/dev/null; }
# THE DUPLICATE PAIR'S STATUSES (R2b D11; Codex R2, target 11 LOW): one request is a clean 200; the other answers 200
# (it read the marker: replayed), 502 (the statement's sentinel) or 409 — launched together, the second lookup can
# legitimately see the row the first already released, and `Target Locked?` refuses it. All three wrote nothing.
dup_other() { [ "$1" = "200" ] || [ "$1" = "502" ] || [ "$1" = "409" ]; }
dup_pair_ok() { # dup_pair_ok <code A> <code B> <body A> <body B>
  { clean_200 "$1" "$3" && dup_other "$2"; } || { clean_200 "$2" "$4" && dup_other "$1"; }
}

if [ "${1:-}" = "--selftest-state" ]; then
  rc=0
  tmpb="$(mktemp)"
  for b in '{"ok":true,"degraded":"alert_undelivered"}' '{"ok":true,"degraded":"anything_else"}'; do
    printf '%s' "$b" > "$tmpb"; is_degraded "$tmpb" || { echo "✗ a degraded body was NOT caught: $b"; rc=1; }; done
  for b in '{"ok":true}' '{"ok":false,"error":"not_locked"}' 'not json'; do
    printf '%s' "$b" > "$tmpb"; is_degraded "$tmpb" && { echo "✗ a clean body WAS flagged degraded: $b"; rc=1; }; done
  rm -f "$tmpb"
  for s in 'STORE-ERROR|read-conversation' 'STORE-ERROR|read-conversation+count-markers' 'READ-FAILED' '' \
           'REFUSED' '<html>error</html>' 'The requested webhook is not registered' \
           $'<html>\nNOT-FOUND|0\n</html>' $'REFUSED\nnew||1'; do
    is_state_error "$s" || { echo "✗ '$s' was NOT treated as a store error"; rc=1; }; done
  for s in 'new||1' 'handoff|handoff|0' 'reschedule_confirming|invalid|12' 'NOT-FOUND|0' 'NOT-FOUND' 'new||?' 'NO-STORE'; do
    is_state_error "$s" && { echo "✗ '$s' WAS treated as a store error"; rc=1; }; done
  for pair in '{"error":"ECONNREFUSED"}=READ-FAILED' '{"error":"42501"}=READ-FAILED' 'not json=READ-FAILED' \
              '{"row":null}=READ-FAILED' '{"row":null,"markers":0}=NOT-FOUND|0' \
              '{"row":{"stage":"new","last_intent":null},"markers":1}=new||1' \
              '{"row":{"stage":"handoff","last_intent":"handoff"},"markers":0}=handoff|handoff|0'; do
    got="$(printf '%s' "${pair%%=*}" | python3 -c "$DIRECT_PARSE")"
    [ "$got" = "${pair#*=}" ] || { echo "✗ direct-read parser turned '${pair%%=*}' into '$got' (want '${pair#*=}')"; rc=1; }
    is_state_error "$got" && [ "${pair#*=}" != "READ-FAILED" ] && { echo "✗ the parser's reading '$got' is not a state"; rc=1; }
  done
  for v in 'handoff|handoff|0 handoff|handoff|0=ok' 'handoff|handoff|0 new||1=moved' 'NO-STORE NO-STORE=unmeasured' \
           'handoff|handoff|0 NO-STORE=unmeasured' 'handoff|handoff|0 READ-FAILED=error'; do
    got="$(unchanged_verdict ${v%%=*})"
    [ "$got" = "${v#*=}" ] || { echo "✗ unchanged_verdict ${v%%=*} → '$got' (want '${v#*=}')"; rc=1; }
  done
  rel() { printf '{"data":[%s]}' "$1"; }
  ex() { printf '{"startedAt":"%s","data":{"resultData":{"runData":{"Release Handoff Lock":[{"data":{"main":[[{"json":%s}]]}}]}}}}' "$1" "$2"; }
  R='{"id":"recAAAAAAAAAAAAAA","fields":{"stage":"new"}}'; SNT='{"id":null,"fields":{"released":false,"conflict":"replay"}}'
  for pair in "$(ex 2030-01-01T10:00:01.000Z "$R"),$(ex 2030-01-01T10:00:01.500Z "$SNT")=COUNT 1" \
              "$(ex 2030-01-01T10:00:01.000Z "$R"),$(ex 2030-01-01T10:00:02.000Z "$R")=COUNT 2" \
              "$(ex 2030-01-01T10:00:01.000Z "$SNT")=COUNT 0" \
              "$(ex 2030-01-01T09:59:00.000Z "$R")=COUNT 0" \
              '{"startedAt":"2030-01-01T10:00:05.000Z","data":{"resultData":{"runData":{"Respond Owner Replayed":[{}]}}}}=COUNT 0'; do
    got="$(rel "${pair%%=*}" | python3 -c "$RELEASES_PY" 2030-01-01T10:00:00)"
    [ "$got" = "${pair#*=}" ] || { echo "✗ release counter: got '$got', want '${pair#*=}'"; rc=1; }
  done
  for bodyx in 'not json' '{"message":"unauthorized"}' \
               "{\"data\":[$(ex 2030-01-01T10:00:01.000Z "$R"),{\"startedAt\":\"2030-01-01T10:00:02.000Z\"}]}" \
               "{\"data\":[$(ex 2030-01-01T10:00:01.000Z "$R"),{\"startedAt\":\"2030-01-01T10:00:02.000Z\",\"data\":{\"resultData\":{\"runData\":{}}}}]}" \
               "{\"data\":[$(ex 2030-01-01T10:00:01.000Z "$R")],\"nextCursor\":\"abc\"}" \
               "{\"data\":[$(ex 2030-01-01T10:00:01.000Z "$R"),{\"startedAt\":null,\"data\":{\"resultData\":{\"runData\":{\"x\":[]}}}}]}" \
               "{\"data\":[$(ex 2030-13-45T99:99:99.000Z "$R")]}"; do
    got="$(printf '%s' "$bodyx" | python3 -c "$RELEASES_PY" 2030-01-01T10:00:00)"
    case "$got" in ERROR*) ;; *) echo "✗ release counter read '${bodyx:0:90}…' as '$got' (incomplete evidence must be ERROR)"; rc=1 ;; esac
  done
  got="$(printf '{"data":[%s,%s],"nextCursor":"abc"}' "$(ex 2030-01-01T10:00:01.000Z "$R")" "$(ex 2030-01-01T09:00:00.000Z "$R")" | python3 -c "$RELEASES_PY" 2030-01-01T10:00:00)"
  [ "$got" = "COUNT 1" ] || { echo "✗ release counter: a further page past the window start was refused ('$got')"; rc=1; }
  pb="$(mktemp)"; pr="$(mktemp)"; pd="$(mktemp)"
  printf '{"ok":true}' > "$pb"; printf '{"ok":true,"replayed":true}' > "$pr"; printf '{"ok":true,"degraded":"x"}' > "$pd"
  for v in "200 409 $pb $pr=ok" "409 200 $pr $pb=ok" "200 502 $pb $pr=ok" "200 200 $pb $pr=ok" \
           "200 500 $pb $pr=bad" "502 409 $pr $pb=bad" "200 409 $pd $pr=bad" "409 409 $pb $pb=bad"; do
    set -- ${v%%=*}
    if dup_pair_ok "$1" "$2" "$3" "$4"; then got=ok; else got=bad; fi
    [ "$got" = "${v#*=}" ] || { echo "✗ duplicate pair $1/$2 judged '$got' (want '${v#*=}')"; rc=1; }
  done
  rm -f "$pb" "$pr" "$pd"
  [ "$rc" = 0 ] && echo "run-d11 selftest: state classifier OK (9 non-readings caught, 7 readings passed through) · direct-read parser OK (3 failures and a count-less body → READ-FAILED, 3 readings) · degraded-body check OK (2 caught, 3 passed) · release counter OK (6 readings, 7 non-readings → ERROR: incl. missing run data, a further in-window page, a missing or unparseable start) · duplicate pair OK (4 accepted incl. a 409, 4 refused) · unchanged verdict OK (5 cases; two empty readings are not a pass)"
  exit "$rc"
fi

URL="${OWNER_ACTION_URL:?set OWNER_ACTION_URL}"
SEC="${OWNER_HMAC_SECRET:?set OWNER_HMAC_SECRET}"
CID="${CF_OWNER_ACCESS_CLIENT_ID:?set CF_OWNER_ACCESS_CLIENT_ID (from ~/.n8n-api.env)}"
CSE="${CF_OWNER_ACCESS_CLIENT_SECRET:?set CF_OWNER_ACCESS_CLIENT_SECRET}"
TGT="${TARGET_RECORD:?set TARGET_RECORD — the record id (rec…) of a conversation in stage=handoff}"
# ⚠ STATE_URL is not a standing endpoint: the 2026-09-13 7/7 run used a TEMPORARY n8n workflow that
# returned "stage|last_intent" for a posted record_id, created for the drill and deleted after it. Recreate
# it (or supply the read-only database env) before re-running, or cases 4/5/6 have no way to
# read the DATA — and this file's whole premise is that a status code is only half the test.

RUN="$(date +%s)"
PASS=0; FAIL=0

say()  { printf '%-58s %s\n' "$1" "$2"; }
ok()   { PASS=$((PASS+1)); say "$1" "✓ $2"; }
bad()  { FAIL=$((FAIL+1)); say "$1" "✗ $2"; }

# The HMAC secret never reaches an argv (a process list is readable by other local users): Python reads it from the env.
sign() { printf '%s' "$1" | RUN_D11_SEC="$SEC" python3 -c 'import hmac,hashlib,os,sys; print(hmac.new(os.environ["RUN_D11_SEC"].encode(), sys.stdin.buffer.read(), hashlib.sha256).hexdigest())'; }

# post <body> <signature> [--no-token]   (the response body lands in $LAST_BODY for not_degraded)
LAST_BODY="$(mktemp)"; trap 'rm -f "$LAST_BODY"' EXIT
post() {
  local body="$1" sig="$2" notok="${3:-}" hdr code
  hdr="$(mktemp)"; chmod 600 "$hdr"     # the Access secret travels in a 0600 header file, never on curl's argv
  printf 'Content-Type: application/json\nX-Owner-Signature: %s\n' "$sig" > "$hdr"
  [ "$notok" = "--no-token" ] || printf 'CF-Access-Client-Id: %s\nCF-Access-Client-Secret: %s\n' "$CID" "$CSE" >> "$hdr"
  code="$(curl -s -4 -o "$LAST_BODY" -m 25 -w '%{http_code}' -X POST "$URL" -H "@$hdr" --data "$body")"
  rm -f "$hdr"
  printf '%s' "$code"
}

not_degraded() { # not_degraded <case label> <code> — FAILS a 200 whose body declares itself degraded; never adds a pass
  [ "$2" = "200" ] && is_degraded "$LAST_BODY" && bad "  ↳ $1" "200, but the body says degraded ($(head -c 80 "$LAST_BODY"))"
  return 0
}

body_for() { # body_for <action> <sender> <messageId> <ts>
  printf '{"action":"%s","record_id":"%s","messageId":"%s","ts":%s}' "$1" "$2" "$3" "$4"
}

# Reading the STATE is half the test: cases 4/5/6 must show what the DATA did, not what a status code
# said. Two routes, because the credential you have depends on where you are standing:
#   · the read-only database env (PGHOST, PGDATABASE, PGUSER, PGPASSWORD; salon_ro): a direct read of the row
#     AND the replay-marker count. (Before D5 this route was an Airtable PAT and could not count markers.)
#   · STATE_URL — an endpoint that returns "stage|last_intent|count" for a posted record_id (the Drill State
#     Read workflow). A machine that holds the ENGINE's credentials but no read-only database login has this
#     route and not the first one; that was the situation on 2026-09-13.
# With NEITHER configured it returns NO-STORE and case 6 still FAILS loudly — two equal readings from an
# instrument that measured nothing are a broken instrument, not a pass. The fallback adds a route, it does not
# add a way to pass without evidence.
state_of() { # state_of [messageId]  -> "stage|last_intent|markerCount"
  local mid="${1:-zz-no-such-message-id}"
  if [ -n "${STATE_URL:-}" ]; then
    local body sig
    body="$(printf '{"action":"read_drill_state","record_id":"%s","messageId":"%s"}' "$TGT" "$mid")"
    sig="$(sign "$body")"
    local hdr; hdr="$(mktemp)"; chmod 600 "$hdr"
    printf 'Content-Type: application/json\nX-Owner-Signature: %s\n' "$sig" > "$hdr"
    [ -n "${CF_OWNER_ACCESS_CLIENT_ID:-}" ] && printf 'CF-Access-Client-Id: %s\nCF-Access-Client-Secret: %s\n' "$CF_OWNER_ACCESS_CLIENT_ID" "${CF_OWNER_ACCESS_CLIENT_SECRET:-}" >> "$hdr"
    curl -s -4 -m 25 -X POST "$STATE_URL" -H "@$hdr" --data "$body"
    rm -f "$hdr"
    return
  fi
  [ -n "${PGHOST:-}" ] && [ -n "${PGDATABASE:-}" ] && [ -n "${PGUSER:-}" ] && [ -n "${PGPASSWORD:-}" ] \
    || { echo "NO-STORE"; return; }
  RUN_D11_PG="$(cd "$(dirname "$0")/.." && pwd)/web/node_modules/pg" RUN_D11_TGT="$TGT" RUN_D11_MID="$mid" \
    timeout 25 node -e "$DIRECT_JS" 2>/dev/null | python3 -c "$DIRECT_PARSE"
}

# A REFUSAL THAT STILL WROTE is the failure this endpoint exists to prevent, and checking only the status
# code cannot see it: "write, then return 403" passes a status-only assertion. Every rejected request is
# therefore followed by this.
assert_unchanged() { # assert_unchanged <case label> <expected state>
  local now; now="$(state_of)"
  case "$(unchanged_verdict "$2" "$now")" in
    ok)         ok "  ↳ $1" "target row UNCHANGED after the refusal" ;;
    error)      bad "  ↳ $1" "the state oracle returned a STORE ERROR ('${now%%|*}') — 'unchanged' cannot be judged" ;;
    unmeasured) bad "  ↳ $1" "no state route configured — 'unchanged' cannot be judged (two empty readings are not a pass)" ;;
    *)          bad "  ↳ $1" "the refusal still MOVED the row: '$2' -> '$now'" ;;
  esac
}

echo "run-d11 — nine cases, tag $RUN"
echo "target record: ${TGT:0:3}…  (masked — security-secrets.md redacts record ids to a bare rec…)"
BEFORE="$(state_of)"; echo "state before: $BEFORE"
if is_state_error "$BEFORE"; then
  echo "✗ ABORT: the state oracle reported a store error ('${BEFORE%%|*}'). Nothing this run could assert"
  echo "  about the DATA would be evidence, so it stops here instead of producing green that means nothing."
  exit 2
fi
echo

NOW=$(date +%s)
B_OK="$(body_for release_handoff "$TGT" "d11-$RUN" "$NOW")"
S_OK="$(sign "$B_OK")"

# 1 — no service token. CONTROL for every later case.
c1="$(post "$B_OK" "$S_OK" --no-token)"
not_degraded "1 no service token" "$c1"
[ "$c1" = "403" ] && ok "1 no service token" "403 (Access refused)" \
                  || bad "1 no service token" "got $c1, expected 403"
assert_unchanged "1 no service token" "$BEFORE"

# 2 — token present, signature wrong.
c2="$(post "$B_OK" "$(sign "${B_OK}tampered")")"
not_degraded "2 token OK, HMAC wrong" "$c2"
[ "$c2" = "403" ] && ok "2 token OK, HMAC wrong" "403" \
                  || bad "2 token OK, HMAC wrong" "got $c2, expected 403"
assert_unchanged "2 token OK, HMAC wrong" "$BEFORE"

# 3 — signed correctly, action outside the allow-list.
B3="$(body_for delete_everything "$TGT" "d11-$RUN-3" "$NOW")"
c3="$(post "$B3" "$(sign "$B3")")"
not_degraded "3 action off the allow-list" "$c3"
[ "$c3" = "400" ] && ok "3 action off the allow-list" "400" \
                  || bad "3 action off the allow-list" "got $c3, expected 400"
assert_unchanged "3 action off the allow-list" "$BEFORE"

# 7 — stale ts (run before the real release so it cannot be masked by an already-released target).
B7="$(body_for release_handoff "$TGT" "d11-$RUN-7" "$((NOW-3600))")"
c7="$(post "$B7" "$(sign "$B7")")"
not_degraded "7 ts older than the window" "$c7"
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
not_degraded "4 wrong target" "$c4"
A4="$(state_of)"    # same shape as BEFORE, so the comparison below is a real one
if { [ "$c4" = "404" ] || [ "$c4" = "409" ]; } && [ "$A4" = "$BEFORE" ]; then
  ok "4 wrong target (well-formed, nonexistent)" "$c4 and the target row is UNCHANGED"
else
  bad "4 wrong target (well-formed, nonexistent)" "got $c4, state ${BEFORE} -> ${A4}"
fi

# 4b — a MALFORMED record id must be refused by the allow-list, before any lookup, and write nothing.
B4b="$(body_for release_handoff "recNOPE" "d11-$RUN-4b" "$NOW")"
c4b="$(post "$B4b" "$(sign "$B4b")")"
not_degraded "4b malformed record id" "$c4b"
[ "$c4b" = "400" ] && ok "4b malformed record id" "400 at the allow-list, before the lookup" \
                   || bad "4b malformed record id" "got $c4b, expected 400"
assert_unchanged "4b malformed record id" "$BEFORE"

# 5 + 6 — the real release, raced against its own duplicate (7-2 Tur 2, Codex CRT 11 MEDIUM).
# ⚠ WHAT THE OLD CASE COULD NOT SHOW. It released, then sent the same request again and counted dedupe MARKERS
# (1 -> 1). Two faults: the marker statement was an upsert, so one marker survives any number of releases; and the
# sequential replay never reached the replay check at all — `Target Locked?` runs BEFORE `Check Owner Replay`, so the
# released row answered 409 first. A real duplicate is CONCURRENT: both requests pass the lock gate before either
# writes. So the same signed request is sent twice AT ONCE, and RELEASES are counted where they happen — the n8n
# executions in which `Release Handoff Lock` returned a real row (not its sentinel). Statuses are asserted, not printed.
B1="$(mktemp)"; B2="$(mktemp)"; trap 'rm -f "$LAST_BODY" "$B1" "$B2"' EXIT
RUN_START="$(date -u +%Y-%m-%dT%H:%M:%S)"
( LAST_BODY="$B1"; post "$B_OK" "$S_OK" > "$B1.code" ) &
( LAST_BODY="$B2"; post "$B_OK" "$S_OK" > "$B2.code" ) &
wait
c5a="$(cat "$B1.code")"; c5b="$(cat "$B2.code")"; rm -f "$B1.code" "$B2.code"
sleep 4   # the executions are persisted after the responses
AFTER1="$(state_of "d11-$RUN")"
REL="$(release_count "$RUN_START")"
if dup_pair_ok "$c5a" "$c5b" "$B1" "$B2"; then
  ok "5 statuses (the duplicate pair)" "$c5a / $c5b — one clean 200; the duplicate 200 (replayed), 502 (sentinel) or 409 (saw it released)"
else
  bad "5 statuses (the duplicate pair)" "got $c5a / $c5b — expected one clean 200 and the other 200, 502 or 409"
fi
case "$REL" in
  "COUNT 1") ok "5 releases (the duplicate pair)" "exactly ONE execution wrote the release; the duplicate wrote nothing" ;;
  COUNT*)    bad "5 releases (the duplicate pair)" "${REL#COUNT } executions wrote a release (expected exactly 1)" ;;
  *)         bad "5 releases (the duplicate pair)" "releases cannot be counted ($REL) — a status code is not evidence of a write" ;;
esac
# 5b — a SEQUENTIAL replay of the released request meets the lock gate first: 409, nothing written.
c5c="$(post "$B_OK" "$S_OK")"
[ "$c5c" = "409" ] && ok "5b sequential replay after the release" "409 not_locked (the lock gate answers before the replay check)" \
                   || bad "5b sequential replay after the release" "got $c5c, expected 409"
AFTER2="$(state_of "d11-$RUN")"
for st in "$A4" "$AFTER1" "$AFTER2"; do
  is_state_error "$st" && bad "state read during cases 4–6" "the state oracle returned a STORE ERROR ('${st%%|*}')"
done

# 6 — write-then-verify, from the DATA not the status code.
if [ "$AFTER1" = "NO-STORE" ]; then
  bad "6 released state" "no state route configured — cannot verify the DATA, only the code ($c5a)"
elif [ "${AFTER1%|*}" = "new|" ]; then
  ok "6 released state" "stage='new' AND last_intent empty"
else
  bad "6 released state" "expected 'new|…', got '$AFTER1'"
fi
[ "$AFTER2" = "$AFTER1" ] || bad "6 state after the sequential replay" "the row moved: '$AFTER1' -> '$AFTER2'"

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
