import { z } from 'zod';
import { DEFAULT_LOG_LEVEL, LOG_LEVELS, normalizeLogLevel } from './logger.config';

/** Runtime modes the application recognises. */
export const NODE_ENVS = ['development', 'production', 'test'] as const;

/** One of {@link NODE_ENVS}. */
export type NodeEnv = (typeof NODE_ENVS)[number];

/** Shortest queue dashboard password accepted; a shorter one is rejected at start-up. */
export const MIN_QUEUE_MONITOR_PASSWORD_LENGTH = 16;

const MIN_TCP_PORT = 1;
const MAX_TCP_PORT = 65_535;
const MIN_TRUST_PROXY_HOPS = 0;
const MAX_TRUST_PROXY_HOPS = 10;

const ENV_DEFAULTS = {
  PORT: 3000,
  NODE_ENV: 'development',
  REDIS_HOST: 'localhost',
  REDIS_PORT: 6379,
  CORS_ORIGINS: 'http://localhost:4200',
  QUEUE_MONITOR_USER: 'admin',
  DB_CONNECT_TIMEOUT_MS: 5_000,
  DB_QUERY_TIMEOUT_MS: 15_000,
  DB_POOL_MAX: 10,
  DB_BREAKER_FAILURE_THRESHOLD: 5,
  DB_BREAKER_RESET_MS: 30_000,
  HEALTH_HEAP_READINESS_MB: 300,
  HEALTH_HEAP_LIVENESS_MB: 512,
  TRUST_PROXY_HOPS: 1,
  DB_ALLOW_INSECURE_TRANSPORT: false,
} as const;

/**
 * `sslmode` values of `DATABASE_URL` that put the database connection under TLS: `require` encrypts,
 * `verify-ca` and `verify-full` also verify the server certificate. Every one of them makes the
 * `ssl` option the Prisma adapter derives (`deriveSslOption`) non-empty, so production never ends
 * up on a plaintext link while the schema reports it as protected.
 */
export const ENCRYPTED_DATABASE_SSLMODES: ReadonlySet<string> = new Set([
  'require',
  'verify-ca',
  'verify-full',
]);

const SSLMODE_PARAMETER = 'sslmode';
const PRODUCTION_NODE_ENV: NodeEnv = 'production';
const DATABASE_TRANSPORT_ERROR =
  'DATABASE_URL must carry sslmode=require, verify-ca or verify-full when NODE_ENV is production; ' +
  'set DB_ALLOW_INSECURE_TRANSPORT=true only for a database on the same host or a private network ' +
  'without TLS';

const ENV_ERROR_PREFIX = 'Invalid environment variables:';
const ROOT_PATH_LABEL = '(root)';
const CORS_ORIGIN_SEPARATOR = ',';

/**
 * Turns an empty string into `undefined`, for `z.preprocess` on keys that are left blank in a
 * generated `.env` file to mean "not set".
 *
 * @param value - The raw environment value.
 * @returns `undefined` for `''`; every other value unchanged, so a bad value still fails later.
 */
export function blankToUndefined(value: unknown): unknown {
  return value === '' ? undefined : value;
}

const portSchema = z.coerce.number().pipe(z.int().min(MIN_TCP_PORT).max(MAX_TCP_PORT));
const positiveIntegerSchema = z.coerce.number().pipe(z.int().positive());
const trustProxyHopsSchema = z.coerce
  .number()
  .pipe(z.int().min(MIN_TRUST_PROXY_HOPS).max(MAX_TRUST_PROXY_HOPS));
const postgresUrlSchema = z.url({ protocol: /^postgres(ql)?$/ });

const corsOriginsSchema = z
  .string()
  .default(ENV_DEFAULTS.CORS_ORIGINS)
  .transform((raw) =>
    raw
      .split(CORS_ORIGIN_SEPARATOR)
      .map((origin) => origin.trim())
      .filter((origin) => origin.length > 0),
  )
  .pipe(z.array(z.url({ protocol: /^https?$/ })).min(1))
  // The browser's Origin header never carries a path or a trailing slash, so an entry written with
  // one would silently never match.
  .transform((origins) => [...new Set(origins.map((origin) => new URL(origin).origin))]);

// Normalisation lives in logger.config so the vocabulary and the casing rule stay together.
const logLevelSchema = z
  .string()
  .default(DEFAULT_LOG_LEVEL)
  .transform(normalizeLogLevel)
  .pipe(z.enum(LOG_LEVELS));

/**
 * Keys every variant needs, as a plain shape so an overlay can spread it next to its own keys.
 *
 * - `DATABASE_URL`, `DIRECT_URL`: Postgres connection strings, required.
 * - `PORT`, `REDIS_PORT`: TCP ports, 1 to 65535.
 * - `CORS_ORIGINS`: comma-separated http(s) URLs in the file, an array of bare origins (scheme,
 *   host, port) once validated.
 * - `TRUST_PROXY_HOPS`: reverse proxies between the client and this process (0 to 10). The client
 *   address the rate limiter keys on is read that many entries from the right of `X-Forwarded-For`.
 *   Use 0 when the API is exposed directly, otherwise a client can spoof the header.
 * - `API_DOCS_ENABLED`: publishes the OpenAPI UI at `/docs`; unset means on outside production.
 * - `LOG_LEVEL`: any casing of a pino level; validated lowercase.
 * - `QUEUE_MONITOR_USER`, `QUEUE_MONITOR_PASSWORD`: credentials of the queue dashboard. A blank or
 *   absent password leaves the dashboard closed.
 * - `DB_*`: client-side connect and query timeouts, the pool size and the circuit breaker
 *   thresholds.
 * - `DB_ALLOW_INSECURE_TRANSPORT`: opt-out of the production rule on `DATABASE_URL`, see
 *   {@link baseEnvSchema}. Default `false`.
 * - `HEALTH_HEAP_*_MB`: heap ceilings, in megabytes, of the readiness and liveness probes.
 */
export const baseEnvShape = {
  DATABASE_URL: postgresUrlSchema,
  DIRECT_URL: postgresUrlSchema,
  PORT: portSchema.default(ENV_DEFAULTS.PORT),
  NODE_ENV: z.enum(NODE_ENVS).default(ENV_DEFAULTS.NODE_ENV),
  REDIS_HOST: z.string().min(1).default(ENV_DEFAULTS.REDIS_HOST),
  REDIS_PORT: portSchema.default(ENV_DEFAULTS.REDIS_PORT),
  CORS_ORIGINS: corsOriginsSchema,
  LOG_LEVEL: logLevelSchema,
  TRUST_PROXY_HOPS: trustProxyHopsSchema.default(ENV_DEFAULTS.TRUST_PROXY_HOPS),
  API_DOCS_ENABLED: z.preprocess(blankToUndefined, z.stringbool().optional()),
  QUEUE_MONITOR_USER: z.string().min(1).default(ENV_DEFAULTS.QUEUE_MONITOR_USER),
  QUEUE_MONITOR_PASSWORD: z.preprocess(
    blankToUndefined,
    z.string().min(MIN_QUEUE_MONITOR_PASSWORD_LENGTH).optional(),
  ),
  DB_CONNECT_TIMEOUT_MS: positiveIntegerSchema.default(ENV_DEFAULTS.DB_CONNECT_TIMEOUT_MS),
  DB_QUERY_TIMEOUT_MS: positiveIntegerSchema.default(ENV_DEFAULTS.DB_QUERY_TIMEOUT_MS),
  DB_POOL_MAX: positiveIntegerSchema.default(ENV_DEFAULTS.DB_POOL_MAX),
  DB_BREAKER_FAILURE_THRESHOLD: positiveIntegerSchema.default(
    ENV_DEFAULTS.DB_BREAKER_FAILURE_THRESHOLD,
  ),
  DB_BREAKER_RESET_MS: positiveIntegerSchema.default(ENV_DEFAULTS.DB_BREAKER_RESET_MS),
  HEALTH_HEAP_READINESS_MB: positiveIntegerSchema.default(ENV_DEFAULTS.HEALTH_HEAP_READINESS_MB),
  HEALTH_HEAP_LIVENESS_MB: positiveIntegerSchema.default(ENV_DEFAULTS.HEALTH_HEAP_LIVENESS_MB),
  DB_ALLOW_INSECURE_TRANSPORT: z.preprocess(
    blankToUndefined,
    z.stringbool().default(ENV_DEFAULTS.DB_ALLOW_INSECURE_TRANSPORT),
  ),
};

type BaseEnvInput = z.output<z.ZodObject<typeof baseEnvShape>>;

function usesEncryptedTransport(databaseUrl: string): boolean {
  // A value that is not a Postgres URL is already reported on its own key; a second message about
  // its transport would only add noise.
  if (!postgresUrlSchema.safeParse(databaseUrl).success) {
    return true;
  }
  const sslmodes = new URL(databaseUrl).searchParams.getAll(SSLMODE_PARAMETER);
  // Every occurrence must be encrypted: drivers disagree on which of several sslmode parameters
  // wins, so `sslmode=require&sslmode=disable` must not pass on the strength of its first value.
  return sslmodes.length > 0 && sslmodes.every((mode) => ENCRYPTED_DATABASE_SSLMODES.has(mode));
}

function isDatabaseTransportAllowed(env: BaseEnvInput): boolean {
  return (
    env.NODE_ENV !== PRODUCTION_NODE_ENV ||
    env.DB_ALLOW_INSECURE_TRANSPORT ||
    usesEncryptedTransport(env.DATABASE_URL)
  );
}

/**
 * Schema of the keys every variant needs. Unknown keys are dropped from the validated result.
 *
 * With `NODE_ENV=production` the schema refuses a `DATABASE_URL` whose `sslmode` parameter is
 * absent or is not `require`, `verify-ca` or `verify-full`, so credentials and rows never cross a
 * network in the clear by accident. `DB_ALLOW_INSECURE_TRANSPORT=true` is the explicit opt-out for
 * a database on the same host or a private network that serves no TLS, such as the compose `db`
 * service. Outside production the rule does not apply. The message names both keys and never the
 * URL, which holds the password.
 *
 * Overlays add their keys with `.extend()`, which keeps this rule.
 */
export const baseEnvSchema = z.object(baseEnvShape).refine(isDatabaseTransportAllowed, {
  path: ['DATABASE_URL'],
  error: DATABASE_TRANSPORT_ERROR,
});

/** Validated base configuration, as `ConfigService<BaseEnv, true>` returns it. */
export type BaseEnv = z.output<typeof baseEnvSchema>;

function describeIssues(error: z.ZodError): string {
  return error.issues
    .map((issue) => {
      const path = issue.path.map((segment) => String(segment)).join('.');
      return `${path || ROOT_PATH_LABEL}: ${issue.message}`;
    })
    .join('; ');
}

/**
 * Creates the `validate` function `ConfigModule.forRoot` calls with the raw environment, so the
 * check is written once and an overlay only supplies its own schema.
 *
 * @param schema - Object schema of every key the variant reads.
 * @returns A function that returns the parsed, defaulted configuration and throws when it is
 *   invalid. The error lists every failing key with the reason; it never repeats a value, which
 *   may be a credential.
 */
export function createEnvValidator<S extends z.ZodType<Record<string, unknown>>>(
  schema: S,
): (config: Record<string, unknown>) => z.output<S> {
  return (config) => {
    const parsed = schema.safeParse(config);
    if (!parsed.success) {
      throw new Error(`${ENV_ERROR_PREFIX} ${describeIssues(parsed.error)}`);
    }
    return parsed.data;
  };
}
