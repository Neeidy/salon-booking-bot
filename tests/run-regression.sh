#!/usr/bin/env bash
# Regression harness — the curl-only (no Airtable setup) subset of tests/regression-suite.md.
# Asserts the customer-facing reply. The node-path / MUST-NOT-RUN column is verified separately
# from the n8n execution API (see the suite doc). Scenarios needing injected Airtable state or
# credential/config changes (⚙ in the suite) are NOT run here — run them assisted.
#
# Usage:  WEBHOOK_URL="https://<your-n8n-host>/webhook/barber-inbound" bash tests/run-regression.sh
#         (production webhook = no arming. For the draft/-test webhook you must arm before EACH call,
#          so this harness is intended for the published production webhook.)
#         The host is NOT hardcoded — this is a public, reusable template; pass your own host via env.
set -u
URL="${WEBHOOK_URL:?set WEBHOOK_URL to your published webhook, e.g. https://<n8n-host>/webhook/barber-inbound}"
RUN="$(date +%s)"               # unique tag so messageIds never collide with a previous run
PASS=0; FAIL=0; N=0

fire() { # session text msgid  -> echoes reply body
  curl -sS -X POST "$URL" -H 'Content-Type: application/json' \
    -d "{\"channel\":\"widget\",\"sessionId\":\"$1\",\"text\":\"$2\",\"messageId\":\"$3\"}"
}
assert() { # name reply needle
  N=$((N+1))
  if printf '%s' "$2" | grep -qi -- "$3"; then PASS=$((PASS+1)); printf 'PASS  %s\n' "$1"
  else FAIL=$((FAIL+1)); printf 'FAIL  %s\n      got: %s\n      want~ %s\n' "$1" "$2" "$3"; fi
}

WK="2026-08-26"   # a Wednesday (weekday, open) — bump if in the past

echo "== booking happy =="
S="reg-book-$RUN"
assert "1 book prompt"   "$(fire "$S" "Book a haircut on $WK at 14:00 please" "$S-1")" "shall I book"
assert "1 booked"        "$(fire "$S" "yes" "$S-2")" "You're booked"

echo "== cancel happy (fresh TTL passes) =="
assert "4 cancel prompt" "$(fire "$S" "I want to cancel my appointment" "$S-3")" "Cancel your"
assert "4 cancelled 204" "$(fire "$S" "yes" "$S-4")" "is cancelled"

echo "== FAQ =="
F="reg-faq-$RUN"
assert "16 faq price"    "$(fire "$F" "what are your prices?" "$F-1")" "prices"

echo "== lead =="
L="reg-lead-$RUN"
assert "17 lead"         "$(fire "$L" "Can someone call me back about a package?" "$L-1")" "team"

echo "== handoff (reschedule -> handoff) =="
H="reg-ho-$RUN"
assert "18 handoff"      "$(fire "$H" "I want to reschedule to next week" "$H-1")" "team member"

echo "== Abort: FAQ intervenes mid cancel-confirm =="
# NOTE isolation: this scenario books a slot and then ABORTS the cancel (booking stands), so it must
# clean up its own booking afterwards — otherwise the live GCal event lingers and the next run's booking
# loses the race on that slot. Slots used per run: 14:00 (booking-happy, self-cancels) · 16:00 (here).
A="reg-abort-$RUN"
fire "$A" "Book a haircut on $WK at 16:00 please" "$A-1" >/dev/null
fire "$A" "yes" "$A-2" >/dev/null
fire "$A" "I want to cancel my appointment" "$A-3" >/dev/null
assert "13 abort on FAQ" "$(fire "$A" "what are your prices?" "$A-4")" "booking stands"
# cleanup — release the 16:00 booking (bot deletes the GCal event) so the slot is free next run
fire "$A" "cancel my appointment" "$A-c1" >/dev/null
fire "$A" "yes" "$A-c2" >/dev/null

echo "== idempotency (same messageId twice) =="
I="reg-idem-$RUN"; MID="$I-dup"
fire "$I" "what are your prices?" "$MID" >/dev/null      # 1st: processed
assert "3 idempotent 2nd ignored" "$(fire "$I" "what are your prices?" "$MID")" "duplicate_ignored"

echo "== invalid payload -> 400 (Validate Payload reject) =="
BAD="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$URL" -H 'Content-Type: application/json' \
       -d "{\"channel\":\"widget\",\"sessionId\":\"regbad-$RUN\",\"text\":\"hi\"}")"   # no messageId -> reject
N=$((N+1)); if [ "$BAD" = "400" ]; then PASS=$((PASS+1)); echo "PASS  20 invalid payload 400"
else FAIL=$((FAIL+1)); echo "FAIL  20 invalid payload (got HTTP $BAD, want 400)"; fi

echo "== cancel with NO booking -> cancelNoBooking =="
NB="reg-nobk-$RUN"
assert "21 cancel no-booking" "$(fire "$NB" "cancel my appointment" "$NB-1")" "active booking"

echo "== handoff lock (2nd message on a handed-off session) =="
HL="reg-lock-$RUN"
fire "$HL" "I want to reschedule to next week" "$HL-1" >/dev/null   # reschedule -> stage=handoff
assert "22 handoff lock" "$(fire "$HL" "actually what are your hours?" "$HL-2")" "already helping"

echo
echo "== BASELINE (curl-only subset): $PASS/$N passed, $FAIL failed =="
echo "== ⚙ setup-heavy scenarios (race · 401 · Validate rejects · legacy tc=0 · TTL stale · bind · cancelTargetGone · guard-trip) are run assisted — see tests/regression-suite.md =="
[ "$FAIL" -eq 0 ]
