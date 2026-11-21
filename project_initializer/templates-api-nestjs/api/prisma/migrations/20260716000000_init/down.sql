-- Rolls back 20260716000000_init without losing data: "users" is copied into
-- migration_backup."users__rollback_<UTC timestamp>" first. The suffix has microsecond
-- resolution, so back-to-back rollback and redeploy cycles never collide. The copy carries rows
-- only, no constraints or indexes. Restore with
--   INSERT INTO "users" SELECT * FROM migration_backup."users__rollback_<timestamp>"
-- The backup lives outside "public" on purpose: a backup table there is served by the Supabase
-- Data API, whose publishable key ships in the browser, and would expose personal data. Prisma
-- inspects only the schema named in the datasource, so `prisma migrate diff` ignores the backup.
-- Drop the backup tables once the restore is verified.
-- Apply, newest migration first:
--   npx prisma db execute --file prisma/migrations/20260716000000_init/down.sql
-- The DELETE un-records the migration: `prisma migrate resolve --rolled-back` rejects one that
-- finished successfully (P3012), and once un-recorded `prisma migrate deploy` applies it again.
CREATE SCHEMA IF NOT EXISTS migration_backup;
REVOKE ALL ON SCHEMA migration_backup FROM PUBLIC;
DO $$
DECLARE
  backup_table text := format(
    'users__rollback_%s',
    to_char(clock_timestamp() AT TIME ZONE 'utc', 'YYYYMMDDHH24MISSUS')
  );
BEGIN
  EXECUTE format('CREATE TABLE migration_backup.%I AS SELECT * FROM "users"', backup_table);
  DROP INDEX "users_email_key";
  DROP TABLE "users";
END
$$;
DELETE FROM "_prisma_migrations" WHERE "migration_name" = '20260716000000_init';
