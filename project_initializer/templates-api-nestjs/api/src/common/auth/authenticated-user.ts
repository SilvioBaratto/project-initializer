import type { Request } from 'express';

/** Identity that the active auth variant resolved from a verified access token. */
export interface AuthenticatedUser {
  /** Stable subject identifier of the caller; never a display name or an email. */
  readonly id: string;
  /** Present only when the identity provider released a valid address. */
  readonly email?: string;
  readonly roles: readonly string[];
}

/** An Express request that {@link AccessTokenGuard} has (or has not yet) attached an identity to. */
export type AuthenticatedRequest = Request & { user?: AuthenticatedUser };

/**
 * Returns the identifier that scopes a caller's own data, such as chat jobs.
 *
 * @param user - Identity attached by the guard, or `undefined` on public routes and in the
 *   base template where no authentication is wired.
 * @returns The caller's id, or `null` when the request is anonymous. Anonymous callers all share
 *   the `null` owner, which keeps the no-auth variant working without request scoping.
 */
export function ownerIdOf(user?: AuthenticatedUser): string | null {
  return user?.id ?? null;
}
