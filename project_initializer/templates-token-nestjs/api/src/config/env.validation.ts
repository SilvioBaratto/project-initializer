import { z } from 'zod';

export const envSchema = z
  .object({
    DATABASE_URL: z.string().min(1),
    DIRECT_URL: z.string().min(1),
    AUTH_TOKEN: z.string().min(16, 'AUTH_TOKEN must be at least 16 characters'),
    PORT: z.coerce.number().default(3000),
    NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
    REDIS_HOST: z.string().default('localhost'),
    REDIS_PORT: z.coerce.number().default(6379),
    CORS_ORIGINS: z.string().optional(),
    LOG_LEVEL: z.string().optional(),
  })
  .passthrough();

export function validate(config: Record<string, unknown>): Record<string, unknown> {
  const parsed = envSchema.safeParse(config);
  if (!parsed.success) {
    const failures = parsed.error.issues
      .map((i) => `${i.path.join('.')}: ${i.message}`)
      .join('; ');
    throw new Error(`Invalid environment variables: ${failures}`);
  }
  return parsed.data as Record<string, unknown>;
}
