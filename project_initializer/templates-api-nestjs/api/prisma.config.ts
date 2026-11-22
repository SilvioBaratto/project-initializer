// The project .env lives at the repo root (one level above api/). Load it first,
// then a local api/.env fallback, so `npx prisma ...` run from api/ resolves
// DATABASE_URL/DIRECT_URL. In Docker these arrive as real env vars (compose
// env_file) and the missing files are simply skipped. dotenv writes an "injected env" line to
// stderr on every load unless `quiet: true` is passed, which keeps prisma commands quiet.
import { config } from "dotenv";
config({ path: ["../.env", ".env"], quiet: true });
import { defineConfig } from "prisma/config";

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
  },
  datasource: {
    url: process.env["DATABASE_URL"],
    directUrl: process.env["DIRECT_URL"],
  },
});
