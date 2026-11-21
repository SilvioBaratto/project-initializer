import { Logger, ServiceUnavailableException, UnauthorizedException } from '@nestjs/common';
import {
  AuthApiError,
  AuthRetryableFetchError,
  AuthSessionMissingError,
  AuthUnknownError,
  type AuthError,
  type User,
  type UserResponse,
} from '@supabase/supabase-js';
import {
  AUTH_PROVIDER_UNAVAILABLE_MESSAGE,
  INVALID_CREDENTIALS_MESSAGE,
} from '../../common/auth/auth-messages';
import { AuthService, SUPABASE_ANONYMOUS_ROLE, SUPABASE_DEFAULT_ROLE } from './auth.service';

const ACCESS_TOKEN = 'opaque.jwt.value';
const NETWORK_FAILURE_STATUS = 0;

function buildUser(overrides: Partial<User> = {}): User {
  return {
    id: '8f0f4b0e-6c5d-4d57-9a64-0f6e0f3f0a11',
    aud: 'authenticated',
    app_metadata: {},
    user_metadata: {},
    created_at: '2026-01-01T00:00:00Z',
    email: 'ada@example.com',
    role: 'authenticated',
    ...overrides,
  };
}

function userFound(user: User): UserResponse {
  return { data: { user }, error: null };
}

function userRejected(error: AuthError): UserResponse {
  return { data: { user: null }, error };
}

async function rejection(attempt: Promise<unknown>): Promise<unknown> {
  try {
    await attempt;
  } catch (error) {
    return error;
  }
  throw new Error('Expected the promise to reject');
}

/** Validates src/modules/auth/auth.service.ts (Supabase access token verification). */
describe('AuthService.verify', () => {
  const getUser = jest.fn<Promise<UserResponse>, [string?]>();
  const service = new AuthService({ auth: { getUser } });
  let errorLog: jest.SpyInstance;

  beforeAll(() => {
    Logger.overrideLogger(false);
  });

  beforeEach(() => {
    getUser.mockReset();
    errorLog = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('accepted tokens', () => {
    it('when Supabase returns a user, then the identity carries id, email and role', async () => {
      const user = buildUser();
      getUser.mockResolvedValue(userFound(user));

      await expect(service.verify(ACCESS_TOKEN)).resolves.toEqual({
        id: user.id,
        email: 'ada@example.com',
        roles: ['authenticated'],
      });
      expect(getUser).toHaveBeenCalledWith(ACCESS_TOKEN);
    });

    it('when the user has no email, as for phone sign-ins, then email is undefined', async () => {
      getUser.mockResolvedValue(userFound(buildUser({ email: undefined, phone: '+15550100' })));

      const identity = await service.verify(ACCESS_TOKEN);

      expect(identity.email).toBeUndefined();
      expect(identity.id).toEqual(expect.any(String));
    });

    it('when Supabase reports an empty email, then email is undefined', async () => {
      getUser.mockResolvedValue(userFound(buildUser({ email: '' })));

      await expect(service.verify(ACCESS_TOKEN)).resolves.toMatchObject({ email: undefined });
    });

    it.each([
      ['first!last@example.com', 'first!last@example.com'],
      ['dev@localhost', 'dev@localhost'],
      ['müller@bücher.de', undefined],
    ])('when the email is %j, then the identity email is %j', async (email, expected) => {
      getUser.mockResolvedValue(userFound(buildUser({ email })));

      const identity = await service.verify(ACCESS_TOKEN);

      expect(identity.email).toBe(expected);
    });

    it('when the user has no role, then the default Supabase role is used', async () => {
      getUser.mockResolvedValue(userFound(buildUser({ role: undefined })));

      await expect(service.verify(ACCESS_TOKEN)).resolves.toMatchObject({
        roles: [SUPABASE_DEFAULT_ROLE],
      });
    });

    it('when the user has a custom role, then it is exposed as the only role', async () => {
      getUser.mockResolvedValue(userFound(buildUser({ role: 'editor' })));

      await expect(service.verify(ACCESS_TOKEN)).resolves.toMatchObject({ roles: ['editor'] });
    });

    it('when the user signed in anonymously, then the anonymous role replaces authenticated', async () => {
      getUser.mockResolvedValue(
        userFound(buildUser({ email: undefined, is_anonymous: true, role: 'authenticated' })),
      );

      await expect(service.verify(ACCESS_TOKEN)).resolves.toMatchObject({
        roles: [SUPABASE_ANONYMOUS_ROLE],
      });
    });
  });

  describe('rejected tokens', () => {
    it.each([
      ['401 bad_jwt', new AuthApiError('invalid JWT: provider-specific detail', 401, 'bad_jwt')],
      ['403 bad_jwt', new AuthApiError('invalid JWT', 403, 'bad_jwt')],
      [
        '404 user_not_found',
        new AuthApiError('User from sub claim does not exist', 404, 'user_not_found'),
      ],
      ['a signed-out session', new AuthSessionMissingError()],
    ])('when Supabase answers %s, then the response is the generic 401', async (_label, error) => {
      getUser.mockResolvedValue(userRejected(error));

      const outcome = await rejection(service.verify(ACCESS_TOKEN));

      expect(outcome).toBeInstanceOf(UnauthorizedException);
      expect(outcome).toHaveProperty('message', INVALID_CREDENTIALS_MESSAGE);
      expect(errorLog).not.toHaveBeenCalled();
    });
  });

  describe('answers that are no verdict on the token', () => {
    it.each([
      ['a network failure', new AuthRetryableFetchError('fetch failed', NETWORK_FAILURE_STATUS)],
      [
        'a 429 over_request_rate_limit',
        new AuthApiError('rate limited', 429, 'over_request_rate_limit'),
      ],
      ['a 500', new AuthApiError('upstream failure', 500, undefined)],
      ['a 502', new AuthApiError('bad gateway', 502, undefined)],
      ['a 503', new AuthRetryableFetchError('unavailable', 503)],
      [
        'an unparseable body',
        new AuthUnknownError('Unexpected token < in JSON', new SyntaxError()),
      ],
    ])(
      'when Supabase answers with %s, then the response is 503 carrying the cause',
      async (_label, error) => {
        getUser.mockResolvedValue(userRejected(error));

        const outcome = await rejection(service.verify(ACCESS_TOKEN));

        expect(outcome).toBeInstanceOf(ServiceUnavailableException);
        expect(outcome).not.toBeInstanceOf(UnauthorizedException);
        expect(outcome).toHaveProperty('message', AUTH_PROVIDER_UNAVAILABLE_MESSAGE);
        expect(outcome).toHaveProperty('cause', error);
      },
    );

    it.each([
      ['no user', { data: { user: null }, error: null }],
      ['a user without an id', { data: { user: {} }, error: null }],
    ])('when Supabase answers 200 with %s, then the response is 503', async (_label, answer) => {
      getUser.mockResolvedValue(answer as unknown as UserResponse);

      const outcome = await rejection(service.verify(ACCESS_TOKEN));

      expect(outcome).toBeInstanceOf(ServiceUnavailableException);
      expect(outcome).toHaveProperty('cause', expect.any(Error));
    });

    it('when the Supabase client throws, then the response is 503 carrying what was thrown', async () => {
      const failure = new TypeError('unexpected client failure');
      getUser.mockRejectedValue(failure);

      const outcome = await rejection(service.verify(ACCESS_TOKEN));

      expect(outcome).toBeInstanceOf(ServiceUnavailableException);
      expect(outcome).toHaveProperty('message', AUTH_PROVIDER_UNAVAILABLE_MESSAGE);
      expect(outcome).toHaveProperty('cause', failure);
    });

    it('when Supabase is unavailable, then the verifier itself writes no error log', async () => {
      getUser.mockResolvedValue(userRejected(new AuthApiError('upstream failure', 500, undefined)));

      await rejection(service.verify(ACCESS_TOKEN));

      expect(errorLog).not.toHaveBeenCalled();
    });
  });
});
