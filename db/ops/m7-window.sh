#!/usr/bin/env bash
# M7 store-outage window (MIGRATION-PLAN §3s, D4 plan §7; ruling D4-8, 2026-10-23). OPERATOR SCRIPT: run as root,
# ONCE, on the server. Cowork reads it before it runs.
#   sudo bash m7-window.sh --check     proves both connection paths and the baseline; changes nothing
#   sudo bash m7-window.sh             the window
#   sudo bash m7-window.sh --restore   re-grants CONNECT and the table privileges, then checks both (any time)
#
# It takes salon_app's access away in four declared stages, so the inactive Main and Reminders copies can have
# their error paths drilled against a REAL store failure. The live originals run on Airtable, so no production
# path uses salon_app: only the copies notice.
#
#   C1  CONNECT on database salon, plus the termination of salon_app's open sessions   (the store is unreachable)
#   T1  UPDATE on appointments                       (Reminders: Find Due works, Stamp Reminded fails)
#   T2  SELECT on bot_metrics                         (Main: the spend read fails, M5's fail-open row)
#   T3  INSERT and UPDATE on conversations            (Main: Save State fails; D4-3's measurement)
#
# WHY the superuser appears at all: database salon is owned by `postgres` (measured 2026-10-23 through salon_ro,
# pg_database.datdba), and only a database's owner or a superuser can REVOKE CONNECT on it; salon_owner owns the
# schema, not the database. WHY sessions are terminated: REVOKE CONNECT refuses NEW connections only, so n8n's pool
# could keep serving the copy (the risk recorded with K-3). The REVOKE comes first, so a terminated session cannot
# reconnect.
# THE SUPERUSER BOUNDARY (D4-8): superuser() takes a KEYWORD, never SQL, and maps it to one of exactly two kinds of
# statement: GRANT/REVOKE CONNECT ON DATABASE salon to/from salon_app, and pg_terminate_backend over the sessions
# with usename = 'salon_app' AND datname = 'salon'. It reads no stdin, so nothing else can be piped through it.
# Every CHECK runs as salon_migrator (has_database_privilege and pg_stat_activity need no superuser); table
# grants run as salon_owner, as in k3-window.sh. --check proves the superuser path with the GRANT itself, which is
# a no-op while the grant stands: it adds no third kind of statement. tests/ops/m7-window.test.sh asserts all of it.
# How the superuser authenticates (the container's local socket, no password) is NOT measured: --check decides.
# Every stage first restores salon_app's full access and then takes its own set, then checks it; between stages
# it waits for Claude's flag file. On any exit the EXIT trap restores and CHECKS: it prints "RESTORED" only when
# CONNECT is granted and salon_app lacks no table privilege, and otherwise "RESTORE FAILED" and exits non-zero.
# Secrets: the migrator password reaches psql only by environment inheritance (PGPASSWORD + `exec -e NAME`).
# Nothing is printed but stage names, privileges and session counts.
set -euo pipefail
ENV=/root/n8n/postgres-roles.env
FLAGS=/home/yigit/m7-flags
WAIT_START=3600   # seconds to wait for Claude's "go"
WAIT_STAGE=1200   # seconds per stage before giving up (the trap still restores)

[ "$(id -u)" = 0 ] || { echo "m7-window: run as root"; exit 2; }
[ -r "$ENV" ] || { echo "m7-window: $ENV not readable"; exit 2; }
set -a; . "$ENV"; set +a
[ -n "${SALON_MIGRATOR_PASSWORD:-}" ] || { echo "m7-window: SALON_MIGRATOR_PASSWORD missing from $ENV"; exit 2; }

psql_as() {   # psql_as <role> [extra exec args…]: SQL on stdin
  local role="$1"; shift
  docker compose --project-directory /root/n8n exec -T "$@" postgres \
    psql -X -At -q -v ON_ERROR_STOP=1 -U "$role" -d salon -f -
}
mig() {   # SQL on stdin, as salon_migrator over TCP (password checked); checks only
  PGPASSWORD="$SALON_MIGRATOR_PASSWORD" psql_as salon_migrator -e PGPASSWORD -e PGHOST=127.0.0.1
}
q() {   # SQL on stdin, as salon_owner (table grants), exactly as k3-window.sh
  { printf 'SET ROLE salon_owner;\n'; cat; } | mig
}
superuser() {   # superuser revoke|grant|terminate — the ONLY superuser statements this script can send (D4-8)
  local sql
  case "$1" in
    revoke)    sql='REVOKE CONNECT ON DATABASE salon FROM salon_app;' ;;
    grant)     sql='GRANT CONNECT ON DATABASE salon TO salon_app;' ;;
    terminate) sql="SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity WHERE usename = 'salon_app' AND datname = 'salon';" ;;
    *)         echo "m7-window: superuser refused '$1' (not one of revoke, grant, terminate)"; return 1 ;;
  esac
  printf '%s\n' "$sql" | psql_as postgres
}
BASE='GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA salon TO salon_app;'
MISSING="SELECT coalesce(string_agg(t || ':' || p, ' ' ORDER BY t, p), '-')
           FROM unnest(ARRAY['appointments','bot_metrics','conversations','leads','processed_messages']) t,
                unnest(ARRAY['DELETE','INSERT','SELECT','UPDATE']) p
          WHERE NOT has_table_privilege('salon_app', 'salon.' || t, p);"
CONNECT="SELECT has_database_privilege('salon_app', 'salon', 'CONNECT');"
SESSIONS="SELECT count(*) FROM pg_stat_activity WHERE usename = 'salon_app' AND datname = 'salon';"

state() {   # prints "<connect t/f> <missing set>"; both read as salon_migrator / salon_owner, never the superuser
  local c m
  c="$(printf '%s\n' "$CONNECT" | mig)" || return 1
  m="$(printf '%s\n' "$MISSING" | q)" || return 1
  echo "$c $m"
}

restore_all() {   # returns 0 only when the restore is CHECKED
  local left='?'
  superuser grant || true
  printf '%s\n' "$BASE" | q || true
  left="$(state)" || left='?'
  [ "$left" = "t -" ]
}

on_exit() {
  local rc=$?
  trap '' INT TERM HUP             # a second Ctrl-C must not interrupt the restore itself
  if restore_all; then
    echo "m7-window: RESTORED — CONNECT granted, salon_app lacks no table privilege."
    exit "$rc"
  fi
  echo "m7-window: RESTORE FAILED (state: $(state 2>/dev/null || echo '?')). Run 'm7-window.sh --restore' NOW."
  exit 1
}

wait_for() {   # wait_for <flag> <seconds>
  local i=0
  while [ ! -e "$FLAGS/$1" ]; do
    i=$((i + 5)); [ "$i" -le "$2" ] || { echo "m7-window: no '$1' from Claude within $2 s — stopping"; exit 1; }
    sleep 5
  done
}

table_stage() {   # table_stage <name> <expected missing set> <REVOKE statements>
  printf 'BEGIN;\n%s\n%s\nCOMMIT;\n' "$BASE" "$3" | q
  local got; got="$(state)"
  [ "$got" = "t $2" ] || { echo "m7-window: stage $1 left '$got', expected 't $2' — aborting"; exit 1; }
  echo "m7-window: stage $1 applied · CONNECT granted · salon_app lacks: $2 · waiting for Claude ($1.done)"
  wait_for "$1.done" "$WAIT_STAGE"
}

case "${1:-}" in
  '') ;;
  --check)
    base="$(state)" || { echo "m7-window --check: FAILED — the salon_migrator checks did not run (psql error above)"; exit 1; }
    [ "$base" = "t -" ] || { echo "m7-window --check: FAILED — state is '$base', not 't -' (run --restore)"; exit 1; }
    superuser grant >/dev/null || { echo "m7-window --check: FAILED — the superuser path did not run (psql error above)"; exit 1; }
    echo "m7-window --check: OK — salon_migrator checks run, CONNECT is granted, salon_app lacks nothing, and the superuser path works (its GRANT CONNECT was a no-op). Nothing changed."
    exit 0 ;;
  --restore)
    if restore_all; then echo "m7-window --restore: OK — CONNECT granted, salon_app lacks no table privilege."; exit 0; fi
    echo "m7-window --restore: FAILED (state: $(state 2>/dev/null || echo '?'))"; exit 1 ;;
  *) echo "usage: m7-window.sh [--check|--restore]"; exit 2 ;;
esac

exec 9>/root/m7-window.lock
flock -n 9 || { echo "m7-window: another m7-window is running — not starting"; exit 1; }
[ -d "$FLAGS" ] || { echo "m7-window: $FLAGS does not exist yet (Claude creates it when ready) — not starting"; exit 1; }
entries="$(ls -A "$FLAGS")" || { echo "m7-window: cannot list $FLAGS — not starting"; exit 1; }
[ -z "$entries" ] || { echo "m7-window: $FLAGS is not empty (stale flags would advance stages) — not starting"; exit 1; }
base="$(state)" || { echo "m7-window: the baseline check failed (psql error above) — not starting"; exit 1; }
[ "$base" = "t -" ] || { echo "m7-window: state is '$base' before the window, not 't -' (run --restore) — not starting"; exit 1; }
trap on_exit EXIT
echo "m7-window: baseline OK (CONNECT granted, full table grant). Waiting for Claude's go ($FLAGS/go)."
wait_for go "$WAIT_START"

# The "open now: 0" check below is read by salon_migrator. Its positive control: what salon_migrator saw BEFORE must
# not be fewer than what the superuser then terminated, or salon_migrator cannot see salon_app's sessions and its 0
# means nothing (pre-push audit, 2026-10-23). With no session open at all the control is not exercised, and it says so.
seen="$(printf '%s\n' "$SESSIONS" | mig)"
superuser revoke
killed="$(superuser terminate)"
[ "$seen" -ge "$killed" ] || { echo "m7-window: salon_migrator saw $seen salon_app session(s) but $killed were terminated — its session count is blind, aborting"; exit 1; }
left="$(printf '%s\n' "$SESSIONS" | mig)"
got="$(state)"
[ "$got" = "f -" ] && [ "$left" = 0 ] || { echo "m7-window: stage C1 left '$got' with $left salon_app session(s), expected 'f -' and 0 — aborting"; exit 1; }
[ "$killed" -gt 0 ] && vis="the count's visibility shown" || vis="no session was open, so the count's visibility is NOT shown"
echo "m7-window: stage C1 applied · CONNECT revoked · salon_app sessions seen: $seen, terminated: $killed, open now: 0 ($vis) · waiting for Claude (C1.done)"
wait_for C1.done "$WAIT_STAGE"
superuser grant
table_stage T1 'appointments:UPDATE' 'REVOKE UPDATE ON salon.appointments FROM salon_app;'
table_stage T2 'bot_metrics:SELECT' 'REVOKE SELECT ON salon.bot_metrics FROM salon_app;'
table_stage T3 'conversations:INSERT conversations:UPDATE' 'REVOKE INSERT, UPDATE ON salon.conversations FROM salon_app;'
echo "m7-window: all four stages done."
