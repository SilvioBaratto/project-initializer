/**
 * Derives the node-postgres `ssl` option for the Prisma pg adapter from the
 * DATABASE_URL.
 *
 * `@prisma/adapter-pg` (node-postgres) ignores `sslmode` in the connection
 * string, so TLS must be passed in code. Two signals decide it:
 *
 * 1. An explicit `sslmode` wins — it is the standard way to state intent, and
 *    the escape hatch when the host heuristic below guesses wrong. The Supabase
 *    pooler presents a certificate that does not validate against the default CA
 *    chain, hence `rejectUnauthorized: false` rather than plain `true`.
 * 2. Otherwise the host decides: loopback and single-label hostnames are
 *    container/LAN hosts and stay plaintext; a public DNS name gets TLS.
 *
 * The single-label rule is what makes Docker work. Compose points the API at
 * `postgresql://...@db:5432/...` with no `sslmode`, and the `postgres:16-alpine`
 * image serves no TLS at all, so connecting with TLS fails outright:
 * "Error opening a TLS connection: The server does not support SSL connections".
 * A bare `db` is never a public DNS name, so it is treated like localhost.
 */

export type PgSslOption = { rejectUnauthorized: boolean } | undefined;

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

/**
 * `sslmode` values that demand TLS. `prefer`/`allow` mean "try TLS, fall back",
 * which node-postgres cannot express, so they defer to the host heuristic.
 */
const TLS_REQUIRED_SSLMODES = new Set(['require', 'verify-ca', 'verify-full']);

/**
 * Returns the `ssl` option for `PrismaPg`: `undefined` (plaintext) for local,
 * containerised, or `sslmode=disable` targets; TLS otherwise.
 */
export function deriveSslOption(databaseUrl: string | undefined): PgSslOption {
  const url = parseUrl(databaseUrl);
  if (url === null) {
    return undefined;
  }

  const sslmode = url.searchParams.get('sslmode');
  if (sslmode === 'disable') {
    return undefined;
  }
  if (sslmode !== null && TLS_REQUIRED_SSLMODES.has(sslmode)) {
    return { rejectUnauthorized: false };
  }

  return isLocalOrContainerHost(url.hostname) ? undefined : { rejectUnauthorized: false };
}

/** True for loopback and for hosts that cannot be public DNS names. */
function isLocalOrContainerHost(host: string): boolean {
  if (LOCAL_HOSTS.has(host)) {
    return true;
  }
  // A bracketed IPv6 literal that is not the loopback is a real address; only
  // the LOCAL_HOSTS check above may treat one as local.
  if (host.startsWith('[')) {
    return false;
  }
  // Single-label hostnames ("db", "postgres") are Docker/compose service names
  // or LAN hosts, never public DNS, so they stay plaintext by default.
  return !host.includes('.');
}

function parseUrl(databaseUrl: string | undefined): URL | null {
  if (!databaseUrl) {
    return null;
  }
  try {
    return new URL(databaseUrl);
  } catch {
    return null;
  }
}
