-- 002_roles.sql — least-privilege roles for the bot's store (docs/MIGRATION-PLAN.md §3g, ruling Q6).
--
-- Applied ONCE, after 001_init.sql and in the SAME transaction (the runner adds BEGIN and then ROLLBACK
-- for the dry run or COMMIT for real; see 001), by the operator, as the bootstrap superuser, inside the
-- Postgres container, with both files on STDIN.
--
-- WHERE THE PASSWORDS COME FROM, AND WHERE THEY NEVER APPEAR:
-- · NOT in this file (no literal), and NOT on any command line: a process's argv is readable by every local
--   account on this host (OPS-6), including argv inside a container.
-- · They live in a root-only roles file that is NEVER given to the container as an env_file (so they are
--   not in the container's lasting environment, where `docker inspect` would show them). The operator's
--   root shell loads that file and runs `docker compose exec -e SALON_APP_PASSWORD …`: with `-e NAME` and
--   no value, only the NAME is on the command line, and the value goes from the caller's environment to
--   this one psql process. psql reads it here with \getenv. It exists in psql's memory and in the CREATE
--   ROLE statement on its connection, and nowhere else, and the psql process ends with the script.
-- · Echo and error text are kept terse, and this session raises log_min_error_statement, because a FAILED
--   CREATE ROLE would otherwise be written, password included, to the server log by default.
--
-- Roles:
--   salon_owner    NOLOGIN — owns the schema and every object in it (DDL lives here)
--   salon_migrator LOGIN   — member of salon_owner; applies future migrations with SET ROLE salon_owner
--   salon_app      LOGIN   — the n8n credential: DML on the five tables, nothing else
--   salon_ro       LOGIN   — the dashboard and Claude's verification: SELECT only
-- Claude holds ONLY salon_ro (ruling Q6). Each role's limits are proven by NEGATIVE tests in D2b-3.

\set ON_ERROR_STOP on
\set ECHO none
\set VERBOSITY terse
\set SHOW_CONTEXT never
SET log_min_error_statement = PANIC;
SET log_statement = 'none';
SET log_min_duration_statement = -1;       -- none of the duration/sample loggers may capture CREATE ROLE
SET log_min_duration_sample = -1;
SET log_transaction_sample_rate = 0;

\getenv migrator_pw SALON_MIGRATOR_PASSWORD
\getenv app_pw      SALON_APP_PASSWORD
\getenv ro_pw       SALON_RO_PASSWORD

-- A missing or short password stops the script with a real error (ON_ERROR_STOP), never a quiet \echo.
\if :{?migrator_pw}
\else
  \echo 'SALON_MIGRATOR_PASSWORD is not in the environment'
  SELECT 'abort'::int;
\endif
\if :{?app_pw}
\else
  \echo 'SALON_APP_PASSWORD is not in the environment'
  SELECT 'abort'::int;
\endif
\if :{?ro_pw}
\else
  \echo 'SALON_RO_PASSWORD is not in the environment'
  SELECT 'abort'::int;
\endif
SELECT (length(:'migrator_pw') >= 24 AND length(:'app_pw') >= 24 AND length(:'ro_pw') >= 24
        AND :'migrator_pw' <> :'app_pw' AND :'app_pw' <> :'ro_pw' AND :'migrator_pw' <> :'ro_pw') AS pw_ok \gset
\if :pw_ok
\else
  \echo 'a password is shorter than 24 characters, or two roles share one'
  SELECT 'abort'::int;
\endif

CREATE ROLE salon_owner NOLOGIN;
CREATE ROLE salon_migrator LOGIN PASSWORD :'migrator_pw';
-- INHERIT FALSE: the migrator must SET ROLE salon_owner to do DDL. With inheritance (the PG16+ default for
-- a grant), DDL run without SET ROLE would create objects owned by the MIGRATOR, outside the default
-- privileges below, so the app and ro roles would silently lack access to them.
GRANT salon_owner TO salon_migrator WITH INHERIT FALSE, SET TRUE;
CREATE ROLE salon_app      LOGIN PASSWORD :'app_pw';
CREATE ROLE salon_ro       LOGIN PASSWORD :'ro_pw';

-- Ownership: everything 001 created moves to salon_owner (identity sequences follow their table).
ALTER SCHEMA salon OWNER TO salon_owner;
ALTER TABLE salon.conversations      OWNER TO salon_owner;
ALTER TABLE salon.appointments       OWNER TO salon_owner;
ALTER TABLE salon.leads              OWNER TO salon_owner;
ALTER TABLE salon.processed_messages OWNER TO salon_owner;
ALTER TABLE salon.bot_metrics        OWNER TO salon_owner;
ALTER FUNCTION salon.gen_rec_id()          OWNER TO salon_owner;
ALTER FUNCTION salon.at_ts(timestamptz)    OWNER TO salon_owner;

-- Nobody gets anything by default.
REVOKE ALL ON DATABASE salon FROM PUBLIC;           -- includes CONNECT and TEMPORARY
-- The other two databases keep PUBLIC's default CONNECT + TEMPORARY otherwise: app/ro could open TEMP
-- tables there. Only the superuser needs them.
REVOKE CONNECT, TEMPORARY ON DATABASE postgres, template1 FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA salon FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA salon FROM PUBLIC;

GRANT CONNECT ON DATABASE salon TO salon_migrator, salon_app, salon_ro;
GRANT USAGE ON SCHEMA salon TO salon_app, salon_ro;

-- salon_app: DML only. No CREATE on any schema, not the owner of anything, so no DDL, DROP, ALTER or
-- TRUNCATE (TRUNCATE is a separate privilege and is not granted).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA salon TO salon_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA salon TO salon_app;
GRANT EXECUTE ON FUNCTION salon.gen_rec_id(), salon.at_ts(timestamptz) TO salon_app;  -- DEFAULT runs as the inserter

-- salon_ro: SELECT only.
GRANT SELECT ON ALL TABLES IN SCHEMA salon TO salon_ro;
GRANT EXECUTE ON FUNCTION salon.at_ts(timestamptz) TO salon_ro;

-- Objects a later migration creates (as salon_owner) inherit the same split.
ALTER DEFAULT PRIVILEGES FOR ROLE salon_owner IN SCHEMA salon GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO salon_app;
ALTER DEFAULT PRIVILEGES FOR ROLE salon_owner IN SCHEMA salon GRANT USAGE, SELECT ON SEQUENCES TO salon_app;
ALTER DEFAULT PRIVILEGES FOR ROLE salon_owner IN SCHEMA salon GRANT SELECT ON TABLES TO salon_ro;
-- Functions: the PUBLIC EXECUTE default is GLOBAL, and a schema-scoped default can only ADD to it, never
-- take it away, so this revoke must be global (no IN SCHEMA). Otherwise every function a later migration
-- creates would be born executable by everyone, a SECURITY DEFINER one included.
ALTER DEFAULT PRIVILEGES FOR ROLE salon_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

ALTER ROLE salon_migrator SET search_path = salon;
ALTER ROLE salon_app      SET search_path = salon;
ALTER ROLE salon_ro       SET search_path = salon;

-- Forget the values in this psql session before it ends.
\unset migrator_pw
\unset app_pw
\unset ro_pw
\echo '002_roles: statements accepted (the runner decides COMMIT or ROLLBACK)'
