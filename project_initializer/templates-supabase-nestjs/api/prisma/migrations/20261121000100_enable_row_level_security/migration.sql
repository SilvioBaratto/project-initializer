-- Row-level security is enabled with no policies on purpose: the Supabase Data API roles
-- (anon, authenticated) are denied every row, while the API connects as the table owner, which
-- bypasses row-level security. "_prisma_migrations" sits in "public" like the app tables, so it
-- needs the same protection from the Data API.
ALTER TABLE "profiles" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "items" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "_prisma_migrations" ENABLE ROW LEVEL SECURITY;
