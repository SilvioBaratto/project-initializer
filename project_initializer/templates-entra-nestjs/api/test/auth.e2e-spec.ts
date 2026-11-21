import { generateKeyPairSync } from 'node:crypto';
import {
  ForbiddenException,
  INestApplication,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import * as jwt from 'jsonwebtoken';
import { JwksRateLimitError } from 'jwks-rsa';
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
import {
  entraIssuer,
  SIGNING_KEY_RESOLVER,
  type SigningKeyResolver,
} from '../src/modules/auth/auth.service';
import {
  TEST_ENTRA_API_AUDIENCE,
  TEST_ENTRA_API_SCOPE,
  TEST_ENTRA_TENANT_ID,
} from './support/auth-test-env';
import { createE2eApp, httpServerOf } from './support/create-e2e-app';

const TOKEN_USER_A = 'token-user-a';
const TOKEN_USER_B = 'token-user-b';
const TOKEN_MISSING_SCOPE = 'token-missing-scope';
const TOKEN_PROVIDER_DOWN = 'token-provider-down';

const USER_A: AuthenticatedUser = { id: 'user-a', email: 'a@example.com', roles: ['Reader'] };
const USER_B: AuthenticatedUser = { id: 'user-b', roles: [] };

// The real verifier needs Microsoft's keys; this stub maps each token to one verifier outcome so
// the guard, the exception filter and the controllers are exercised for every status.
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
describe('Entra authentication (e2e)', () => {
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
});

/** Validates src/modules/auth/auth.module.ts wiring of the real verifier behind the guard. */
describe('Entra token verification wiring (e2e)', () => {
  const RSA_MODULUS_BITS = 2048;
  const SIGNING_KEY_ID = 'e2e-signing-key';
  const TOKEN_LIFETIME = '5m';
  const OTHER_TENANT_ID = '44444444-4444-4444-8444-444444444444';
  const UNRELATED_SCOPE = 'Files.Read';
  const USER_OBJECT_ID = '33333333-3333-4333-8333-333333333333';
  const keyPair = generateKeyPairSync('rsa', {
    modulusLength: RSA_MODULUS_BITS,
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
  let app: INestApplication;
  let resolveKey: SigningKeyResolver;

  function signedToken(claims: Record<string, unknown> = {}): string {
    return jwt.sign(
      { tid: TEST_ENTRA_TENANT_ID, oid: USER_OBJECT_ID, scp: TEST_ENTRA_API_SCOPE, ...claims },
      keyPair.privateKey,
      {
        algorithm: 'RS256',
        keyid: SIGNING_KEY_ID,
        audience: TEST_ENTRA_API_AUDIENCE,
        issuer: entraIssuer(TEST_ENTRA_TENANT_ID),
        expiresIn: TOKEN_LIFETIME,
      },
    );
  }

  async function currentUser(token: string): Promise<request.Response> {
    return request(httpServerOf(app))
      .get(route('/auth/me'))
      .set('Authorization', `Bearer ${token}`);
  }

  beforeAll(async () => {
    // Only the key lookup is replaced; the guard, the real verifier and the configuration run as in
    // production, which is what proves the module wiring and the env-driven settings agree.
    ({ app } = await createE2eApp({
      verifier: null,
      customize: (builder) =>
        builder.overrideProvider(SIGNING_KEY_RESOLVER).useValue((kid: string) => resolveKey(kid)),
    }));
  });

  beforeEach(() => {
    resolveKey = () => Promise.resolve(keyPair.publicKey);
  });

  afterAll(async () => {
    await app.close();
  });

  it('when a token for the configured tenant, audience and scope is sent, then its identity is returned', async () => {
    const response = await currentUser(signedToken());

    expect(response.status).toBe(200);
    expect(response.body).toEqual({ id: USER_OBJECT_ID, email: null, roles: [] });
  });

  it('when the token has no required scope, then the response is 403', async () => {
    const response = await currentUser(signedToken({ scp: UNRELATED_SCOPE }));

    expect(response.status).toBe(403);
  });

  it('when the token is addressed to another tenant, then the response is the generic 401', async () => {
    const response = await currentUser(signedToken({ tid: OTHER_TENANT_ID }));

    expect(response.status).toBe(401);
    expect(response.body).toMatchObject({ message: INVALID_CREDENTIALS_MESSAGE });
  });

  it('when the signing keys cannot be fetched because of the rate limit, then the response is 503', async () => {
    resolveKey = () => Promise.reject(new JwksRateLimitError('Too many requests'));

    const response = await currentUser(signedToken());

    expect(response.status).toBe(503);
    expect(response.body).toMatchObject({ message: AUTH_PROVIDER_UNAVAILABLE_MESSAGE });
  });
});
