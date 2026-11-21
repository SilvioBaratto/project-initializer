import { createHash, timingSafeEqual } from 'node:crypto';
import { Injectable, Logger, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { AccessTokenVerifier } from '../../common/auth/access-token-verifier';
import { INVALID_CREDENTIALS_MESSAGE } from '../../common/auth/auth-messages';
import { AuthenticatedUser } from '../../common/auth/authenticated-user';
import { Env } from '../../config/env.validation';
import { AuthResponseDto } from './dto/auth.dto';

/** Identity of every caller that presents the shared secret; the token cannot tell clients apart. */
export const TOKEN_CLIENT: AuthenticatedUser = { id: 'token-client', roles: ['service'] };

/** `message` of a `POST /auth/validate` answer for the right secret. */
export const TOKEN_ACCEPTED_MESSAGE = 'Authentication successful';

/** `message` of a `POST /auth/validate` answer for any other token. */
export const TOKEN_REJECTED_MESSAGE = 'Invalid token';

/**
 * Compares two secrets without leaking where they differ or how long they are.
 *
 * Hashing first gives `timingSafeEqual` equal-length inputs for any pair of strings, including
 * multibyte ones, so no length check has to run on the raw values.
 */
function constantTimeEquals(left: string, right: string): boolean {
  const leftDigest = createHash('sha256').update(left).digest();
  const rightDigest = createHash('sha256').update(right).digest();
  return timingSafeEqual(leftDigest, rightDigest);
}

/**
 * Verifies the single shared secret of the token variant. It is meant for service-to-service use:
 * every holder of the secret is the same `TOKEN_CLIENT`, so there is no per-user authorization.
 */
@Injectable()
export class AuthService implements AccessTokenVerifier {
  private readonly logger = new Logger(AuthService.name);
  private readonly authToken: string;

  constructor(config: ConfigService<Env, true>) {
    this.authToken = config.get('AUTH_TOKEN', { infer: true });
  }

  /**
   * @param token - Raw bearer token from the `Authorization` header.
   * @returns The shared service identity.
   * @throws UnauthorizedException when the token is not the configured secret. The guard writes the
   *   audit line for the rejection, so nothing is logged here.
   */
  verify(token: string): Promise<AuthenticatedUser> {
    if (!constantTimeEquals(token, this.authToken)) {
      return Promise.reject(new UnauthorizedException(INVALID_CREDENTIALS_MESSAGE));
    }
    return Promise.resolve(TOKEN_CLIENT);
  }

  /**
   * Checks a token for the public `POST /auth/validate` endpoint.
   *
   * @param token - Candidate secret from the request body.
   * @returns `authenticated: true` on a match. A mismatch is answered, not thrown, and written to
   *   the log without the token, because this public route has no guard to audit failed attempts.
   */
  validateToken(token: string): AuthResponseDto {
    if (constantTimeEquals(token, this.authToken)) {
      return { authenticated: true, message: TOKEN_ACCEPTED_MESSAGE };
    }
    this.logger.warn('Token validation failed');
    return { authenticated: false, message: TOKEN_REJECTED_MESSAGE };
  }
}
