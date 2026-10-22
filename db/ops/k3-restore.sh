#!/usr/bin/env bash
# K-3 restore and proof (MIGRATION-PLAN §3r). OPERATOR SCRIPT: run as root after k3-window.sh (or after any
# interruption). It re-grants salon_app's full table privileges, checks the catalog, and then PROVES the grant
# by behaviour: it connects AS salon_app over TCP and SELECTs from all five tables. Exits non-zero on any miss.
# The grant and the catalog count run after `SET ROLE salon_owner`: salon_migrator itself has no USAGE on schema
# salon (002_roles.sql, INHERIT FALSE), so without it even resolving 'salon.<table>' is denied (root output,
# operator ran it 2026-10-22: k3-window.sh's catalog check, which resolves 'salon.<table>' the same way, was
# refused). The proof read runs as salon_app, which has USAGE.
# Secrets reach psql only by environment inheritance; nothing but counts of checks is printed.
set -euo pipefail
ENV=/root/n8n/postgres-roles.env
[ "$(id -u)" = 0 ] || { echo "k3-restore: run as root"; exit 2; }
[ -r "$ENV" ] || { echo "k3-restore: $ENV not readable"; exit 2; }
set -a; . "$ENV"; set +a
[ -n "${SALON_MIGRATOR_PASSWORD:-}" ] && [ -n "${SALON_APP_PASSWORD:-}" ] || { echo "k3-restore: a password is missing from $ENV"; exit 2; }
as() {   # as <role> <password>, SQL on stdin
  PGPASSWORD="$2" docker compose --project-directory /root/n8n exec -T -e PGPASSWORD postgres \
    psql -X -At -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$1" -d salon -f -
}
owner() {   # SQL on stdin, as salon_migrator after SET ROLE salon_owner
  { printf 'SET ROLE salon_owner;\n'; cat; } | as salon_migrator "$SALON_MIGRATOR_PASSWORD"
}
printf 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA salon TO salon_app;\n' | owner \
  || { echo "k3-restore: the GRANT failed (psql error above) — NOT restored"; exit 1; }
granted="$(owner <<'SQL'
SELECT count(*) FILTER (WHERE has_table_privilege('salon_app', 'salon.' || t, p)) || '/' || count(*)
  FROM unnest(ARRAY['appointments','bot_metrics','conversations','leads','processed_messages']) t,
       unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE']) p;
SQL
)" || granted='no answer (psql error above)'
[ "$granted" = "20/20" ] || { echo "k3-restore: the catalog check gave $granted, not 20/20 — NOT restored"; exit 1; }
reads="$(as salon_app "$SALON_APP_PASSWORD" <<'SQL'
SELECT (SELECT 1 FROM (SELECT count(*) FROM salon.conversations) a) + (SELECT 1 FROM (SELECT count(*) FROM salon.appointments) b)
     + (SELECT 1 FROM (SELECT count(*) FROM salon.leads) c) + (SELECT 1 FROM (SELECT count(*) FROM salon.processed_messages) d)
     + (SELECT 1 FROM (SELECT count(*) FROM salon.bot_metrics) e);
SQL
)" || reads='?'
[ "$reads" = "5" ] || { echo "k3-restore: salon_app could not SELECT from every table"; exit 1; }
echo "k3-restore: OK — catalog 20/20 privileges · salon_app SELECT works on all 5 tables"
