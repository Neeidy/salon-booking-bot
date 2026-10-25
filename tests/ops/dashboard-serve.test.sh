#!/usr/bin/env bash
# Offline test for web/dashboard/scripts/serve.sh and ops/systemd/salon-dashboard.service (7-F1, item 13).
# A FAKE npm on PATH stands in for `npm start`; it records its argv and the config it received. What this proves:
# serve.sh exits 78 (the unit's RestartPreventExitStatus) on an unset, missing, non-file or empty config and never
# reaches npm then; with a readable config it hands the file's exact contents to npm as CLIENT_CONFIG_JSON and runs
# `npm start`. The unit file passes `systemd-analyze --user verify` when that tool exists here. What it does NOT
# prove: restart-on-crash or start-at-boot — those are the live proof in the 7-F1 round record.
# Run: bash tests/ops/dashboard-serve.test.sh </dev/null
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${SERVE_SRC:-$ROOT/web/dashboard/scripts/serve.sh}"
UNIT="$ROOT/ops/systemd/salon-dashboard.service"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/bin/npm" <<'SH'
#!/bin/sh
echo "$*" > "$FAKE_OUT.argv"
printf '%s' "$CLIENT_CONFIG_JSON" > "$FAKE_OUT.cfg"
SH
chmod +x "$T/bin/npm"
export FAKE_OUT="$T/out"
fail=0
check() { if [ "$2" = "$3" ]; then echo "✓ $1"; else echo "✗ $1 — expected '$3', got '$2'"; fail=1; fi; }

run() { rm -f "$FAKE_OUT".*; env -u CLIENT_CONFIG_JSON PATH="$T/bin:$PATH" "$@" /bin/sh "$SRC" 2>/dev/null; }

run env -u CLIENT_CONFIG_FILE; check 'unset config → exit 78' "$?" 78
check 'unset config → npm not run' "$([ -e "$FAKE_OUT.argv" ] && echo ran || echo not-run)" not-run
run env CLIENT_CONFIG_FILE="$T/missing.json"; check 'missing config → exit 78' "$?" 78
mkdir "$T/dir.json"
run env CLIENT_CONFIG_FILE="$T/dir.json"; check 'a directory as config → exit 78' "$?" 78
: > "$T/empty.json"
run env CLIENT_CONFIG_FILE="$T/empty.json"; check 'empty config → exit 78' "$?" 78
check 'empty config → npm not run' "$([ -e "$FAKE_OUT.argv" ] && echo ran || echo not-run)" not-run
printf '{"business":{"name":"Test Shop"}}\n' > "$T/ok.json"
run env CLIENT_CONFIG_FILE="$T/ok.json"; check 'readable config → exit 0' "$?" 0
check 'readable config → npm start' "$(cat "$FAKE_OUT.argv" 2>/dev/null)" start
check 'readable config → exact contents in CLIENT_CONFIG_JSON' "$(cat "$FAKE_OUT.cfg" 2>/dev/null)" '{"business":{"name":"Test Shop"}}'

if command -v systemd-analyze >/dev/null 2>&1; then
  out="$(systemd-analyze --user verify "$UNIT" 2>&1)"; rc=$?
  check "systemd-analyze --user verify (output: ${out:-none})" "$rc" 0
else
  echo "SKIP systemd-analyze is not on this machine's PATH — the unit file was NOT verified here"
fi

[ "$fail" = 0 ] && echo "dashboard-serve: all checks passed" || echo "dashboard-serve: FAILED"
exit "$fail"
