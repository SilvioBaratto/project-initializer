import type { z } from 'zod';
import { baseEnvSchema, createEnvValidator } from './env.base';

/**
 * Schema of every environment key this variant reads.
 *
 * The base variant needs only the shared keys. An auth overlay replaces this file with
 * `baseEnvSchema.extend({ ... })` for its own keys; nothing else in the template changes.
 */
export const envSchema = baseEnvSchema;

/** Validated configuration of this variant. Shared code types its config as `BaseEnv` instead. */
export type Env = z.output<typeof envSchema>;

/** Passed to `ConfigModule.forRoot` so a bad or missing key stops the process at start-up. */
export const validate = createEnvValidator(envSchema);
