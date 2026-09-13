#!/usr/bin/env bash
# env-presence — report whether named variables are SET, never what they hold.
#
# WHY THIS FILE EXISTS. On 2026-09-13 a one-liner meant to do exactly this printed the real values of four
# credentials into a report. The construct was `${x:+set (len ${#x})}${x:-MISSING}`: for a NON-EMPTY variable
# the first half expands to "set" AND the second half expands to the VALUE, because `${x:-...}` substitutes
# the default only when x is empty — it yields x otherwise. Two expansions were read as an if/else.
#
# The lesson is not "be careful with parameter expansion". It is `writing-about-a-secret-is-when-you-type-it`:
# the report channel has no guard and cannot have one (`check-no-host-leak.sh` KNOWN LIMITS names reports as
# an unseeable channel), so the only defence is a mechanism that CANNOT emit the value. This script never
# interpolates it — it branches on emptiness and prints a literal.
#
# Usage:  bash scripts/env-presence.sh VAR1 VAR2 ...     (source your env first)
#         bash scripts/env-presence.sh --selftest
set -u

report() {
  local name value
  for name in "$@"; do
    value="${!name-}"
    if [ -n "$value" ]; then
      printf '  %-32s set (%d chars)\n' "$name" "${#value}"
    else
      printf '  %-32s MISSING\n' "$name"
    fi
  done
}

if [ "${1-}" = "--selftest" ]; then
  # Mutation test, BOTH directions, against a value that would be unmistakable in the output.
  export ZZ_FULL='S3CR3T-canary-value-do-not-print'
  export ZZ_EMPTY=''
  out="$(report ZZ_FULL ZZ_EMPTY ZZ_UNSET)"
  fail=0
  printf '%s' "$out" | grep -qE 'ZZ_FULL +set \([0-9]+ chars\)'   || { echo "FAIL: a set variable is not reported as set"; fail=1; }
  printf '%s' "$out" | grep -q 'ZZ_EMPTY  *MISSING'          || { echo "FAIL: an empty variable is not reported MISSING"; fail=1; }
  printf '%s' "$out" | grep -q 'ZZ_UNSET  *MISSING'          || { echo "FAIL: an unset variable is not reported MISSING"; fail=1; }
  # THE assertion this file exists for.
  printf '%s' "$out" | grep -q 'S3CR3T'                      && { echo "FAIL: the VALUE reached the output — this is the 2026-09-13 defect"; fail=1; }
  # And the negative control: prove the canary check can fire, or it proves nothing.
  printf 'ZZ_FULL S3CR3T-canary-value-do-not-print\n' | grep -q 'S3CR3T' \
    || { echo "FAIL: the canary assertion cannot fire — it measures nothing"; fail=1; }
  [ "$fail" -eq 0 ] && echo "env-presence selftest: OK — set/empty/unset all correct, and the value never appears (canary check proven able to fire)"
  exit "$fail"
fi

[ "$#" -gt 0 ] || { echo "usage: bash scripts/env-presence.sh VAR [VAR...]"; exit 2; }
report "$@"
