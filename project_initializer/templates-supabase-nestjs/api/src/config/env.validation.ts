import { z } from 'zod';
import { baseEnvSchema, createEnvValidator } from './env.base';

const HTTPS_PROTOCOL = 'https:';
const PRODUCTION_NODE_ENV = 'production';

/**
 * Environment contract of the Supabase variant: the shared platform keys plus the project URL and
 * the publishable key used to verify access tokens.
 *
 * The service-role (secret) key is deliberately absent. It bypasses Row Level Security and nothing
 * here needs it, so the schema neither requires nor exposes it.
 *
 * In production `SUPABASE_URL` must use `https`: every token check sends the caller's access token
 * and the publishable key to that URL. Plain `http` is accepted elsewhere for the local Supabase
 * CLI (`http://127.0.0.1:54321`).
 */
export const envSchema = baseEnvSchema
  .extend({
    SUPABASE_URL: z.url({ protocol: /^https?$/ }),
    SUPABASE_PUBLISHABLE_KEY: z.string().min(1),
  })
  .refine(
    (env) =>
      env.NODE_ENV !== PRODUCTION_NODE_ENV || new URL(env.SUPABASE_URL).protocol === HTTPS_PROTOCOL,
    { path: ['SUPABASE_URL'], error: 'SUPABASE_URL must use https when NODE_ENV is production' },
  );

/** Validated configuration of the Supabase variant. */
export type Env = z.output<typeof envSchema>;

/**
 * `ConfigModule` validation hook for the Supabase variant.
 *
 * @param config - Raw environment as loaded by `ConfigModule`.
 * @returns The parsed configuration with defaults applied.
 * @throws Error naming every invalid key; values are never echoed.
 */
export const validate = createEnvValidator(envSchema);
