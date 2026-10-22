#!/usr/bin/env bash
# K-3 error-path window (MIGRATION-PLAN §3r). OPERATOR SCRIPT: run as root, ONCE, on the server.
#
# It takes salon_app's table privileges away in four declared stages, so the inactive migration copies
# (D3a Drill State, D3b Owner Actions, D3d Purge) can have their error paths drilled against a REAL store
# failure. The live originals run on Airtable, so no production path uses salon_app: only the copies notice.
#
#   W1  UPDATE on conversations, DELETE on processed_messages and leads   (reads work, writes fail)
#   R1  SELECT on processed_messages and leads
#   R2  SELECT on conversations
#   W2  INSERT and UPDATE on processed_messages                           (the owner marker cannot be written)
#
# Every stage first restores salon_app's full grant and then revokes its own set, inside ONE transaction, and
# then checks the catalog: if salon_app is missing anything other than exactly that set, it aborts.
# Between stages it waits for Claude's flag file (no stage advances by itself). Whatever happens (end,
# error, timeout, Ctrl-C), the EXIT trap restores the full grant and prints what salon_app lacks: "-" = nothing.
# Secrets: the migrator password reaches psql only by environment inheritance (PGPASSWORD + `exec -e NAME`,
# which puts the NAME on the command line, never the value). Nothing is printed but stage names and privileges.
set -euo pipefail
ENV=/root/n8n/postgres-roles.env
FLAGS=/home/yigit/k3-flags
WAIT_START=3600   # seconds to wait for Claude's "go"
WAIT_STAGE=1200   # seconds per stage before giving up (the trap still restores)

[ "$(id -u)" = 0 ] || { echo "k3-window: run as root"; exit 2; }
[ -r "$ENV" ] || { echo "k3-window: $ENV not readable"; exit 2; }
set -a; . "$ENV"; set +a
[ -n "${SALON_MIGRATOR_PASSWORD:-}" ] || { echo "k3-window: SALON_MIGRATOR_PASSWORD missing from $ENV"; exit 2; }

q() {   # SQL on stdin, as salon_migrator over TCP (the socket is trust; TCP checks the password)
  PGPASSWORD="$SALON_MIGRATOR_PASSWORD" docker compose --project-directory /root/n8n exec -T -e PGPASSWORD postgres \
    psql -X -At -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -U salon_migrator -d salon -f -
}
BASE='GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA salon TO salon_app;'
MISSING="SELECT coalesce(string_agg(t || ':' || p, ' ' ORDER BY t, p), '-')
           FROM unnest(ARRAY['appointments','bot_metrics','conversations','leads','processed_messages']) t,
                unnest(ARRAY['DELETE','INSERT','SELECT','UPDATE']) p
          WHERE NOT has_table_privilege('salon_app', 'salon.' || t, p);"

restore() {
  local rc=$?
  printf 'SET ROLE salon_owner;\n%s\n' "$BASE" | q
  echo "k3-window: RESTORED. salon_app lacks: $(printf '%s\n' "$MISSING" | q)   (\"-\" = nothing)"
  exit "$rc"
}

wait_for() {   # wait_for <flag> <seconds>
  local i=0
  while [ ! -e "$FLAGS/$1" ]; do
    i=$((i + 5)); [ "$i" -le "$2" ] || { echo "k3-window: no '$1' from Claude within $2 s — stopping"; exit 1; }
    sleep 5
  done
}

stage() {   # stage <name> <expected missing set> <REVOKE statements>
  printf 'SET ROLE salon_owner;\nBEGIN;\n%s\n%s\nCOMMIT;\n' "$BASE" "$3" | q
  local got; got="$(printf '%s\n' "$MISSING" | q)"
  [ "$got" = "$2" ] || { echo "k3-window: stage $1 left salon_app lacking '$got', expected '$2' — aborting"; exit 1; }
  echo "k3-window: stage $1 applied · salon_app lacks: $got · waiting for Claude ($1.done)"
  wait_for "$1.done" "$WAIT_STAGE"
}

[ "$(printf '%s\n' "$MISSING" | q)" = "-" ] || { echo "k3-window: salon_app is not at its full grant before the window — not starting"; exit 1; }
trap restore EXIT
echo "k3-window: baseline OK (salon_app has its full grant). Waiting for Claude's go ($FLAGS/go)."
wait_for go "$WAIT_START"
stage W1 'conversations:UPDATE leads:DELETE processed_messages:DELETE' \
  'REVOKE UPDATE ON salon.conversations FROM salon_app; REVOKE DELETE ON salon.processed_messages, salon.leads FROM salon_app;'
stage R1 'leads:SELECT processed_messages:SELECT' \
  'REVOKE SELECT ON salon.processed_messages, salon.leads FROM salon_app;'
stage R2 'conversations:SELECT' \
  'REVOKE SELECT ON salon.conversations FROM salon_app;'
stage W2 'processed_messages:INSERT processed_messages:UPDATE' \
  'REVOKE INSERT, UPDATE ON salon.processed_messages FROM salon_app;'
echo "k3-window: all four stages done."
