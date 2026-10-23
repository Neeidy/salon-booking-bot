#!/usr/bin/env bash
# Offline test of db/ops/m7-window.sh (MIGRATION-PLAN §3s, D4 plan §7, ruling D4-8). No root, no Postgres, no
# network, never the real docker.
# The script runs as a COPY in which only the `docker` word is pointed at a fake (absolute path, count asserted),
# so psql_as() / mig() / q() / superuser() themselves run. The fake checks the exact `compose … exec … psql`
# argument shape per role (salon_migrator over TCP with its password by environment; postgres over the local socket
# with no environment at all), then plays a store that models the boundaries this script depends on:
#   · salon_migrator has no USAGE on schema salon, so `salon.` before `SET ROLE salon_owner` is denied (002_roles);
#   · only salon_owner may GRANT/REVOKE on the tables; only the database owner, postgres, may GRANT/REVOKE CONNECT
#     on database salon or terminate salon_app's sessions;
#   · REVOKE CONNECT alone leaves open sessions open (the pool risk); only the termination closes them.
# Every statement the SUPERUSER receives is logged verbatim, and the D4-8 boundary is asserted three ways: what the
# superuser received in every scenario · the shape of the code (one superuser call site, keyword in, no stdin
# passed through) · the function itself, run in isolation with SQL piped at it and an unknown keyword.
# Run: bash tests/ops/m7-window.test.sh
#      M7_WINDOW_SRC=<file> bash tests/ops/m7-window.test.sh   (test another version, e.g. a mutant)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${M7_WINDOW_SRC:-$ROOT/db/ops/m7-window.sh}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir "$T/bin" "$T/trip"
printf '#!/bin/sh\ntouch %s/tripped\nexit 99\n' "$T" > "$T/trip/docker"; chmod +x "$T/trip/docker"; export PATH="$T/trip:$PATH"
cat > "$T/fakedb.py" <<'PY'
import sys, re, os, json
args = sys.argv[1:]
head = ['compose', '--project-directory', '/root/n8n', 'exec', '-T']
tail = ['postgres', 'psql', '-X', '-At', '-q', '-v', 'ON_ERROR_STOP=1', '-U']
if args[:len(head)] != head:
    sys.stderr.write('fake docker: unexpected command shape: %r\n' % args); sys.exit(9)
rest = args[len(head):]
envs = []
while rest[:1] == ['-e']:
    envs.append(rest[1]); rest = rest[2:]
if rest[:len(tail)] != tail or rest[len(tail) + 1:] != ['-d', 'salon', '-f', '-']:
    sys.stderr.write('fake docker: unexpected command shape: %r\n' % args); sys.exit(9)
user = rest[len(tail)]
if user == 'salon_migrator':
    if envs != ['PGPASSWORD', 'PGHOST=127.0.0.1'] or os.environ.get('PGPASSWORD') != 'fake-mig-pw':
        sys.stderr.write('fake psql: password authentication failed for user "salon_migrator"\n'); sys.exit(2)
elif user == 'postgres':
    if envs:   # the superuser path carries NO environment: no password, no host (the container's local socket)
        sys.stderr.write('fake docker: the superuser call must pass no environment, got %r\n' % envs); sys.exit(9)
    if os.environ.get('M7_SU_DOWN'):
        sys.stderr.write('fake psql: FATAL:  role "postgres" could not authenticate\n'); sys.exit(2)
else:
    sys.stderr.write('fake psql: unexpected role %r\n' % user); sys.exit(9)
if os.environ.get('M7_DOWN') or (os.environ.get('M7_DOWN_AFTER') and os.path.exists(os.environ['M7_DOWN_AFTER'])):
    sys.stderr.write('fake psql: connection refused\n'); sys.exit(2)
stp = os.environ['M7_STATE']
st = json.load(open(stp)) if os.path.exists(stp) else {'missing': [], 'connect': True, 'sessions': 2}
miss = set(st['missing'])
log = open(os.environ['M7_LOG'], 'a')
sulog = open(os.environ['M7_SULOG'], 'a')
role, out = user, []
def fail(n, msg):
    sys.stderr.write('psql:<stdin>:%d: ERROR:  %s\n' % (n, msg)); sys.exit(3)   # ON_ERROR_STOP: nothing is kept
for n, stmt in enumerate([x.strip() for x in sys.stdin.read().split(';') if x.strip()], 1):
    log.write('%s %s\n' % (role, stmt.split()[0].upper()))
    if user == 'postgres':
        sulog.write(' '.join(stmt.split()) + ';\n')
    if stmt == 'SET ROLE salon_owner':
        if user != 'salon_migrator': fail(n, 'permission denied to set role "salon_owner"')
        role = 'salon_owner'; continue
    if re.search(r"\bsalon\.|\bIN SCHEMA salon\b", stmt) and role not in ('salon_owner', 'postgres'):
        fail(n, 'permission denied for schema salon')
    if re.search(r'\bON DATABASE salon\b', stmt):
        if role != 'postgres': fail(n, 'must be owner of database salon')
        if stmt == 'REVOKE CONNECT ON DATABASE salon FROM salon_app': st['connect'] = False
        if stmt == 'GRANT CONNECT ON DATABASE salon TO salon_app' and not os.environ.get('M7_GRANT_NOOP'): st['connect'] = True
        continue
    if 'pg_terminate_backend' in stmt:
        if role != 'postgres': fail(n, 'permission denied to terminate process')
        out.append(str(st['sessions']))
        if not os.environ.get('M7_TERMINATE_NOOP'): st['sessions'] = 0
        continue
    if stmt.startswith(('GRANT', 'REVOKE')) and role != 'salon_owner':
        fail(n, 'permission denied for table')
    if stmt == 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA salon TO salon_app':
        miss = set()
    for privs, tabs in re.findall(r'^REVOKE ([A-Z, ]+) ON (salon\.[a-z_, .]+) FROM salon_app$', stmt):
        for p in [x.strip() for x in privs.split(',')]:
            for t in [x.strip().replace('salon.', '') for x in tabs.split(',')]:
                miss.add(f'{t}:{p}')
    if os.environ.get('M7_SABOTAGE') and stmt.startswith('REVOKE') and 'ON salon.' in stmt: miss.add('leads:SELECT')
    if 'has_table_privilege' in stmt: out.append(' '.join(sorted(miss)) or '-')
    if 'has_database_privilege' in stmt: out.append('t' if st['connect'] else 'f')
    if stmt.startswith('SELECT count(*) FROM pg_stat_activity'): out.append(str(st['sessions']))
st['missing'] = sorted(miss)
json.dump(st, open(stp, 'w'))
print('\n'.join(out), end='\n' if out else '')
PY
printf '#!/bin/sh\nexec python3 %s "$@"\n' "$T/fakedb.py" > "$T/bin/docker"; chmod +x "$T/bin/docker"
printf 'SALON_MIGRATOR_PASSWORD=fake-mig-pw\n' > "$T/env"
prep() {   # the copy may reach only the fake docker (tokens counted, comments excluded)
  sed -e "s#^ENV=.*#ENV=$T/env#" -e "s#^FLAGS=.*#FLAGS=$T/flags#" -e 's#^WAIT_START=.*#WAIT_START=6#' \
      -e 's#^WAIT_STAGE=.*#WAIT_STAGE=6#' -e "s#/root/m7-window.lock#$T/lock#" -e 's#\[ "$(id -u)" = 0 \] ||#true ||#' \
      -e "s#docker compose#$T/bin/docker compose#" "$1" > "$2"
  [ "$(grep -v '^[[:space:]]*#' "$2" | grep -ow 'docker' | wc -l)" = 1 ] && [ "$(grep -c "$T/bin/docker compose" "$2")" = 1 ] \
    || { echo "✗ setup: $2 must call docker exactly once, through the fake"; exit 1; }
}
prep "$SRC" "$T/t.sh"
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "✓ $1"; else fail=$((fail+1)); echo "✗ $1"; echo "$out" | sed 's/^/    /'; fi; }
fresh() { rm -rf "$T/flags" "$T/state" "$T/down" "$T/log" "$T/sulog"; mkdir "$T/flags"; touch "$T/sulog"; }
run() { out="$(M7_STATE="$T/state" M7_LOG="$T/log" M7_SULOG="$T/sulog" "$@" 2>&1 </dev/null)"; rc=$?; cat "$T/sulog" >> "$T/sulog-all"; }   # stdin closed: a mutant that reads it must not hang the test
st() { python3 -c "import json;d=json.load(open('$T/state'));print(('t' if d['connect'] else 'f'), ' '.join(d['missing']) or '-', d['sessions'])"; }
setstate() { printf '%s' "$1" > "$T/state"; }
SU_REVOKE='REVOKE CONNECT ON DATABASE salon FROM salon_app;'
SU_GRANT='GRANT CONNECT ON DATABASE salon TO salon_app;'
SU_TERM="SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity WHERE usename = 'salon_app' AND datname = 'salon';"
: > "$T/sulog-all"

echo "— m7-window.sh --check —"
fresh; rm -rf "$T/flags"; run bash "$T/t.sh" --check
check "--check on the baseline: OK, exit 0; the superuser received only its no-op GRANT CONNECT; nothing changed" '[ $rc = 0 ] && grep -q "check: OK" <<<"$out" && [ "$(cat $T/sulog)" = "$SU_GRANT" ] && [ "$(st)" = "t - 2" ] && ! grep -q "^salon_owner \(GRANT\|REVOKE\)" "$T/log"'
fresh; setstate '{"missing": [], "connect": false, "sessions": 0}'; run bash "$T/t.sh" --check
check "--check while CONNECT is revoked: FAILED naming the state, exit 1, and the superuser received NOTHING (no repair by --check)" '[ $rc = 1 ] && grep -q "state is .f -." <<<"$out" && [ ! -s "$T/sulog" ] && [ "$(st)" = "f - 0" ]'
fresh; setstate '{"missing": ["leads:SELECT"], "connect": true, "sessions": 0}'; run bash "$T/t.sh" --check
check "--check while a table privilege is missing: FAILED, exit 1, changes nothing" '[ $rc = 1 ] && grep -q "leads:SELECT" <<<"$out" && [ ! -s "$T/sulog" ]'
fresh; run env M7_SU_DOWN=1 bash "$T/t.sh" --check
check "--check when the superuser path cannot authenticate: FAILED with that reason, exit 1" '[ $rc = 1 ] && grep -q "superuser path did not run" <<<"$out" && grep -q "could not authenticate" <<<"$out"'
fresh; run env M7_DOWN=1 bash "$T/t.sh" --check
check "--check with Postgres unreachable: FAILED, exit 1" '[ $rc = 1 ] && grep -q "check: FAILED" <<<"$out"'
fresh; run bash "$T/t.sh" --bogus
check "an unknown argument: usage, exit 2, nothing run" '[ $rc = 2 ] && grep -q "usage" <<<"$out" && [ ! -e "$T/log" ]'

echo "— m7-window.sh, the window —"
fresh; ( sleep 1; touch "$T/flags/go"; for s in C1 T1 T2 T3; do sleep 1; touch "$T/flags/$s.done"; done ) &
run bash "$T/t.sh"; wait
check "full run: C1 T1 T2 T3 in order, then RESTORED, exit 0, state t - and no session left" '[ $rc = 0 ] && [ "$(grep -o "stage [A-Z0-9]* applied" <<<"$out" | tr "\n" " ")" = "stage C1 applied stage T1 applied stage T2 applied stage T3 applied " ] && grep -q "RESTORED" <<<"$out" && [ "$(st)" = "t - 0" ]'
check "C1 reported the 2 sessions it terminated and 0 open" 'grep -q "sessions terminated: 2 · open now: 0" <<<"$out"'
check "the superuser received exactly: REVOKE CONNECT, the termination, GRANT CONNECT (after C1), GRANT CONNECT (the trap)" '[ "$(cat $T/sulog)" = "$(printf "%s\n%s\n%s\n%s" "$SU_REVOKE" "$SU_TERM" "$SU_GRANT" "$SU_GRANT")" ]'
check "every table GRANT/REVOKE ran as salon_owner; every other migrator statement is a SELECT check" '[ "$(grep -c "^salon_owner REVOKE" "$T/log")" = 3 ] && ! grep -q "^salon_migrator \(GRANT\|REVOKE\)" "$T/log"'
fresh; ( sleep 1; touch "$T/flags/go" ) &
run env M7_TERMINATE_NOOP=1 bash "$T/t.sh"; wait
check "a termination that leaves a session open: C1 aborts naming it, exit 1, RESTORED (CONNECT granted again)" '[ $rc = 1 ] && grep -q "stage C1 left .f -. with 2 salon_app session" <<<"$out" && grep -q "RESTORED" <<<"$out" && [ "$(st | cut -c1-3)" = "t -" ]'
fresh; ( sleep 1; touch "$T/flags/go"; sleep 1; touch "$T/flags/C1.done" ) &
run env M7_SABOTAGE=1 bash "$T/t.sh"; wait
check "a table stage that leaves the wrong set aborts, exit 1, RESTORED" '[ $rc = 1 ] && grep -q "stage T1 left" <<<"$out" && grep -q "RESTORED" <<<"$out" && [ "$(st | cut -c1-3)" = "t -" ]'
fresh; ( sleep 1; touch "$T/flags/go" ) &
run bash "$T/t.sh"; wait
check "no C1 flag: timeout, exit 1, RESTORED with CONNECT granted" '[ $rc = 1 ] && grep -q "within 6 s" <<<"$out" && grep -q "RESTORED" <<<"$out" && [ "$(st | cut -c1-3)" = "t -" ]'
fresh; ( sleep 1; touch "$T/flags/go" ) & run timeout -s INT 8 bash "$T/t.sh"; wait
check "Ctrl-C while C1 is applied: RESTORED, CONNECT granted" 'grep -q "stage C1 applied" <<<"$out" && grep -q "RESTORED" <<<"$out" && [ "$(st | cut -c1-3)" = "t -" ]'
fresh; ( sleep 1; touch "$T/flags/go"; sleep 3; touch "$T/down" ) &
run env M7_DOWN_AFTER="$T/down" bash "$T/t.sh"; wait
check "the store goes away during C1: RESTORE FAILED, exit 1 (never a false RESTORED)" '[ $rc = 1 ] && grep -q "RESTORE FAILED" <<<"$out" && ! grep -q "RESTORED —" <<<"$out"'
fresh; ( sleep 1; touch "$T/flags/go" ) &
run env M7_GRANT_NOOP=1 bash "$T/t.sh"; wait
check "a GRANT CONNECT that does not take: RESTORE FAILED, exit 1" '[ $rc = 1 ] && grep -q "RESTORE FAILED" <<<"$out"'
fresh; setstate '{"missing": [], "connect": false, "sessions": 0}'; run bash "$T/t.sh"
check "CONNECT not granted before the window: refuses, changes nothing" '[ $rc = 1 ] && grep -q "before the window" <<<"$out" && [ ! -s "$T/sulog" ]'
fresh; touch "$T/flags/C1.done"; run bash "$T/t.sh"
check "a stale flag: refuses to start" '[ $rc = 1 ] && grep -q "not empty" <<<"$out" && [ ! -e "$T/state" ]'
rm -rf "$T/flags"; run bash "$T/t.sh"
check "no flag directory: refuses" '[ $rc = 1 ] && grep -q "does not exist yet" <<<"$out"'
if [ "$(id -u)" != 0 ]; then out="$(bash "$SRC" 2>&1)"; rc=$?; check "the real m7-window.sh refuses a non-root user" '[ $rc = 2 ] && grep -q "run as root" <<<"$out"'; fi

echo "— m7-window.sh --restore —"
fresh; setstate '{"missing": ["conversations:INSERT"], "connect": false, "sessions": 0}'; run bash "$T/t.sh" --restore
check "--restore from a revoked state: OK, exit 0, state t -" '[ $rc = 0 ] && grep -q "restore: OK" <<<"$out" && [ "$(st | cut -c1-3)" = "t -" ]'
fresh; setstate '{"missing": [], "connect": false, "sessions": 0}'; run env M7_SU_DOWN=1 bash "$T/t.sh" --restore
check "--restore when the superuser path fails: FAILED, exit 1, never OK" '[ $rc = 1 ] && grep -q "restore: FAILED" <<<"$out" && ! grep -q "restore: OK" <<<"$out"'

echo "— the superuser boundary (D4-8) —"
out="$(sort -u "$T/sulog-all")"
check "across EVERY scenario above, the superuser received only the three allowed statements (two kinds)" '[ -n "$out" ] && [ -z "$(grep -vxF -e "$SU_REVOKE" -e "$SU_GRANT" -e "$SU_TERM" <<<"$out")" ]'
code="$(grep -v '^[[:space:]]*#' "$SRC")"
out="$(grep -n 'postgres' <<<"$code")"
check "the code names the postgres role in exactly one call, inside superuser()" '[ "$(grep -c "psql_as postgres" <<<"$code")" = 1 ] && [ "$(grep -cw -- "-U postgres" <<<"$code")" = 0 ] && awk "/^superuser\\(\\) \\{/,/^\\}/" "$SRC" | grep -q "psql_as postgres"'
body="$(awk '/^superuser\(\) \{/,/^\}/' "$SRC")"
out="$body"
check "superuser() reads no stdin of its own and takes no SQL argument: one keyword, mapped by a case" '! grep -qE "\bcat\b|\\\$\{?[2-9@*]|read " <<<"$body" && grep -q "case \"\$1\" in" <<<"$body"'
# The function, run in isolation: psql_as replaced by a logger that records what the superuser would receive.
cat > "$T/iso.sh" <<EOF
psql_as() { [ "\$1" = postgres ] && { printf '%s\n' "\$(cat)" >> "$T/iso.log"; }; }
$body
echo 'DROP DATABASE salon;' | superuser grant
superuser 'DROP DATABASE salon' && echo "UNKNOWN-ACCEPTED"
superuser revoke-all && echo "UNKNOWN-ACCEPTED"
EOF
rm -f "$T/iso.log"; out="$(bash "$T/iso.sh" 2>&1)"
check "piped SQL is not passed through (the superuser got GRANT CONNECT only), and unknown keywords are refused" '[ "$(cat "$T/iso.log")" = "$SU_GRANT" ] && ! grep -q UNKNOWN-ACCEPTED <<<"$out" && [ "$(grep -c "superuser refused" <<<"$out")" = 2 ]'
out=''; check "the PATH tripwire was never called (no copy reached a real docker)" '[ ! -e "$T/tripped" ]'
echo "m7 script test: $pass passed, $fail failed"
[ "$fail" = 0 ]
