import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';
import { Logger, ServiceUnavailableException, UnauthorizedException } from '@nestjs/common';
import { createClient } from '@supabase/supabase-js';
import { TEST_SUPABASE_PUBLISHABLE_KEY } from '../../../test/support/auth-test-env';
import { AuthService } from './auth.service';
import {
  createTimeoutFetch,
  SUPABASE_SERVER_AUTH_OPTIONS,
  type SupabaseTokenClient,
} from './supabase-client.provider';

type ServerReply = (request: IncomingMessage, response: ServerResponse) => void;

const ACCESS_TOKEN = 'opaque.jwt.value';
const SHORT_TIMEOUT_MS = 50;
const USER_PATH = '/auth/v1/user';
const GENEROUS_TIMEOUT_MS = 5_000;
const USER_ID = '8f0f4b0e-6c5d-4d57-9a64-0f6e0f3f0a11';

function replyJson(status: number, body: unknown): ServerReply {
  return (_request, response) => {
    response.writeHead(status, { 'content-type': 'application/json' });
    response.end(JSON.stringify(body));
  };
}

/**
 * Validates how src/modules/auth/auth.service.ts AuthService and
 * src/modules/auth/supabase-client.provider.ts createTimeoutFetch behave with the real Supabase
 * auth client, against a local HTTP server that plays Supabase Auth.
 */
describe('Supabase token verification over HTTP', () => {
  let server: Server;
  let reply: ServerReply;
  let requestedPaths: string[];
  let baseUrl: string;

  function serviceWithTimeout(timeoutMs: number): AuthService {
    const client: SupabaseTokenClient = createClient(baseUrl, TEST_SUPABASE_PUBLISHABLE_KEY, {
      auth: SUPABASE_SERVER_AUTH_OPTIONS,
      global: { fetch: createTimeoutFetch(timeoutMs) },
    });
    return new AuthService(client);
  }

  beforeAll(async () => {
    server = createServer((request, response) => {
      requestedPaths.push(request.url ?? '');
      reply(request, response);
    });
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
    Logger.overrideLogger(false);
  });

  beforeEach(() => {
    requestedPaths = [];
    // The auth client prints every failed fetch itself; the output is not what these tests check.
    jest.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  afterAll(async () => {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  it('when Supabase answers with the user, then the identity is returned', async () => {
    reply = replyJson(200, { id: USER_ID, email: 'ada@example.com', role: 'authenticated' });

    const identity = await serviceWithTimeout(GENEROUS_TIMEOUT_MS).verify(ACCESS_TOKEN);

    expect(identity).toEqual({ id: USER_ID, email: 'ada@example.com', roles: ['authenticated'] });
    expect(requestedPaths).toEqual([USER_PATH]);
  });

  it.each([
    ['401 bad_jwt', 401, { code: 401, error_code: 'bad_jwt', msg: 'invalid JWT' }],
    ['403 bad_jwt', 403, { code: 403, error_code: 'bad_jwt', msg: 'invalid JWT' }],
    ['404 user_not_found', 404, { code: 404, error_code: 'user_not_found', msg: 'gone' }],
    [
      '403 session_not_found',
      403,
      { code: 403, error_code: 'session_not_found', msg: 'signed out' },
    ],
  ])(
    'when Supabase answers %s, then the token is refused with 401',
    async (_label, status, body) => {
      reply = replyJson(status, body);

      await expect(
        serviceWithTimeout(GENEROUS_TIMEOUT_MS).verify(ACCESS_TOKEN),
      ).rejects.toBeInstanceOf(UnauthorizedException);
    },
  );

  it.each([
    [
      '429 over_request_rate_limit',
      429,
      { code: 429, error_code: 'over_request_rate_limit', msg: 'slow down' },
    ],
    ['500', 500, { code: 500, error_code: 'unexpected_failure', msg: 'boom' }],
    ['503', 503, { msg: 'unavailable' }],
  ])(
    'when Supabase answers %s, then the caller sees 503, not an invalid token',
    async (_label, status, body) => {
      reply = replyJson(status, body);

      await expect(
        serviceWithTimeout(GENEROUS_TIMEOUT_MS).verify(ACCESS_TOKEN),
      ).rejects.toBeInstanceOf(ServiceUnavailableException);
    },
  );

  it('when the error body is not JSON, then the caller sees 503', async () => {
    reply = (_request, response) => {
      response.writeHead(500, { 'content-type': 'text/html' });
      response.end('<html>Internal Server Error</html>');
    };

    await expect(
      serviceWithTimeout(GENEROUS_TIMEOUT_MS).verify(ACCESS_TOKEN),
    ).rejects.toBeInstanceOf(ServiceUnavailableException);
  });

  it('when Supabase does not answer within the timeout, then the caller sees 503 promptly', async () => {
    reply = () => undefined;
    const startedAt = Date.now();

    await expect(serviceWithTimeout(SHORT_TIMEOUT_MS).verify(ACCESS_TOKEN)).rejects.toBeInstanceOf(
      ServiceUnavailableException,
    );

    expect(Date.now() - startedAt).toBeLessThan(GENEROUS_TIMEOUT_MS);
  });

  describe('createTimeoutFetch', () => {
    it('when the server never answers, then the request is aborted with a timeout error', async () => {
      reply = () => undefined;

      await expect(
        createTimeoutFetch(SHORT_TIMEOUT_MS)(`${baseUrl}${USER_PATH}`),
      ).rejects.toMatchObject({
        name: 'TimeoutError',
      });
    });

    it('when the caller aborts first, then the request is aborted with the caller reason', async () => {
      reply = () => undefined;
      const caller = new AbortController();
      const pending = createTimeoutFetch(GENEROUS_TIMEOUT_MS)(`${baseUrl}${USER_PATH}`, {
        signal: caller.signal,
      });

      caller.abort(new Error('caller gave up'));

      await expect(pending).rejects.toThrow('caller gave up');
    });
  });
});
