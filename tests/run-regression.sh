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

# --- Assertion-strength audit (2026-08-17) — "would this assertion FAIL if the behaviour were WRONG?" ---
# The 12/12 pass is the safety gate for the whole #5 refactor, so each needle must be exit-specific.
#   1 book prompt  "shall I book"      STRONG — only the availability confirm-ask contains it
#   1 booked       "You're booked"     STRONG — bookingConfirmed only
#   4 cancel prompt "Cancel your"      STRONG — Build Cancel-Confirm only
#   4 cancelled    "is cancelled"      STRONG — cancelDone only ("already cancelled" lacks the contiguous "is cancelled")
#  16 faq price    "Haircut €25"       STRONG — tightened from "prices" to assert the real config price flows (deterministic)
#  17 lead         "got your details"  STRONG — leadCaptured only; message "Do you do hair coloring? I'm
#                                              interested" reliably classifies capture_lead (verified live in the
#                                              sub-step-2 window; the old "package call-back" message was ambiguous
#                                              and drifted to handoff, and the old "team" needle passed on both).
#  18 handoff      "team member"       STRONG — gibberish -> unknown/low-conf -> handoff -> t.handoff (reschedule is a real action since CP4)
#  13 abort        "booking stands"    STRONG — cancelAborted only
#   3 idempotent   "duplicate_ignored" STRONG — distinct short-circuit JSON
#  20 invalid      HTTP 400            STRONG — status code, not a string
#  21 no-booking   "active booking"    STRONG — cancelNoBooking only
#  22 lock         "already helping"   STRONG — handoffLocked only
# Verdict: 12/12 exit-specific (all assertions FAIL on wrong behaviour). #17 tightened 2026-08-18 after a live
# capture_lead check.

echo "== booking happy =="
S="reg-book-$RUN"
assert "1 book prompt"   "$(fire "$S" "Book a haircut on $WK at 14:00 please" "$S-1")" "shall I book"
assert "1 booked"        "$(fire "$S" "yes" "$S-2")" "You're booked"

echo "== cancel happy (fresh TTL passes) =="
assert "4 cancel prompt" "$(fire "$S" "I want to cancel my appointment" "$S-3")" "Cancel your"
assert "4 cancelled 204" "$(fire "$S" "yes" "$S-4")" "is cancelled"

echo "== FAQ =="
F="reg-faq-$RUN"
assert "16 faq price"    "$(fire "$F" "what are your prices?" "$F-1")" "Haircut €25"   # tightened: assert the real config price, not just the word "prices"

echo "== lead =="
L="reg-lead-$RUN"
assert "17 lead"         "$(fire "$L" "Do you do hair coloring? I'm interested" "$L-1")" "got your details"   # exit-specific: leadCaptured only; message reliably classifies capture_lead (verified live)

echo "== handoff (unknown/low-conf -> handoff) =="
H="reg-ho-$RUN"
assert "18 handoff"      "$(fire "$H" "asdfgh qwerty zzz ???" "$H-1")" "team member"

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
fire "$HL" "asdfgh qwerty zzz ???" "$HL-1" >/dev/null   # unknown/low-conf -> stage=handoff (reschedule is a real action since CP4)
assert "22 handoff lock" "$(fire "$HL" "actually what are your hours?" "$HL-2")" "already helping"

# --- Reschedule (CP4) — the curl-only self-cleaning subset. The failure paths (target-invalid,
# insert-fail, race-lost, verify-unavailable, delete-404, delete-unavailable, mirror-failed,
# stale-TTL, past-guard) need injected Airtable state / stripped auth (and past-guard hands off →
# locked, so curl cannot self-clean it) → they are ⚙ in tests/regression-suite.md, verified via the
# execution API. Reschedule slots (10:00/10:30 · 11:30/12:00) avoid the booking slots (14:00/16:00).
echo "== reschedule: no booking -> rescheduleNoBooking =="
RNB="reg-rnb-$RUN"
assert "24 reschedule no-booking" "$(fire "$RNB" "reschedule my appointment" "$RNB-1")" "booking to reschedule"

echo "== reschedule happy (book -> move -> Moved) =="
RH="reg-rh-$RUN"
fire "$RH" "Book a haircut on $WK at 10:00 please" "$RH-1" >/dev/null
fire "$RH" "yes" "$RH-2" >/dev/null
fire "$RH" "Move my appointment to $WK at 10:30" "$RH-3" >/dev/null
assert "25 reschedule happy -> Moved" "$(fire "$RH" "yes" "$RH-4")" "Moved"
# cleanup — cancel the MOVED (10:30) booking so no GCal event lingers
fire "$RH" "cancel my appointment" "$RH-c1" >/dev/null
fire "$RH" "yes" "$RH-c2" >/dev/null

echo "== reschedule abort (FAQ intervenes mid reschedule-confirm) =="
RA="reg-ra-$RUN"
fire "$RA" "Book a haircut on $WK at 11:30 please" "$RA-1" >/dev/null
fire "$RA" "yes" "$RA-2" >/dev/null
fire "$RA" "Move my appointment to $WK at 12:00" "$RA-3" >/dev/null   # -> reschedule_confirming
assert "27 reschedule abort" "$(fire "$RA" "what are your prices?" "$RA-4")" "booking stays"
# cleanup — the booking stands at 11:30 (aborted, no move); cancel it
fire "$RA" "cancel my appointment" "$RA-c1" >/dev/null
fire "$RA" "yes" "$RA-c2" >/dev/null

# --- Pre-hours class fix (Task 2): a REJECTED availability slot (closed/past/invalid/busy) is cleared in
# Compute Availability AND a fail-closed gate in Build Event Request routes a stray "yes" to handoff — never
# a booking on the rejected slot. closed/past/invalid create NO booking (handoff) → self-clean; busy needs a
# blocker booking → ⚙ (see tests/regression-suite.md). The needle "team member" is the handoff reply, which a
# real booking ("You're booked …") never contains — so it proves the stray "yes" did NOT book.
echo "== pre-hours: closed-hour re-ask then stray yes -> handoff, NO booking =="
PHC="reg-phc-$RUN"
fire "$PHC" "Book a haircut on $WK at 09:00 please" "$PHC-1" >/dev/null   # 09:00 < opening 10:00 -> closed
assert "37 pre-hours closed -> no book" "$(fire "$PHC" "yes" "$PHC-2")" "team member"

echo "== pre-hours: past slot re-ask then stray yes -> handoff, NO booking =="
PHP="reg-php-$RUN"
fire "$PHP" "Book a haircut on 2020-01-01 at 12:00 please" "$PHP-1" >/dev/null
assert "38 pre-hours past -> no book" "$(fire "$PHP" "yes" "$PHP-2")" "team member"

echo "== pre-hours: invalid date re-ask then stray yes -> handoff, NO booking =="
PHI="reg-phi-$RUN"
fire "$PHI" "Book a haircut on 2026-02-30 at 12:00 please" "$PHI-1" >/dev/null
assert "39 pre-hours invalid -> no book" "$(fire "$PHI" "yes" "$PHI-2")" "team member"

# --- Outbound lane (CP4b) — the curl-automatable slice: O1/O6 widget parity. The whatsapp send path
# (O2–O5) needs a signed nested payload + the execution API to see whether Send WhatsApp ran, so it is
# ⚙ in tests/regression-suite.md, not here. What IS automatable via curl: a widget request must come
# back SYNCHRONOUSLY with its real reply body — proving Channel Switch routes widget → Send Reply (widget)
# and does NOT take the whatsapp ACK-200 path (whose envelope is {"ok":true}).
echo "== outbound lane O1/O6: widget stays synchronous, NOT the whatsapp ACK path =="
OL="reg-ol-$RUN"
OLBODY="$(fire "$OL" "what are your prices?" "$OL-1")"
assert "O1/O6 widget synchronous reply" "$OLBODY" "Haircut €25"          # Channel Switch(widget) -> Send Reply (widget)
# whatsapp ACK (Respond ACK 200) MUST-NOT-RUN on widget: the reply must NOT be the {ok:true} ACK envelope
N=$((N+1)); if printf '%s' "$OLBODY" | grep -qiE '"ok"[[:space:]]*:[[:space:]]*true'; then
  FAIL=$((FAIL+1)); printf 'FAIL  O1/O6 widget took the whatsapp ACK path (got ok:true, want the synchronous reply)\n'
else PASS=$((PASS+1)); printf 'PASS  O1/O6 widget NOT the whatsapp ACK path (no ok:true envelope)\n'; fi

echo
echo "== BASELINE (curl-only subset): $PASS/$N passed, $FAIL failed =="
echo "== ⚙ setup-heavy scenarios (race · 401 · Validate rejects · legacy tc=0 · TTL stale · bind · cancelTargetGone · guard-trip · reschedule failure paths + past-guard) are run assisted — see tests/regression-suite.md =="
[ "$FAIL" -eq 0 ]
