import { z } from 'zod';
import { baseEnvSchema, createEnvValidator } from './env.base';
import { requiredScopeName } from './entra-scope';

// Entra writes GUIDs in lowercase in `iss` and `tid`, and both are compared as plain strings, so a
// tenant id pasted in uppercase would otherwise produce an issuer that no token ever matches.
const lowercaseGuidSchema = z.guid().transform((guid) => guid.toLowerCase());

/**
 * Environment contract of the Entra variant: the shared platform keys plus the identifiers of the
 * API app registration.
 *
 * The backend only verifies signatures against Entra's public keys, so no client secret is read.
 * Tenant and client ids are GUIDs, lowercased; a placeholder such as `your-tenant-id` fails at
 * startup instead of silently producing an issuer URL that no token will ever match.
 * `ENTRA_API_SCOPE` is reduced to its bare name (see {@link requiredScopeName}) and must not be
 * empty after that, so a value such as `api://<client-id>/` fails at startup instead of rejecting
 * every token with 403.
 */
export const envSchema = baseEnvSchema.extend({
  ENTRA_TENANT_ID: lowercaseGuidSchema,
  ENTRA_API_CLIENT_ID: lowercaseGuidSchema,
  ENTRA_API_AUDIENCE: z.string().min(1),
  ENTRA_API_SCOPE: z
    .string()
    .transform(requiredScopeName)
    .pipe(z.string().min(1, 'ENTRA_API_SCOPE must name a scope, for example access_as_user')),
});

/** Validated configuration of the Entra variant. */
export type Env = z.output<typeof envSchema>;

/**
 * `ConfigModule` validation hook for the Entra variant.
 *
 * @param config - Raw environment as loaded by `ConfigModule`.
 * @returns The parsed configuration with defaults applied.
 * @throws Error naming every invalid key; values are never echoed.
 */
export const validate = createEnvValidator(envSchema);
