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
