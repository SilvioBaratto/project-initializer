import { z } from 'zod';

/**
 * Response-facing whitelist for the Prisma `User` row.
 *
 * Only safe, non-secret columns are listed here. `StandardSchemaSerializerInterceptor`
 * (registered globally as `APP_INTERCEPTOR`) parses every outgoing User payload
 * against this schema, so any sensitive column that a future migration might add
 * to the `users` table (e.g. a credential hash or token) is stripped before it
 * leaves the API — it can only leak if it is added to this whitelist.
 */
export const UserResponseSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string(),
  is_active: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type UserResponseDto = z.infer<typeof UserResponseSchema>;
