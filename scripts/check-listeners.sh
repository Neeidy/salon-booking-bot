#!/usr/bin/env bash
# check-listeners — the SWEEP gate for `.claude/rules/remote-operator.md`.
#
# WHAT PRODUCED IT: the rule said "drill/dev servers ALWAYS bind to 127.0.0.1" and nothing ever
# looked at what was ALREADY listening. Three orphan servers accumulated under that rule —
# `0.0.0.0:8788` (2026-09-09, two days), `0.0.0.0:8789`, and `*:3001` (2026-09-10, 37 hours) — each
# found by accident while doing something else, each owned by a dead session. A rule with no sweep
# is a rule about the next bind only; this script is about the ones that are already up.
#
# THE TEST, and why it is shaped this way:
#   FAIL (exit 1) — a wildcard-bound listener whose process is VISIBLE TO THIS USER.
#     Visible-to-this-user is the precise form of "ours". `ss` shows the process for sockets owned by
#     the running user and hides it for everyone else's, so a socket we can attribute is a socket we
#     started. All three orphans were exactly this. System daemons run as root or as their own service
#     user, are unattributable from here, and are NOT this repo's failure class.
#   LIST (no failure) — every other wildcard listener, printed with its port, so a human can rule on
#     it. Yigitcan's instruction, 2026-09-12: "ÖLDÜRME — listele, ben karar veririm."
#
# ⚠ KNOWN LIMITS — read these before quoting this script as evidence of anything:
#   - It measures the BIND, not REACHABILITY. A wildcard bind may be refused by a firewall upstream
#     (measured externally on 2026-09-12 for `*:3001`: the connection timed out from Yigitcan's
#     network); a loopback bind may be fully exposed through a tunnel. This script cannot see either.
#     It answers "is a TCP socket listening on every interface", and nothing else — `ss -ltn` is TCP,
#     so a UDP listener is invisible to it, and so is a unix socket.
#   - It cannot attribute a socket owned by another user without root, so a wildcard bind by a root
#     process is listed and never failed on. That is a deliberate hole, not an oversight: this repo
#     does not start root processes.
#   - It is a SWEEP, not a prevention. It finds the fourth orphan after it exists. What prevents one
#     is the `--bind 127.0.0.1` half of the rule.
#   - It is point-in-time. A server started after it runs is invisible to the run that already passed.
#
# WHY THIS IS NOT IN `check-all`, stated as a decision rather than left looking like an omission
# (`code-reviewer` #10 / `security-auditor` L4, 2026-09-12): `check-all` is a REPO gate — it must give
# the same answer in any clone, on any machine. This script answers a question about THIS MACHINE's
# network state, which legitimately differs everywhere and changes between two runs with no commit in
# between. Wiring it in would make `check-all` fail for a reason that has nothing to do with the code
# under review, which is how a gate gets switched off. It runs at the start of a session and before a
# push, alongside the `security-auditor`.
#
# Usage:  bash scripts/check-listeners.sh
#         SS_FIXTURE=<file> bash scripts/check-listeners.sh   # classify recorded output instead
#         bash scripts/check-listeners.sh --selftest          # drill the classifier on fixtures
set -u -f   # -f: a process name from `ss` must never be glob-expanded

WILDCARD_RE='^(0\.0\.0\.0|\*|\[::\]|::)$'

# ⚠ THE `-p` IS LOAD-BEARING AND ITS ABSENCE MADE THIS SCRIPT INERT ON ITS FIRST DAY.
# Without `-p`, `ss` prints NO process column at all, so `proc` is always empty, OURS_WILDCARD is
# unreachable, and the exit-1 path is dead code — the gate printed OK for the very orphans it was
# written for. It passed its own selftest because all three FAIL fixtures were copied from an
# `ss -ltnp` run, i.e. a shape the live command could not produce: the control could not produce the
# defect (`negative-control-must-produce-the-defect`). Found by BOTH L2 auditors, independently, on
# the same day it was written. The flag is declared here, once, and the selftest asserts it is present.
SS_CMD=(ss -ltnpH)

# classify <ss -ltnH output> -> prints "VERDICT<TAB>addr<TAB>port<TAB>process"
# Returns the number of listener lines it understood, via the global `parsed`.
classify() {
  parsed=0
  local line state rq sq local_addr addr port proc
  while IFS= read -r line; do
    [ -n "${line//[[:space:]]/}" ] || continue
    # ss columns: State Recv-Q Send-Q Local:Port Peer:Port [Process]
    read -r state rq sq local_addr _peer proc <<<"$line"
    [ "$state" = "LISTEN" ] || continue
    # split host:port on the LAST colon — IPv6 hosts contain colons
    port="${local_addr##*:}"
    addr="${local_addr%:*}"
    case "$port" in ''|*[!0-9]*) continue ;; esac
    parsed=$((parsed + 1))
    local verdict
    if [[ "$addr" =~ $WILDCARD_RE ]]; then
      if [ -n "${proc:-}" ] && [[ "$proc" == users:* ]]; then
        verdict=OURS_WILDCARD
      else
        verdict=UNATTRIBUTED_WILDCARD
      fi
    else
      verdict=LOOPBACK_OR_BOUND
    fi
    printf '%s\t%s\t%s\t%s\n' "$verdict" "$addr" "$port" "${proc:--}"
  done
}

selftest() {
  local fails=0 n=0
  run_case() {  # name | input | expected verdict for the single listener line
    local name="$1" input="$2" want="$3"
    n=$((n + 1))
    local got
    got="$(printf '%s\n' "$input" | classify | head -1 | cut -f1)"
    if [ "$got" != "$want" ]; then
      printf '  FAIL  %-46s want=%s got=%s\n' "$name" "$want" "${got:-<none>}"
      fails=$((fails + 1))
    else
      printf '  ok    %-46s %s\n' "$name" "$want"
    fi
  }

  echo "check-listeners --selftest"
  # THE CASE THE SCRIPT EXISTS FOR — the three real orphans, in their recorded shapes.
  run_case 'the real *:3001 orphan (next-server, ours)' \
    'LISTEN 0 511 *:3001 *:* users:(("next-server (v1",pid=1693838,fd=21))' OURS_WILDCARD
  run_case '0.0.0.0 bind by python http.server (ours)' \
    'LISTEN 0 5 0.0.0.0:8788 0.0.0.0:* users:(("python3",pid=1,fd=3))' OURS_WILDCARD
  run_case 'IPv6 wildcard bind, ours' \
    'LISTEN 0 511 [::]:8789 [::]:* users:(("node",pid=2,fd=4))' OURS_WILDCARD
  # NEGATIVE CONTROLS — these must NOT fail the gate, or it gets switched off.
  run_case 'loopback bind is fine (this is the rule)' \
    'LISTEN 0 511 127.0.0.1:3210 0.0.0.0:* users:(("next-server (v1",pid=3,fd=5))' LOOPBACK_OR_BOUND
  run_case 'IPv6 loopback is fine' \
    'LISTEN 0 4096 [::1]:8125 [::]:* users:(("statsd",pid=4,fd=6))' LOOPBACK_OR_BOUND
  run_case 'a specific non-loopback IP is not a wildcard' \
    'LISTEN 0 128 10.0.0.5:9000 0.0.0.0:* users:(("node",pid=5,fd=7))' LOOPBACK_OR_BOUND
  run_case 'root daemon on a wildcard is listed, not failed' \
    'LISTEN 0 128 0.0.0.0:22 0.0.0.0:*' UNATTRIBUTED_WILDCARD
  run_case '* wildcard, unattributed (a real system-daemon shape)' \
    'LISTEN 0 4096 *:59999 *:*' UNATTRIBUTED_WILDCARD

  # ⚠ THE CASE THAT WAS MISSING, AND WHOSE ABSENCE MADE THE WHOLE GATE INERT. Every fixture above
  # carries `users:((…))`, which only `ss -ltnp` prints. The live command must therefore ALSO be the
  # -p form, or a real orphan arrives here looking like this and is waved through:
  run_case 'wildcard WITHOUT a process column (the -p-less shape)' \
    'LISTEN 0 511 0.0.0.0:8788 0.0.0.0:*' UNATTRIBUTED_WILDCARD
  # …which is correct classification and USELESS as a gate. So the flag itself is pinned as a case:
  n=$((n + 1))
  case " ${SS_CMD[*]} " in
    *" -ltnpH "*|*" -p "*)
      printf '  ok    %-46s %s\n' 'the live ss invocation asks for the process' "${SS_CMD[*]}" ;;
    *)
      printf '  FAIL  %-46s live command lacks -p: exit 1 is unreachable\n' 'the live ss invocation asks for the process'
      fails=$((fails + 1)) ;;
  esac

  # THE BLIND-SPOT PROOF: a classifier that returned one fixed verdict would pass a suite that only
  # ever expects that verdict. All three verdicts must be reachable, and they are asserted above.
  echo "  derived: 9 classifier cases across 3 distinct verdicts + 1 assertion on the live command"
  echo "  (a single-verdict classifier cannot pass; nor can a -p-less invocation)"
  if [ "$fails" -ne 0 ]; then
    echo "check-listeners: SELFTEST FAILED — $fails of $n"
    exit 1
  fi
  echo "check-listeners: selftest $n/$n"
  echo "  SCOPE LIMIT: these cases exercise classify() only. The live \`ss\` parse and the exit paths"
  echo "  are covered by a real run against this machine."
  exit 0
}

[ "${1:-}" = "--selftest" ] && selftest

# ---- live (or fixture) run -------------------------------------------------
raw=''
ERRF="$(mktemp)"
trap 'rm -f "$ERRF"' EXIT
if [ -n "${SS_FIXTURE:-}" ]; then
  [ -r "$SS_FIXTURE" ] || { echo "check-listeners: SS_FIXTURE '$SS_FIXTURE' is not readable" >&2; exit 2; }
  raw="$(cat -- "$SS_FIXTURE")"
  src="fixture $SS_FIXTURE"
else
  command -v ss >/dev/null 2>&1 || { echo "check-listeners: NOT MEASURED — \`ss\` is not on this machine. This is exit 2, not a pass." >&2; exit 2; }
  # The exit status is CHECKED, not discarded. `parsed == 0` catches a total failure; a PARTIAL read —
  # `ss` erroring after printing a few lines — parses fine and would otherwise be reported as a clean
  # sweep over a list that was never complete (`code-reviewer`, third pass). stderr is kept and shown.
  if ! raw="$("${SS_CMD[@]}" 2>"$ERRF")"; then
    echo "check-listeners: NOT MEASURED — \`${SS_CMD[*]}\` exited non-zero; the listener list may be" >&2
    echo "  partial, and a partial sweep reported as clean is the failure this gate exists to prevent." >&2
    sed 's/^/    /' "$ERRF" >&2
    rm -f "$ERRF"
    exit 2
  fi
  rm -f "$ERRF"
  src="live \`${SS_CMD[*]}\`"
fi

out="$(printf '%s\n' "$raw" | classify)"
# `classify` runs in a pipeline, i.e. a SUBSHELL, so the `parsed` counter it increments is destroyed
# on the way back — the first version of this script read it here and got 0 on every live run, so the
# instrument check below fired unconditionally. Caught by the script's own first live run. The
# classifier prints exactly one line per listener it understood, so count those instead.
parsed=0
[ -n "$out" ] && parsed="$(printf '%s\n' "$out" | grep -c '' )"
# THE INSTRUMENT CHECK (reporting.md: an empty result is a claim about the instrument). A machine
# always has at least one listener; zero parsed lines means the parse broke, not that the box is bare.
if [ "${parsed:-0}" -eq 0 ]; then
  echo "check-listeners: NOT MEASURED — parsed 0 listeners from $src. A machine with no listener at" >&2
  echo "  all is not a clean result, it is a broken parse. Refusing to report a zero." >&2
  exit 2
fi

# ⚠ THE SECOND INERTNESS ROUTE, closed after H1 rather than with it (`security-auditor` L5).
# `parsed > 0` proves the ADDRESS column was understood; it says nothing about the PROCESS column.
# If `ss` stops attributing — a container, a dropped capability, a future output change, or someone
# editing `-p` back out of SS_CMD — every socket classifies UNATTRIBUTED, `ours` is 0, and the gate
# returns a confident exit 0. That is H1's failure class arriving by a different road, and the selftest
# cannot see it because the selftest asserts the FLAG, not the RUNTIME RESULT. So: if nothing at all
# was attributable, this run did not measure what it claims to measure, and it says so instead of
# passing. Exit 2 is "NOT MEASURED", which is the honest answer when a box genuinely has no
# user-owned listener either — the sweep cannot tell those two apart, and pretending otherwise is the
# whole defect.
if ! printf '%s\n' "$out" | grep -q 'users:'; then
  echo "check-listeners: NOT MEASURED — $parsed listener(s) parsed from $src and NOT ONE carried a" >&2
  echo "  process column, so nothing could be attributed and the exit-1 path was unreachable for this" >&2
  echo "  run. Either the invocation lost its \`-p\` (\`${SS_CMD[*]}\`), \`ss\` cannot attribute here," >&2
  echo "  or this machine genuinely runs no listener as this user. All three look identical from" >&2
  echo "  inside, so this is exit 2 and not a pass." >&2
  exit 2
fi

ours="$(printf '%s\n' "$out"  | grep -c '^OURS_WILDCARD'          || true)"
other="$(printf '%s\n' "$out" | grep -c '^UNATTRIBUTED_WILDCARD'  || true)"

echo "check-listeners — $src: $parsed listener(s) parsed"
if [ "$other" -gt 0 ]; then
  echo "  wildcard binds NOT attributable to this user ($other) — listed for a human, not failed on:"
  printf '%s\n' "$out" | awk -F'\t' '$1=="UNATTRIBUTED_WILDCARD"{printf "    %s:%s  %s\n",$2,$3,$4}'
fi

if [ "$ours" -gt 0 ]; then
  echo
  echo "✗ $ours listener(s) started by THIS USER are bound to every interface:"
  printf '%s\n' "$out" | awk -F'\t' '$1=="OURS_WILDCARD"{printf "    %s:%s  %s\n",$2,$3,$4}'
  echo "  remote-operator.md: drill/dev servers bind 127.0.0.1 and are reached over the SSH tunnel."
  echo "  Measure it, then decide with Yigitcan — do not kill it unasked."
  exit 1
fi

echo "OK — no wildcard-bound listener is attributable to this user."
