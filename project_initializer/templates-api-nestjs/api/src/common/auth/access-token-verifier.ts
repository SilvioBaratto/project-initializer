import type { AuthenticatedUser } from './authenticated-user';

/** Injection token for the {@link AccessTokenVerifier} that the active auth variant provides. */
export const ACCESS_TOKEN_VERIFIER = Symbol('ACCESS_TOKEN_VERIFIER');

/**
 * Port between the generic guard and a concrete credential check (shared token, Supabase, Entra).
 *
 * Implementations signal failure with Nest HTTP exceptions so the guard can pass them through:
 * `UnauthorizedException` for an invalid or expired token, `ForbiddenException` for a valid token
 * that lacks the required scope, `ServiceUnavailableException` when the identity provider cannot
 * be reached or answers with something other than a verdict on the token. A 503 carries the
 * underlying failure as its `cause` and the verifier does not log it: the exception filter writes
 * that one log line. Any other thrown error is treated by the guard as an invalid token.
 */
export interface AccessTokenVerifier {
  /**
   * Verifies one raw bearer token.
   *
   * @param token - Token without the `Bearer` prefix, already trimmed and length-checked.
   * @returns The identity the token proves.
   */
  verify(token: string): Promise<AuthenticatedUser>;
}
