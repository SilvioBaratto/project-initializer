import { z } from 'zod';
import type { AuthenticatedUser } from './authenticated-user';
import { emailAddressSchema } from './optional-email';

/**
 * Response contract of `GET /auth/me`. It is a whitelist: only these fields leave the API, so
 * claims that a provider adds later stay internal until they are listed here.
 */
export const UserInfoSchema = z.object({
  id: z.string().min(1),
  email: emailAddressSchema.nullable(),
  roles: z.array(z.string()),
});

/** Response body of `GET /auth/me`, derived from {@link UserInfoSchema}. */
export type UserInfoDto = z.infer<typeof UserInfoSchema>;

/**
 * Maps the internal identity to its response shape.
 *
 * @param user - Verified identity attached by the guard.
 * @returns The identity with a missing email as `null`, so the field is always present on the wire.
 */
export function toUserInfo(user: AuthenticatedUser): UserInfoDto {
  return { id: user.id, email: user.email ?? null, roles: [...user.roles] };
}
