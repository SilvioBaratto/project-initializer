import request from 'supertest';
import {
  AUTHENTICATION_REQUIRED_MESSAGE,
  INVALID_CREDENTIALS_MESSAGE,
} from '../src/common/auth/auth-messages';
import { MAX_BEARER_TOKEN_LENGTH } from '../src/common/auth/bearer-token';
import { AUTH_PROBE_RATE_LIMIT } from '../src/config/rate-limit';
import { TOKEN_CLIENT } from '../src/modules/auth/auth.service';
import { TEST_AUTH_TOKEN } from './support/auth-test-env';
import { createE2eApp, E2eApp, httpServerOf } from './support/create-e2e-app';

const PING_PATH = '/api/v1/test/ping';
const VALIDATE_PATH = '/api/v1/auth/validate';
const ME_PATH = '/api/v1/auth/me';
const WRONG_TOKEN = `${TEST_AUTH_TOKEN}-wrong`;

/**
 * Validates the token variant end to end: the global `AccessTokenGuard` with the real shared-secret
 * verifier, the public `POST /auth/validate` endpoint and `GET /auth/me`.
 */
describe('Token authentication (e2e)', () => {
  const open: E2eApp[] = [];

  async function startApp(): Promise<E2eApp> {
    const e2e = await createE2eApp({ verifier: null });
    open.push(e2e);
    return e2e;
  }

  afterEach(async () => {
    await Promise.all(open.splice(0).map((e2e) => e2e.app.close()));
  });

  describe('protected routes', () => {
    it('when no Authorization header is sent, then 401 asks for authentication', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app)).get(PING_PATH);

      expect(response.status).toBe(401);
      expect(response.body).toMatchObject({ message: AUTHENTICATION_REQUIRED_MESSAGE });
    });

    it('when the token is wrong, then 401 with the generic credentials message', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .get(PING_PATH)
        .set('Authorization', `Bearer ${WRONG_TOKEN}`);

      expect(response.status).toBe(401);
      expect(response.body).toMatchObject({ message: INVALID_CREDENTIALS_MESSAGE });
    });

    it('when another scheme is used, then 401 asks for authentication', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .get(PING_PATH)
        .set('Authorization', `Basic ${TEST_AUTH_TOKEN}`);

      expect(response.status).toBe(401);
    });

    it('when the shared secret is sent, then the route answers 200', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .get(PING_PATH)
        .set('Authorization', `Bearer ${TEST_AUTH_TOKEN}`);

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ message: 'pong' });
    });

    it('when the scheme is lowercase, then the shared secret is still accepted', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .get(PING_PATH)
        .set('Authorization', `bearer ${TEST_AUTH_TOKEN}`);

      expect(response.status).toBe(200);
    });

    it('when a health probe has no credentials, then it is public', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app)).get('/api/v1/health/liveness');

      expect(response.status).toBe(200);
    });
  });

  describe('GET /auth/me', () => {
    it('when the shared secret is sent, then the service identity is returned', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .get(ME_PATH)
        .set('Authorization', `Bearer ${TEST_AUTH_TOKEN}`);

      expect(response.status).toBe(200);
      expect(response.body).toEqual({
        id: TOKEN_CLIENT.id,
        email: null,
        roles: TOKEN_CLIENT.roles,
      });
    });

    it('when no credentials are sent, then 401', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app)).get(ME_PATH);

      expect(response.status).toBe(401);
    });
  });

  describe('POST /auth/validate', () => {
    it('when the shared secret is posted without credentials, then it answers authenticated true', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .post(VALIDATE_PATH)
        .send({ token: TEST_AUTH_TOKEN });

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({ authenticated: true });
    });

    it('when a wrong token is posted, then it answers authenticated false with 200', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .post(VALIDATE_PATH)
        .send({ token: WRONG_TOKEN });

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({ authenticated: false });
    });

    it('when the token has surrounding blanks, then it is judged like the guard would judge it', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .post(VALIDATE_PATH)
        .send({ token: `  ${TEST_AUTH_TOKEN}  ` });

      expect(response.body).toMatchObject({ authenticated: true });
    });

    it('when the token has a blank inside, then it is answered as not authenticated', async () => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app))
        .post(VALIDATE_PATH)
        .send({ token: `${TEST_AUTH_TOKEN} ${TEST_AUTH_TOKEN}` });

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({ authenticated: false });
    });

    it.each([
      ['no token', {}],
      ['an empty token', { token: '' }],
      ['a blank token', { token: '   ' }],
      ['an oversize token', { token: 'a'.repeat(MAX_BEARER_TOKEN_LENGTH + 1) }],
      ['a non-string token', { token: 42 }],
    ])('when the body has %s, then it answers 400', async (_label, body) => {
      const { app } = await startApp();

      const response = await request(httpServerOf(app)).post(VALIDATE_PATH).send(body);

      expect(response.status).toBe(400);
    });

    it('when attempts exceed the probe limit, then 429 stops further guessing', async () => {
      const { app } = await startApp();
      const allowedAttempts = AUTH_PROBE_RATE_LIMIT.default.limit;

      for (let attempt = 0; attempt < allowedAttempts; attempt += 1) {
        const allowed = await request(httpServerOf(app))
          .post(VALIDATE_PATH)
          .send({ token: WRONG_TOKEN });
        expect(allowed.status).toBe(200);
      }
      const blocked = await request(httpServerOf(app))
        .post(VALIDATE_PATH)
        .send({ token: WRONG_TOKEN });

      expect(blocked.status).toBe(429);
    });
  });
});
