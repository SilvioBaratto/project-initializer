import {
  ForbiddenException,
  INestApplication,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { AuthApiError, type User, type UserResponse } from '@supabase/supabase-js';
import request from 'supertest';
import { API_PREFIX } from '../src/app.setup';
import type { AccessTokenVerifier } from '../src/common/auth/access-token-verifier';
import {
  AUTH_PROVIDER_UNAVAILABLE_MESSAGE,
  AUTHENTICATION_REQUIRED_MESSAGE,
  INSUFFICIENT_SCOPE_MESSAGE,
  INVALID_CREDENTIALS_MESSAGE,
} from '../src/common/auth/auth-messages';
import type { AuthenticatedUser } from '../src/common/auth/authenticated-user';
import { SUPABASE_CLIENT } from '../src/modules/auth/supabase-client.provider';
import { createE2eApp, httpServerOf } from './support/create-e2e-app';

const TOKEN_USER_A = 'token-user-a';
const TOKEN_USER_B = 'token-user-b';
const TOKEN_MISSING_SCOPE = 'token-missing-scope';
const TOKEN_PROVIDER_DOWN = 'token-provider-down';

const USER_A: AuthenticatedUser = { id: 'user-a', email: 'a@example.com', roles: ['Reader'] };
const USER_B: AuthenticatedUser = { id: 'user-b', roles: [] };

// The real verifier asks Supabase Auth over the network; this stub maps each token to one verifier
// outcome so the guard, the exception filter and the controllers are exercised for every status.
const stubVerifier: AccessTokenVerifier = {
  verify(token) {
    switch (token) {
      case TOKEN_USER_A:
        return Promise.resolve(USER_A);
      case TOKEN_USER_B:
        return Promise.resolve(USER_B);
      case TOKEN_MISSING_SCOPE:
        return Promise.reject(new ForbiddenException(INSUFFICIENT_SCOPE_MESSAGE));
      case TOKEN_PROVIDER_DOWN:
        return Promise.reject(new ServiceUnavailableException(AUTH_PROVIDER_UNAVAILABLE_MESSAGE));
      default:
        return Promise.reject(new UnauthorizedException(INVALID_CREDENTIALS_MESSAGE));
    }
  },
};

function route(path: string): string {
  return `/${API_PREFIX}${path}`;
}

/** Validates src/app.auth.ts wiring: AccessTokenGuard, AuthModule and GET /auth/me. */
describe('Supabase authentication (e2e)', () => {
  let app: INestApplication;

  function get(path: string, token?: string): request.Test {
    const call = request(httpServerOf(app)).get(route(path));
    return token === undefined ? call : call.set('Authorization', `Bearer ${token}`);
  }

  beforeAll(async () => {
    ({ app } = await createE2eApp({ verifier: stubVerifier }));
  });

  afterAll(async () => {
    await app.close();
  });

  describe('credential outcomes', () => {
    it('when no Authorization header is sent, then a protected route returns 401', async () => {
      const response = await get('/auth/me');

      expect(response.status).toBe(401);
      expect(response.body).toMatchObject({ message: AUTHENTICATION_REQUIRED_MESSAGE });
    });

    it('when the scheme is not Bearer, then a protected route returns 401', async () => {
      const response = await request(httpServerOf(app))
        .get(route('/test/ping'))
        .set('Authorization', 'Basic dXNlcjpwYXNz');

      expect(response.status).toBe(401);
    });

    it('when the verifier rejects the token, then the response is the generic 401', async () => {
      const response = await get('/test/ping', 'forged-token');

      expect(response.status).toBe(401);
      expect(response.body).toMatchObject({ message: INVALID_CREDENTIALS_MESSAGE });
    });

    it('when the token lacks the required scope, then the response is 403', async () => {
      const response = await get('/test/ping', TOKEN_MISSING_SCOPE);

      expect(response.status).toBe(403);
      expect(response.body).toMatchObject({ message: INSUFFICIENT_SCOPE_MESSAGE });
    });

    it('when the identity provider is unreachable, then the response is 503', async () => {
      const response = await get('/test/ping', TOKEN_PROVIDER_DOWN);

      expect(response.status).toBe(503);
      expect(response.body).toMatchObject({ message: AUTH_PROVIDER_UNAVAILABLE_MESSAGE });
    });

    it('when the token is valid, then a protected route returns 200', async () => {
      const response = await get('/test/ping', TOKEN_USER_A);

      expect(response.status).toBe(200);
    });
  });

  describe('GET /auth/me', () => {
    it('when the token is valid, then the caller identity is returned', async () => {
      const response = await get('/auth/me', TOKEN_USER_A);

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ id: 'user-a', email: 'a@example.com', roles: ['Reader'] });
    });

    it('when the identity has no email, then email is null instead of an error', async () => {
      const response = await get('/auth/me', TOKEN_USER_B);

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ id: 'user-b', email: null, roles: [] });
    });
  });

  describe('chat job ownership', () => {
    it('when user B asks for a job created by user A, then the response is 404', async () => {
      const created = await request(httpServerOf(app))
        .post(route('/chat/jobs'))
        .set('Authorization', `Bearer ${TOKEN_USER_A}`)
        .send({ user_question: 'Hello' });
      const { jobId } = created.body as { jobId: string };

      const asOwner = await get(`/chat/jobs/${jobId}`, TOKEN_USER_A);
      const asOtherUser = await get(`/chat/jobs/${jobId}`, TOKEN_USER_B);

      expect(created.status).toBe(202);
      expect(asOwner.status).toBe(200);
      expect(asOtherUser.status).toBe(404);
    });
  });
});

/** Validates src/modules/auth/auth.module.ts wiring of the real verifier behind the guard. */
describe('Supabase token verification wiring (e2e)', () => {
  const SUPABASE_TOKEN = 'opaque.jwt.value';
  const UNAUTHORIZED_STATUS = 401;
  const RATE_LIMITED_STATUS = 429;
  const UPSTREAM_FAILURE_STATUS = 500;
  const supabaseUser: User = {
    id: 'a3b0f1c2-0000-4000-8000-000000000001',
    aud: 'authenticated',
    app_metadata: {},
    user_metadata: {},
    created_at: '2026-01-01T00:00:00Z',
    email: 'ada@example.com',
    role: 'authenticated',
  };
  const getUser = jest.fn<Promise<UserResponse>, [string?]>();
  let app: INestApplication;

  async function currentUser(): Promise<request.Response> {
    return request(httpServerOf(app))
      .get(route('/auth/me'))
      .set('Authorization', `Bearer ${SUPABASE_TOKEN}`);
  }

  beforeAll(async () => {
    // Only the Supabase client is replaced; the guard, the real verifier and the module wiring run
    // as in production.
    ({ app } = await createE2eApp({
      verifier: null,
      customize: (builder) =>
        builder.overrideProvider(SUPABASE_CLIENT).useValue({ auth: { getUser } }),
    }));
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(() => {
    getUser.mockReset();
  });

  it('when Supabase resolves the token to a user, then its identity is returned', async () => {
    getUser.mockResolvedValue({ data: { user: supabaseUser }, error: null });

    const response = await currentUser();

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      id: supabaseUser.id,
      email: 'ada@example.com',
      roles: ['authenticated'],
    });
    expect(getUser).toHaveBeenCalledWith(SUPABASE_TOKEN);
  });

  it('when Supabase rejects the token, then the response is the generic 401', async () => {
    getUser.mockResolvedValue({
      data: { user: null },
      error: new AuthApiError('invalid JWT', UNAUTHORIZED_STATUS, 'bad_jwt'),
    });

    const response = await currentUser();

    expect(response.status).toBe(401);
    expect(response.body).toMatchObject({ message: INVALID_CREDENTIALS_MESSAGE });
  });

  it('when Supabase fails with a server error, then the response is 503', async () => {
    getUser.mockResolvedValue({
      data: { user: null },
      error: new AuthApiError('upstream failure', UPSTREAM_FAILURE_STATUS, undefined),
    });

    const response = await currentUser();

    expect(response.status).toBe(503);
    expect(response.body).toMatchObject({ message: AUTH_PROVIDER_UNAVAILABLE_MESSAGE });
  });

  it('when Supabase rate-limits the check, then the response is 503, not an invalid token', async () => {
    getUser.mockResolvedValue({
      data: { user: null },
      error: new AuthApiError('rate limited', RATE_LIMITED_STATUS, 'over_request_rate_limit'),
    });

    const response = await currentUser();

    expect(response.status).toBe(503);
    expect(response.body).toMatchObject({ message: AUTH_PROVIDER_UNAVAILABLE_MESSAGE });
  });

  it.each([
    ['an exclamation mark in the local part', 'first!last@example.com', 'first!last@example.com'],
    ['a non-ASCII domain', 'müller@bücher.de', null],
  ])('when the user email is %s, then /auth/me answers 200', async (_label, email, expected) => {
    getUser.mockResolvedValue({ data: { user: { ...supabaseUser, email } }, error: null });

    const response = await currentUser();

    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({ email: expected });
  });
});
