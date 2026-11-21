import {
  HttpException,
  HttpStatus,
  Inject,
  Injectable,
  Logger,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import {
  isAuthApiError,
  isAuthSessionMissingError,
  type AuthError,
  type User,
  type UserResponse,
} from '@supabase/supabase-js';
import { AccessTokenVerifier } from '../../common/auth/access-token-verifier';
import {
  AUTH_PROVIDER_UNAVAILABLE_MESSAGE,
  INVALID_CREDENTIALS_MESSAGE,
} from '../../common/auth/auth-messages';
import { AuthenticatedUser } from '../../common/auth/authenticated-user';
import { toOptionalEmail } from '../../common/auth/optional-email';
import { SUPABASE_CLIENT, SupabaseTokenClient } from './supabase-client.provider';

/** Role Supabase assigns to a signed-in user whose token names none. */
export const SUPABASE_DEFAULT_ROLE = 'authenticated';

/**
 * Role of a caller that signed in anonymously. Supabase gives such a user the same `authenticated`
 * role as a registered one, and anyone holding the publishable key can create one when anonymous
 * sign-ins are enabled, so the identity carries a distinct role that authorization can tell apart.
 */
export const SUPABASE_ANONYMOUS_ROLE = 'anonymous';

const FIRST_CLIENT_ERROR_STATUS: number = HttpStatus.BAD_REQUEST;
const FIRST_SERVER_ERROR_STATUS: number = HttpStatus.INTERNAL_SERVER_ERROR;
const RATE_LIMITED_STATUS: number = HttpStatus.TOO_MANY_REQUESTS;

const UNEXPECTED_ANSWER_MESSAGE = 'Supabase Auth answered a token check without a user';

function toAuthenticatedUser(user: User): AuthenticatedUser {
  return {
    id: user.id,
    // Phone and anonymous users have no address, and Supabase may report an empty string; either
    // way the identity stays valid without an email.
    email: toOptionalEmail(user.email),
    roles: [user.is_anonymous ? SUPABASE_ANONYMOUS_ROLE : (user.role ?? SUPABASE_DEFAULT_ROLE)],
  };
}

// Only a 4xx answer (other than the rate limit) or a signed-out session is a verdict on the token.
// A rate limit, an outage, a body the client could not parse and any error the library has no
// status for say nothing about the token, so treating them as 401 would make clients drop sessions
// that are still valid.
function isVerdictOnToken(error: AuthError): boolean {
  if (isAuthSessionMissingError(error)) {
    return true;
  }
  return (
    isAuthApiError(error) &&
    error.status >= FIRST_CLIENT_ERROR_STATUS &&
    error.status < FIRST_SERVER_ERROR_STATUS &&
    error.status !== RATE_LIMITED_STATUS
  );
}

/**
 * Verifies Supabase access tokens by asking Supabase Auth who the token belongs to.
 *
 * Failure mapping: a token Supabase rejects is a 401 whose text never says why. Anything that is
 * not such a verdict (a network failure or timeout, a 5xx or 429 answer, an unparseable or empty
 * answer, an unexpected throw) is a 503 that carries the cause, so a Supabase outage does not log
 * every user out with misleading 401s. The verifier does not log a 503; the exception filter does.
 */
@Injectable()
export class AuthService implements AccessTokenVerifier {
  private readonly logger = new Logger(AuthService.name);

  constructor(@Inject(SUPABASE_CLIENT) private readonly supabase: SupabaseTokenClient) {}

  /**
   * @param token - Raw Supabase access token (JWT).
   * @returns The caller's identity; `email` is absent for phone and anonymous users and when the
   *   address is not one the API can return. Anonymous users get {@link SUPABASE_ANONYMOUS_ROLE}.
   * @throws UnauthorizedException when Supabase rejects the token.
   * @throws ServiceUnavailableException when Supabase Auth cannot give a verdict on the token.
   */
  async verify(token: string): Promise<AuthenticatedUser> {
    const {
      data: { user },
      error,
    } = await this.fetchUser(token);
    if (error) {
      throw this.toRejection(error);
    }
    if (!user?.id) {
      throw new ServiceUnavailableException(AUTH_PROVIDER_UNAVAILABLE_MESSAGE, {
        cause: new Error(UNEXPECTED_ANSWER_MESSAGE),
      });
    }
    return toAuthenticatedUser(user);
  }

  private async fetchUser(token: string): Promise<UserResponse> {
    try {
      return await this.supabase.auth.getUser(token);
    } catch (error) {
      throw new ServiceUnavailableException(AUTH_PROVIDER_UNAVAILABLE_MESSAGE, { cause: error });
    }
  }

  private toRejection(error: AuthError): HttpException {
    if (isVerdictOnToken(error)) {
      return this.invalidCredentials(`Supabase rejected the token: ${error.code ?? error.name}`);
    }
    return new ServiceUnavailableException(AUTH_PROVIDER_UNAVAILABLE_MESSAGE, { cause: error });
  }

  // The reason is logged at debug level only: the guard already writes the one audit line per
  // rejection, and the reason must not reach the client.
  private invalidCredentials(reason: string): UnauthorizedException {
    this.logger.debug(reason);
    return new UnauthorizedException(INVALID_CREDENTIALS_MESSAGE);
  }
}
