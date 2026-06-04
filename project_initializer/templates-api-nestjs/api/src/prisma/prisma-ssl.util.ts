/**
 * Derives the node-postgres `ssl` option for the Prisma pg adapter from the
 * DATABASE_URL host.
 *
 * `@prisma/adapter-pg` (node-postgres) ignores `sslmode=require` in the
 * connection string, so TLS must be passed in code. The Supabase pooler
 * presents a certificate that does not validate against the default CA chain,
 * hence `rejectUnauthorized: false`. The local Docker `postgres:16` image has
 * no TLS, so its connection must stay plaintext (`undefined`).
 */

export type PgSslOption = { rejectUnauthorized: boolean } | undefined;

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

/**
 * Returns the `ssl` option for `PrismaPg`: `undefined` (plaintext) for local
 * hosts or an unparseable/empty URL, TLS otherwise.
 */
export function deriveSslOption(databaseUrl: string | undefined): PgSslOption {
  const host = extractHost(databaseUrl);
  if (host === null || LOCAL_HOSTS.has(host)) {
    return undefined;
  }
  return { rejectUnauthorized: false };
}

function extractHost(databaseUrl: string | undefined): string | null {
  if (!databaseUrl) {
    return null;
  }
  try {
    return new URL(databaseUrl).hostname;
  } catch {
    return null;
  }
}
