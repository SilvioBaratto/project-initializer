import { z } from 'zod';
import { baseEnvSchema, createEnvValidator } from './env.base';

/**
 * Shortest accepted shared secret. 32 characters keeps a randomly generated token out of reach of
 * online guessing.
 */
export const MIN_AUTH_TOKEN_LENGTH = 32;

// RFC 6750 `b64token`: the secret travels in an `Authorization: Bearer` header, so it must be one
// run of characters that the header can carry unchanged. A blank inside it would be read as two
// credentials, and a non-ASCII character cannot be sent at all; either way every request would
// be refused while the secret looked valid at startup.
const BEARER_TOKEN_PATTERN = /^[A-Za-z0-9._~+/-]+=*$/;

/** Base environment plus the shared secret that every client presents as a bearer token. */
export const envSchema = baseEnvSchema.extend({
  AUTH_TOKEN: z
    .string()
    .min(MIN_AUTH_TOKEN_LENGTH, `AUTH_TOKEN must be at least ${MIN_AUTH_TOKEN_LENGTH} characters`)
    .regex(
      BEARER_TOKEN_PATTERN,
      'AUTH_TOKEN must contain only letters, digits and - . _ ~ + / (and = padding)',
    ),
});

/** Validated configuration of the token variant. */
export type Env = z.output<typeof envSchema>;

/**
 * Validates the process environment for `ConfigModule`.
 *
 * @throws Error `Invalid environment variables: ...` naming each failing key, never its value.
 */
export const validate = createEnvValidator(envSchema);
