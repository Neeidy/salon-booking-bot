#!/usr/bin/env bash
# Offline control-flow test of db/ops/k3-window.sh (MIGRATION-PLAN §3r, K-3). No root, no Postgres, no network.
# It runs a COPY of the script whose `q` is replaced by a fake privilege store (a JSON file of what salon_app
# lacks), with a local flag directory, a local lock file and short waits. The real psql call is not exercised.
# Run: bash tests/ops/k3-window.test.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; SRC="$ROOT/db/ops/k3-window.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cat > "$T/fakedb.py" <<'PY'
import sys, re, os, json
st = os.environ['K3_STATE']; s = set(json.load(open(st))) if os.path.exists(st) else set()
if os.environ.get('K3_DOWN') or (os.environ.get('K3_DOWN_AFTER') and os.path.exists(os.environ['K3_DOWN_AFTER'])):
    sys.stderr.write('fake psql: connection refused\n'); sys.exit(2)
sql = sys.stdin.read()
if 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA salon TO salon_app' in sql: s = set()
for privs, tabs in re.findall(r'REVOKE ([A-Z, ]+) ON (salon\.[a-z_, .]+) FROM salon_app', sql):
    for p in [x.strip() for x in privs.split(',')]:
        for t in [x.strip().replace('salon.', '') for x in tabs.split(',')]:
            s.add(f'{t}:{p}')
if os.environ.get('K3_SABOTAGE') and 'REVOKE' in sql: s.add('bot_metrics:SELECT')
json.dump(sorted(s), open(st, 'w'))
if 'has_table_privilege' in sql: print(' '.join(sorted(s)) or '-')
PY
echo 'SALON_MIGRATOR_PASSWORD=fake' > "$T/env"
sed -e "s#^ENV=.*#ENV=$T/env#" -e "s#^FLAGS=.*#FLAGS=$T/flags#" -e 's#^WAIT_START=.*#WAIT_START=6#' -e 's#^WAIT_STAGE=.*#WAIT_STAGE=6#' \
    -e "s#/root/k3-window.lock#$T/lock#" -e 's#\[ "$(id -u)" = 0 \] ||#true ||#' "$SRC" \
  | python3 -c "import sys,re; s=sys.stdin.read(); n=len(re.findall(r'q\(\) \{.*?\n\}\n', s, flags=re.S)); assert n==1, n; print(re.sub(r'q\(\) \{.*?\n\}\n', 'q() { python3 $T/fakedb.py; }\n', s, flags=re.S))" > "$T/t.sh"
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "✓ $1"; else fail=$((fail+1)); echo "✗ $1"; echo "$out" | sed 's/^/    /'; fi; }
fresh() { rm -rf "$T/flags" "$T/state" "$T/down"; mkdir "$T/flags"; }
run() { out="$(K3_STATE="$T/state" "$@" 2>&1)"; rc=$?; }

fresh; ( sleep 1; touch "$T/flags/go"; for s in W1 R1 R2 W2; do sleep 1; touch "$T/flags/$s.done"; done ) &
run bash "$T/t.sh"; wait
check "full run: four stages in order, then RESTORED, exit 0" '[ $rc = 0 ] && [ "$(grep -o "stage [A-Z0-9]* applied" <<<"$out" | tr "\n" " ")" = "stage W1 applied stage R1 applied stage R2 applied stage W2 applied " ] && grep -q "RESTORED" <<<"$out" && [ "$(cat $T/state)" = "[]" ]'
fresh; ( sleep 1; touch "$T/flags/go" ) &
run env K3_SABOTAGE=1 bash "$T/t.sh"; wait
check "a stage that leaves the wrong set aborts, exit 1, RESTORED" '[ $rc = 1 ] && grep -q "aborting" <<<"$out" && grep -q "RESTORED" <<<"$out" && [ "$(cat $T/state)" = "[]" ]'
fresh; ( sleep 1; touch "$T/flags/go" ) &
run bash "$T/t.sh"; wait
check "no stage flag: timeout, exit 1, RESTORED" '[ $rc = 1 ] && grep -q "within 6 s" <<<"$out" && grep -q "RESTORED" <<<"$out" && [ "$(cat $T/state)" = "[]" ]'
fresh; ( sleep 1; touch "$T/flags/go" ) & run timeout -s INT 8 bash "$T/t.sh"; wait
check "Ctrl-C while W1 is applied: RESTORED" 'grep -q "stage W1 applied" <<<"$out" && grep -q "RESTORED" <<<"$out" && [ "$(cat $T/state)" = "[]" ]'
fresh; ( sleep 1; touch "$T/flags/go"; sleep 6; touch "$T/down" ) &
run env K3_DOWN_AFTER="$T/down" bash "$T/t.sh"; wait
check "the store goes away during W1: RESTORE FAILED, exit 1 (never a false RESTORED)" '[ $rc = 1 ] && grep -q "RESTORE FAILED" <<<"$out" && ! grep -q "RESTORED —" <<<"$out"'
fresh; echo '["leads:SELECT"]' > "$T/state"; run bash "$T/t.sh"
check "salon_app not at its full grant: refuses, changes nothing" '[ $rc = 1 ] && grep -q "before the window" <<<"$out" && [ "$(cat $T/state)" = "[\"leads:SELECT\"]" ]'
fresh; touch "$T/flags/W1.done"; run bash "$T/t.sh"
check "a stale flag: refuses to start" '[ $rc = 1 ] && grep -q "not empty" <<<"$out" && [ ! -e "$T/state" ]'
fresh; run env K3_DOWN=1 bash "$T/t.sh"
check "Postgres unreachable at start: refuses with that reason" '[ $rc = 1 ] && grep -q "cannot reach Postgres" <<<"$out"'
rm -rf "$T/flags"; run bash "$T/t.sh"
check "no flag directory: refuses" '[ $rc = 1 ] && grep -q "does not exist yet" <<<"$out"'
if [ "$(id -u)" != 0 ]; then out="$(bash "$SRC" 2>&1)"; rc=$?; check "the real script refuses a non-root user" '[ $rc = 2 ] && grep -q "run as root" <<<"$out"'; fi
echo "k3-window test: $pass passed, $fail failed"
[ "$fail" = 0 ]
