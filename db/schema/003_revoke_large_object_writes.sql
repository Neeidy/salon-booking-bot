-- 003_revoke_large_object_writes.sql — close the large-object write path that PUBLIC holds by default
-- (docs/MIGRATION-PLAN.md §3t, Round 3b; Codex CRT #10 finding F1; ruling 2026-10-24).
--
-- WHY: `salon_ro` holds SELECT only on the five tables (002_roles.sql), yet it could CREATE a persistent large
-- object. PostgreSQL grants EXECUTE on the large-object functions to PUBLIC, and with lo_compat_privileges off
-- the creator owns the new object and may write it. Measured on the live cluster as salon_ro, 2026-10-24,
-- read-only: EXECUTE true for salon_ro AND salon_app on every function below; zero large objects exist.
-- The dashboard's runtime check (WRITE_CHECK in web/dashboard/lib/store.ts) asks TABLE privileges only, so it
-- could not see this; the path is closed here, at the database, not in that module.
--
-- WHAT: EXECUTE is revoked from PUBLIC on the functions that create, write, truncate or delete a large object.
-- Reading functions (lo_open, loread, lo_get, lo_lseek*, lo_tell*, lo_close) are left alone: they reach only
-- objects the caller may already SELECT, and none exist. lo_import/lo_export (server files) are already
-- superuser-only in this release and are not touched. lo_unlink is included: deleting is a write.
-- No workflow uses any of these: a grep of all ten n8n exports, the five copy specs and the schema files finds
-- none (Round 3b record).
--
-- SCOPE: function privileges live in each database's own catalog, so this changes database `salon` only.
-- The superuser is unaffected (it bypasses privilege checks).
--
-- HOW: applied once by the operator, as the bootstrap superuser, inside the Postgres container, on STDIN,
-- connected to database `salon`; first as a dry run (this file with its final COMMIT turned into ROLLBACK), then
-- for real. It is idempotent (a second run revokes nothing new and passes the check).
-- Undo, if ever needed: GRANT EXECUTE ON FUNCTION <the same list> TO PUBLIC.
--
-- ⚠ RESTORE: db/ops/pg-backup.sh restores with --no-privileges, so a database rebuilt from a dump does NOT
-- carry this revoke (nor 002's grants). After a real restore, re-apply 002 and then this file.

\set ON_ERROR_STOP on
\set VERBOSITY terse

BEGIN;

DO $$
BEGIN
  IF current_database() <> 'salon' THEN
    RAISE EXCEPTION '003: connected to database %, not salon — nothing changed', current_database();
  END IF;
END $$;

REVOKE EXECUTE ON FUNCTION
  pg_catalog.lo_create(oid),
  pg_catalog.lo_creat(integer),
  pg_catalog.lo_from_bytea(oid, bytea),
  pg_catalog.lo_put(oid, bigint, bytea),
  pg_catalog.lowrite(integer, bytea),
  pg_catalog.lo_truncate(integer, integer),
  pg_catalog.lo_truncate64(integer, bigint),
  pg_catalog.lo_unlink(oid)
FROM PUBLIC;

-- The check runs inside the same transaction: if any of the three can still execute one of them (a direct
-- grant to a role survives a revoke from PUBLIC), the whole file rolls back and says which.
DO $$
DECLARE
  f text;
  r text;
BEGIN
  FOREACH f IN ARRAY ARRAY['pg_catalog.lo_create(oid)', 'pg_catalog.lo_creat(integer)',
                           'pg_catalog.lo_from_bytea(oid, bytea)', 'pg_catalog.lo_put(oid, bigint, bytea)',
                           'pg_catalog.lowrite(integer, bytea)', 'pg_catalog.lo_truncate(integer, integer)',
                           'pg_catalog.lo_truncate64(integer, bigint)', 'pg_catalog.lo_unlink(oid)'] LOOP
    FOREACH r IN ARRAY ARRAY['public', 'salon_app', 'salon_ro'] LOOP
      IF has_function_privilege(r, f, 'EXECUTE') THEN
        RAISE EXCEPTION '003: % can still execute % — rolled back', r, f;
      END IF;
    END LOOP;
  END LOOP;
END $$;

-- psql prints the transaction's outcome on the next line (COMMIT; ROLLBACK in the operator's dry run).
\echo '003_revoke_large_object_writes: revoke applied and checked inside the transaction'
COMMIT;
