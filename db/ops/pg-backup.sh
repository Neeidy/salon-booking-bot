#!/usr/bin/env bash
# pg-backup.sh — the nightly Postgres backup, and the proof that it restores (MIGRATION-PLAN §3j, §3t, D6a).
#
#   bash pg-backup.sh                 dump + verify + retention           (the nightly job calls this)
#   bash pg-backup.sh --verify FILE   verify an existing dump: checksum, TOC, full restore, per-table stats
#
# Runs as the nightly job's (non-root) user, which must be able to run docker; never as root.
#
# WHAT A DUMP MUST SURVIVE BEFORE IT COUNTS (a dump that has never been restored proves nothing — §3j):
#   1. it is written from ONE consistent snapshot, and the per-table row counts and ordered md5s are read IN THAT
#      SAME SNAPSHOT (pg_export_snapshot + pg_dump --snapshot). Comparing a restore against the live database read
#      at another moment would raise a false alarm whenever a row was written in between (Reminders run hourly).
#   2. its sha256 is recorded beside it, and checked before every restore (a flipped byte is caught here);
#   3. `pg_restore --list` shows the five tables' data;
#   4. it restores, whole, into a THROWAWAY container (decision 3): the running container's own image, no network,
#      its own anonymous volume, removed on exit. The live cluster never runs a CREATE DATABASE for this;
#   5. the restored per-table counts and ordered md5s equal the ones recorded at dump time.
# Any failure prints one line naming the step and exits non-zero, so the nightly log shows it (CLAUDE.md: failures
# are visible). The dump, its .sha256 and its .stats are mode 600; files older than KEEP_DAYS are removed.
#
# NO SECRET ANYWHERE, IN ARGV OR ELSEWHERE: the dump is taken by the `postgres` role over the container's own local
# socket (the path M7's --check proved works without a password), and the throwaway accepts local connections
# without a password because it has no network at all. No password is read, set or passed.
set -euo pipefail

BK="${PG_BACKUP_DIR:-$HOME/backups}"
KEEP_DAYS="${PG_BACKUP_KEEP_DAYS:-14}"
DB=salon
TABLES=(appointments bot_metrics conversations leads processed_messages)

# To stderr: die also runs inside command substitutions (`ct="$(container)"`), where a stdout line would be captured
# into the variable and the failure would reach the log with no reason (the offline test caught exactly that).
die() { echo "pg-backup: FAILED at $1" >&2; exit 1; }

# The per-table statistics, one line each: "<table> <rows> <md5 of the rows in id order>". The same text runs in the
# source snapshot and in the restored copy; row text is compared within one Postgres image, so it is stable.
stats_sql() {
  local t first=1
  printf 'SELECT s FROM ('
  for t in "${TABLES[@]}"; do
    [ $first = 1 ] || printf ' UNION ALL '
    first=0
    printf "SELECT '%s' || ' ' || count(*) || ' ' || coalesce(md5(string_agg(x::text, E'\\\\n' ORDER BY x.id)), '-') FROM salon.%s x" "$t" "$t"
  done
  printf ') u(s) ORDER BY s;\n'   # UNION ALL does not promise an order; every line starts with its table name
}

container() {   # the running Postgres container: PG_CONTAINER, else the ONE container compose labels as service "postgres"
  if [ -n "${PG_CONTAINER:-}" ]; then echo "$PG_CONTAINER"; return; fi
  local found n
  found="$(docker ps --filter label=com.docker.compose.service=postgres --format '{{.Names}}')" || die "listing containers"
  n="$(printf '%s' "$found" | grep -c . || true)"
  [ "$n" = 1 ] || die "finding the Postgres container: $n candidates (set PG_CONTAINER)"
  echo "$found"
}

verify() {   # verify <dump file>
  local f="$1" ct img r stats
  [ -s "$f" ] || die "verify: $f is missing or empty"
  [ -s "$f.sha256" ] && [ -s "$f.stats" ] || die "verify: $f has no .sha256 or .stats beside it"
  (cd "$(dirname "$f")" && sha256sum --quiet -c "$(basename "$f").sha256") >/dev/null 2>&1 || die "verify: checksum (the file changed since it was written)"
  ct="$(container)"
  local listed
  listed="$(docker exec -i "$ct" pg_restore --list < "$f" 2>/dev/null | grep -c " TABLE DATA salon " || true)"
  [ "$listed" = "${#TABLES[@]}" ] || die "verify: the dump's table of contents lists $listed of ${#TABLES[@]} tables' data"
  img="$(docker inspect -f '{{.Image}}' "$ct")" || die "verify: reading the running image"
  r="pg-backup-restore-$$"
  # shellcheck disable=SC2064  # the name is fixed now, on purpose
  trap "docker rm -f '$r' >/dev/null 2>&1 || true" EXIT
  docker run -d --rm --network none --name "$r" -e POSTGRES_HOST_AUTH_METHOD=trust "$img" >/dev/null || die "verify: starting the throwaway"
  local i=0
  # TCP, not the socket: the image's first-start server listens on the socket only and then restarts, so a socket
  # "ready" can arrive just before that restart. The final server is the only one listening on 127.0.0.1.
  until docker exec "$r" pg_isready -h 127.0.0.1 -U postgres -q >/dev/null 2>&1; do
    i=$((i + 1)); [ "$i" -le 60 ] || die "verify: the throwaway did not become ready"
    sleep 1
  done
  docker exec "$r" createdb -U postgres "$DB" || die "verify: creating the scratch database in the throwaway"
  docker exec -i "$r" pg_restore -U postgres -d "$DB" --no-owner --no-privileges --exit-on-error < "$f" \
    || die "verify: pg_restore into the throwaway"
  stats="$(stats_sql | docker exec -i "$r" psql -X -At -q -v ON_ERROR_STOP=1 -U postgres -d "$DB")" || die "verify: reading the restored stats"
  [ "$stats" = "$(cat "$f.stats")" ] || die "verify: the restored rows differ from the dump-time stats"
  docker rm -f "$r" >/dev/null 2>&1 || true
  trap - EXIT
  echo "pg-backup: verify OK — checksum, ${#TABLES[@]} tables in the TOC, full restore into a throwaway, stats equal ($(awk '{s += $2} END {print s + 0}' "$f.stats") rows)"
}

dump() {
  local ct ts out snap stats
  mkdir -p "$BK" && chmod 700 "$BK"
  exec 8>"$BK/.pg-backup.lock"
  flock -n 8 || die "lock (another pg-backup is running)"
  ct="$(container)"
  ts="$(date +%Y%m%d-%H%M%S)"
  out="$BK/salon-pg-$ts.dump"
  umask 077
  # One REPEATABLE READ session holds the snapshot open while pg_dump uses it, and then reads the stats in it.
  coproc PSQL { docker exec -i "$ct" psql -X -At -q -v ON_ERROR_STOP=1 -U postgres -d "$DB"; }
  printf 'BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\nSELECT pg_export_snapshot();\n' >&"${PSQL[1]}"
  IFS= read -r -t 30 snap <&"${PSQL[0]}" || die "dump: exporting a snapshot"
  [[ $snap =~ ^[0-9A-F-]+$ ]] || die "dump: the snapshot id is not one"
  docker exec "$ct" pg_dump -U postgres -Fc --snapshot="$snap" "$DB" > "$out.part" || die "dump: pg_dump"
  stats_sql >&"${PSQL[1]}"
  stats=""
  local line k
  for k in "${TABLES[@]}"; do
    IFS= read -r -t 30 line <&"${PSQL[0]}" || die "dump: reading the snapshot stats"
    stats+="$line"$'\n'
  done
  printf 'COMMIT;\n\\q\n' >&"${PSQL[1]}"
  exec {PSQL[1]}>&-
  wait "$PSQL_PID" 2>/dev/null || true
  [ -s "$out.part" ] || die "dump: the dump is empty"
  mv "$out.part" "$out"
  printf '%s' "$stats" > "$out.stats"
  (cd "$BK" && sha256sum "$(basename "$out")" > "$(basename "$out").sha256")
  chmod 600 "$out" "$out.stats" "$out.sha256"
  echo "pg-backup: dump written ($(du -h "$out" | cut -f1)) from one snapshot"
  verify "$out"
  find "$BK" -maxdepth 1 -type f \( -name 'salon-pg-*.dump' -o -name 'salon-pg-*.dump.sha256' -o -name 'salon-pg-*.dump.stats' \) \
    -mtime +"$KEEP_DAYS" -print -delete
}

case "${1:-}" in
  '') dump ;;
  --verify) [ -n "${2:-}" ] || { echo "usage: pg-backup.sh --verify FILE"; exit 2; }; verify "$2" ;;
  *) echo "usage: pg-backup.sh [--verify FILE]"; exit 2 ;;
esac
