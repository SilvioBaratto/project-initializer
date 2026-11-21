/** The `ssl` option node-postgres accepts: `undefined` keeps the connection in plaintext. */
export type PgSslOption = { rejectUnauthorized: boolean } | undefined;

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

/**
 * `sslmode` values that encrypt and validate the server certificate against Node's CA bundle, so
 * a private CA needs `NODE_EXTRA_CA_CERTS`. Node's TLS stack also checks the hostname, which makes
 * `verify-ca` as strict as `verify-full` here; libpq skips that check for `verify-ca`.
 */
const CERTIFICATE_VERIFYING_SSLMODES = new Set(['verify-ca', 'verify-full']);

/**
 * `require` encrypts and accepts any certificate. The Supabase pooler presents a certificate that
 * does not validate against the default CA chain, so this is also what keeps it reachable.
 */
const ENCRYPT_ONLY_SSLMODE = 'require';
const SSLMODE_DISABLE = 'disable';

/**
 * Connection-string parameters that node-postgres turns into its own `ssl` object, and that then
 * replace the `ssl` option passed in code. `pg-connection-string` maps `sslmode=require` (and
 * `prefer`, `verify-ca`) to full certificate verification and prints a security warning for it,
 * which is not what {@link deriveSslOption} decides.
 */
const SSL_URL_PARAMETERS = [
  'sslmode',
  'sslrootcert',
  'sslcert',
  'sslkey',
  'uselibpqcompat',
] as const;

/**
 * Derives the node-postgres `ssl` option for the Prisma pg adapter from the DATABASE_URL.
 *
 * `@prisma/adapter-pg` hands the URL to node-postgres, whose own reading of `sslmode` differs from
 * libpq's, so the decision is made here and {@link stripSslParameters} removes the parameters
 * from the string that reaches the pool. Two signals decide it:
 *
 * 1. An explicit `sslmode` wins, because it is the standard way to state intent and the escape
 *    hatch when the host heuristic below guesses wrong: `disable` keeps plaintext, `require`
 *    encrypts without verifying the certificate, `verify-ca` and `verify-full` encrypt and verify
 *    it (chain and hostname). `prefer` and `allow` mean "try TLS, fall back", which node-postgres
 *    cannot express, so they defer to the host heuristic.
 * 2. Otherwise the host decides: loopback and single-label hostnames are container or LAN hosts
 *    and stay plaintext; a public DNS name gets encrypted, unverified TLS.
 *
 * The single-label rule is what makes Docker work. Compose points the API at
 * `postgresql://...@db:5432/...` with no `sslmode`, and the `postgres:16-alpine` image serves no
 * TLS at all, so connecting with TLS fails outright: "The server does not support SSL
 * connections". A bare `db` is never a public DNS name, so it is treated like localhost.
 *
 * @param databaseUrl - the connection string; a missing or unparsable value yields `undefined`.
 * @returns the `ssl` option for `PoolConfig`, `undefined` for plaintext targets.
 */
export function deriveSslOption(databaseUrl: string | undefined): PgSslOption {
  const url = parseUrl(databaseUrl);
  if (url === null) {
    return undefined;
  }
  const sslmode = url.searchParams.get('sslmode');
  if (sslmode === SSLMODE_DISABLE) {
    return undefined;
  }
  if (sslmode !== null && CERTIFICATE_VERIFYING_SSLMODES.has(sslmode)) {
    return { rejectUnauthorized: true };
  }
  if (sslmode === ENCRYPT_ONLY_SSLMODE) {
    return { rejectUnauthorized: false };
  }
  return isLocalOrContainerHost(url.hostname) ? undefined : { rejectUnauthorized: false };
}

/**
 * Removes the TLS parameters that node-postgres would turn into an `ssl` object of its own.
 *
 * node-postgres merges what it parses from the connection string over the options given in code,
 * so leaving them in would silently discard the result of {@link deriveSslOption}. Certificate
 * files named in the URL (`sslrootcert`, `sslcert`, `sslkey`) are dropped as well: TLS is decided
 * in one place, and a private CA is supplied through `NODE_EXTRA_CA_CERTS`.
 *
 * @param databaseUrl - the connection string.
 * @returns the string without the TLS parameters; an unparsable value comes back unchanged.
 */
export function stripSslParameters(databaseUrl: string): string {
  const url = parseUrl(databaseUrl);
  if (url === null) {
    return databaseUrl;
  }
  for (const parameter of SSL_URL_PARAMETERS) {
    url.searchParams.delete(parameter);
  }
  return url.toString();
}

function isLocalOrContainerHost(host: string): boolean {
  if (LOCAL_HOSTS.has(host)) {
    return true;
  }
  // A bracketed IPv6 literal that is not the loopback is a real address; only the LOCAL_HOSTS
  // check above may treat one as local.
  if (host.startsWith('[')) {
    return false;
  }
  // Single-label hostnames ("db", "postgres") are Docker/compose service names or LAN hosts,
  // never public DNS, so they stay plaintext by default.
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
