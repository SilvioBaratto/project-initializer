-- Rolls back 20261121000100_enable_row_level_security. Switching row-level security off
-- touches no rows, so nothing needs a backup.
-- Apply, newest migration first:
--   npx prisma db execute --file prisma/migrations/20261121000100_enable_row_level_security/down.sql
-- The DELETE un-records the migration: `prisma migrate resolve --rolled-back` rejects one that
-- finished successfully (P3012), and once un-recorded `prisma migrate deploy` applies it again.
ALTER TABLE "_prisma_migrations" DISABLE ROW LEVEL SECURITY;
ALTER TABLE "items" DISABLE ROW LEVEL SECURITY;
ALTER TABLE "profiles" DISABLE ROW LEVEL SECURITY;
DELETE FROM "_prisma_migrations" WHERE "migration_name" = '20261121000100_enable_row_level_security';
