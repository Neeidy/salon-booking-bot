#!/usr/bin/env bash
# Offline test of db/ops/k3-window.sh and db/ops/k3-restore.sh (MIGRATION-PLAN §3r, K-3). No root, no Postgres,
# no network, never the real docker.
# Each script runs as a COPY in which only the `docker` word is pointed at a fake (absolute path, count asserted),
# so q() / as() / owner() themselves run. The fake checks the exact `compose … exec … psql` argument shape and the
# password arriving by environment, then plays a privilege store that models the ROLE BOUNDARY of 002_roles.sql:
# the session starts as the -U role; salon_migrator has no USAGE on schema salon, so any statement touching
# `salon.` before `SET ROLE salon_owner` fails with "permission denied for schema salon" (the operator's
# measurement of 2026-10-22); only salon_owner may GRANT or REVOKE.
# Run: bash tests/ops/k3-window.test.sh
#      K3_WINDOW_SRC=<file> K3_RESTORE_SRC=<file> bash tests/ops/k3-window.test.sh   (test another version)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${K3_WINDOW_SRC:-$ROOT/db/ops/k3-window.sh}"; RSRC="${K3_RESTORE_SRC:-$ROOT/db/ops/k3-restore.sh}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/fakedb.py" <<'PY'
import sys, re, os, json
args = sys.argv[1:]
head = ['compose', '--project-directory', '/root/n8n', 'exec', '-T', '-e', 'PGPASSWORD', 'postgres',
        'psql', '-X', '-At', '-q', '-v', 'ON_ERROR_STOP=1', '-h', '127.0.0.1', '-U']
if args[:len(head)] != head or args[len(head) + 1:] != ['-d', 'salon', '-f', '-']:
    sys.stderr.write('fake docker: unexpected command shape: %r\n' % args); sys.exit(9)
user = args[len(head)]
if os.environ.get('K3_DOWN') or (os.environ.get('K3_DOWN_AFTER') and os.path.exists(os.environ['K3_DOWN_AFTER'])):
    sys.stderr.write('fake psql: connection refused\n'); sys.exit(2)
if os.environ.get('PGPASSWORD') != {'salon_migrator': 'fake-mig-pw', 'salon_app': 'fake-app-pw'}.get(user):
    sys.stderr.write('fake psql: password authentication failed for user "%s"\n' % user); sys.exit(2)
st = os.environ['K3_STATE']; s = set(json.load(open(st))) if os.path.exists(st) else set()
log = open(os.environ['K3_LOG'], 'a')
USAGE = {'salon_owner', 'salon_app', 'salon_ro'}           # 002_roles.sql: owner + GRANT USAGE … TO salon_app, salon_ro
role, out = user, []
def fail(n, msg):
    sys.stderr.write('psql:<stdin>:%d: ERROR:  %s\n' % (n, msg)); sys.exit(3)   # ON_ERROR_STOP: nothing is kept
for n, stmt in enumerate([x.strip() for x in sys.stdin.read().split(';') if x.strip()], 1):
    log.write('%s %s\n' % (role, stmt.split()[0].upper()))
    if stmt == 'SET ROLE salon_owner':
        if user != 'salon_migrator': fail(n, 'permission denied to set role "salon_owner"')
        role = 'salon_owner'; continue
    if re.search(r"\bsalon\.|\bIN SCHEMA salon\b", stmt) and role not in USAGE:
        fail(n, 'permission denied for schema salon')
    if user == 'salon_app' and os.environ.get('K3_APP_DENY'):
        fail(n, 'permission denied for schema salon')
    if stmt.startswith(('GRANT', 'REVOKE')) and role != 'salon_owner':
        fail(n, 'permission denied for table')
    if stmt == 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA salon TO salon_app':
        if not os.environ.get('K3_GRANT_NOOP'): s = set()
    for privs, tabs in re.findall(r'^REVOKE ([A-Z, ]+) ON (salon\.[a-z_, .]+) FROM salon_app$', stmt):
        for p in [x.strip() for x in privs.split(',')]:
            for t in [x.strip().replace('salon.', '') for x in tabs.split(',')]:
                s.add(f'{t}:{p}')
    if os.environ.get('K3_SABOTAGE') and stmt.startswith('REVOKE'): s.add('bot_metrics:SELECT')
    if 'has_table_privilege' in stmt and 'string_agg' in stmt: out.append(' '.join(sorted(s)) or '-')
    if 'has_table_privilege' in stmt and 'FILTER' in stmt: out.append('%d/20' % (20 - len(s)))
    if user == 'salon_app' and stmt.startswith('SELECT'):
        for t in re.findall(r'FROM salon\.(\w+)', stmt):
            if f'{t}:SELECT' in s: fail(n, 'permission denied for table ' + t)
        out.append(str(len(re.findall(r'FROM salon\.(\w+)', stmt))))
json.dump(sorted(s), open(st, 'w'))
print('\n'.join(out), end='\n' if out else '')
PY
printf '#!/bin/sh\nexec python3 %s "$@"\n' "$T/fakedb.py" > "$T/bin/docker"; chmod +x "$T/bin/docker"
printf 'SALON_MIGRATOR_PASSWORD=fake-mig-pw\nSALON_APP_PASSWORD=fake-app-pw\n' > "$T/env"
printf 'SALON_MIGRATOR_PASSWORD=fake-mig-pw\n' > "$T/env-noapp"
prep() {   # prep <src> <out> [extra sed]: the copy may reach only the fake docker
  sed -e "s#^ENV=.*#ENV=$T/env#" -e "s#^FLAGS=.*#FLAGS=$T/flags#" -e 's#^WAIT_START=.*#WAIT_START=6#' \
      -e 's#^WAIT_STAGE=.*#WAIT_STAGE=6#' -e "s#/root/k3-window.lock#$T/lock#" -e 's#\[ "$(id -u)" = 0 \] ||#true ||#' \
      -e "s#docker compose#$T/bin/docker compose#" ${3:+-e "$3"} "$1" > "$2"
  [ "$(grep -c 'docker compose' "$2")" = 1 ] && [ "$(grep -c "$T/bin/docker compose" "$2")" = 1 ] \
    || { echo "✗ setup: $2 must call docker exactly once, through the fake"; exit 1; }
}
prep "$SRC" "$T/t.sh"; prep "$RSRC" "$T/r.sh"; prep "$RSRC" "$T/r-noapp.sh" "s#^ENV=.*#ENV=$T/env-noapp#"
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "✓ $1"; else fail=$((fail+1)); echo "✗ $1"; echo "$out" | sed 's/^/    /'; fi; }
fresh() { rm -rf "$T/flags" "$T/state" "$T/down" "$T/log"; mkdir "$T/flags"; }
run() { out="$(K3_STATE="$T/state" K3_LOG="$T/log" "$@" 2>&1)"; rc=$?; }

echo "— k3-window.sh --check —"
fresh; rm -rf "$T/flags"; run bash "$T/t.sh" --check
check "--check on a full grant: OK, exit 0, no GRANT/REVOKE issued, needs no flag directory" '[ $rc = 0 ] && grep -q "check: OK" <<<"$out" && ! grep -qE "GRANT|REVOKE" "$T/log" && grep -q "^salon_owner SELECT" "$T/log" && [ "$(cat $T/state)" = "[]" ]'
fresh; echo '["leads:SELECT"]' > "$T/state"; run bash "$T/t.sh" --check
check "--check while salon_app lacks a privilege: FAILED naming it, exit 1, changes nothing" '[ $rc = 1 ] && grep -q "lacks .leads:SELECT." <<<"$out" && [ "$(cat $T/state)" = "[\"leads:SELECT\"]" ]'
fresh; run env K3_DOWN=1 bash "$T/t.sh" --check
check "--check with Postgres unreachable: FAILED, exit 1" '[ $rc = 1 ] && grep -q "check: FAILED" <<<"$out"'
fresh; run bash "$T/t.sh" --bogus
check "an unknown argument: usage, exit 2, nothing run" '[ $rc = 2 ] && grep -q "usage" <<<"$out" && [ ! -e "$T/log" ]'

echo "— k3-window.sh, the window —"
fresh; ( sleep 1; touch "$T/flags/go"; for s in W1 R1 R2 W2; do sleep 1; touch "$T/flags/$s.done"; done ) &
run bash "$T/t.sh"; wait
check "full run: four stages in order, then RESTORED, exit 0; every statement ran as salon_owner" '[ $rc = 0 ] && [ "$(grep -o "stage [A-Z0-9]* applied" <<<"$out" | tr "\n" " ")" = "stage W1 applied stage R1 applied stage R2 applied stage W2 applied " ] && grep -q "RESTORED" <<<"$out" && [ "$(cat $T/state)" = "[]" ] && [ "$(grep -vc "^salon_owner\|^salon_migrator SET" "$T/log")" = 0 ] && grep -q "^salon_owner REVOKE" "$T/log"'
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
check "Postgres unreachable at start: refuses with that reason" '[ $rc = 1 ] && grep -q "baseline check failed" <<<"$out" && grep -q "connection refused" <<<"$out"'
rm -rf "$T/flags"; run bash "$T/t.sh"
check "no flag directory: refuses" '[ $rc = 1 ] && grep -q "does not exist yet" <<<"$out"'
if [ "$(id -u)" != 0 ]; then out="$(bash "$SRC" 2>&1)"; rc=$?; check "the real k3-window.sh refuses a non-root user" '[ $rc = 2 ] && grep -q "run as root" <<<"$out"'; fi

echo "— k3-restore.sh —"
fresh; echo '["conversations:UPDATE","leads:SELECT"]' > "$T/state"; run bash "$T/r.sh"
check "restore from a revoked state: OK 20/20 and salon_app reads all 5 tables, exit 0" '[ $rc = 0 ] && grep -q "k3-restore: OK — catalog 20/20" <<<"$out" && [ "$(cat $T/state)" = "[]" ] && grep -q "^salon_app SELECT" "$T/log"'
fresh; echo '["conversations:UPDATE","leads:SELECT"]' > "$T/state"; run env K3_GRANT_NOOP=1 bash "$T/r.sh"
check "a grant that does not take: NOT restored (18/20), exit 1" '[ $rc = 1 ] && grep -q "catalog shows 18/20 privileges — NOT restored" <<<"$out"'
fresh; run env K3_APP_DENY=1 bash "$T/r.sh"
check "catalog 20/20 but salon_app cannot read: says so, exit 1, no OK" '[ $rc = 1 ] && grep -q "could not SELECT" <<<"$out" && ! grep -q "k3-restore: OK" <<<"$out"'
fresh; run env K3_DOWN=1 bash "$T/r.sh"
check "Postgres unreachable: the GRANT failed, exit 1, no OK" '[ $rc = 1 ] && grep -q "GRANT failed" <<<"$out" && ! grep -q "k3-restore: OK" <<<"$out"'
fresh; run bash "$T/r-noapp.sh"
check "salon_app password missing from the env file: refuses, exit 2, nothing run" '[ $rc = 2 ] && grep -q "password is missing" <<<"$out" && [ ! -e "$T/log" ]'
if [ "$(id -u)" != 0 ]; then out="$(bash "$RSRC" 2>&1)"; rc=$?; check "the real k3-restore.sh refuses a non-root user" '[ $rc = 2 ] && grep -q "run as root" <<<"$out"'; fi
echo "k3 scripts test: $pass passed, $fail failed"
[ "$fail" = 0 ]
