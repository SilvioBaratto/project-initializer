import {
  ExecutionContext,
  ForbiddenException,
  HttpException,
  Logger,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { ExecutionContextHost } from '@nestjs/core/helpers/execution-context-host';
import { Test } from '@nestjs/testing';
import { Public } from '../decorators/public.decorator';
import { ACCESS_TOKEN_VERIFIER, AccessTokenVerifier } from './access-token-verifier';
import { AccessTokenGuard } from './access-token.guard';
import {
  AUTH_PROVIDER_UNAVAILABLE_MESSAGE,
  AUTHENTICATION_REQUIRED_MESSAGE,
  INSUFFICIENT_SCOPE_MESSAGE,
  INVALID_CREDENTIALS_MESSAGE,
} from './auth-messages';
import { AuthenticatedRequest, AuthenticatedUser } from './authenticated-user';
import { MAX_BEARER_TOKEN_LENGTH } from './bearer-token';

class ProtectedController {
  handle(): void {}
}

class OpenController {
  @Public()
  handle(): void {}
}

@Public()
class OpenByClassController {
  handle(): void {}
}

type LoggerSpy = jest.SpyInstance<void, [message: unknown, ...optionalParams: unknown[]]>;

const VERIFIED_USER: AuthenticatedUser = { id: 'user-1', roles: ['reader'] };
const SECRET_TOKEN = 'secret-token-value';

function contextFor(
  headers: Record<string, string>,
  controller:
    | typeof ProtectedController
    | typeof OpenController
    | typeof OpenByClassController = ProtectedController,
  requestFields: Record<string, unknown> = { id: 'req-1' },
): { context: ExecutionContext; request: AuthenticatedRequest } {
  const request = {
    headers,
    method: 'GET',
    path: '/api/v1/items',
    ...requestFields,
  } as unknown as AuthenticatedRequest;
  const context = new ExecutionContextHost([request], controller, controller.prototype.handle);
  return { context, request };
}

/** Validates src/common/auth/access-token.guard.ts AccessTokenGuard. */
describe('AccessTokenGuard', () => {
  let guard: AccessTokenGuard;
  let verifier: { verify: jest.Mock<Promise<AuthenticatedUser>, [string]> };
  let warn: LoggerSpy;
  let error: LoggerSpy;

  beforeEach(async () => {
    verifier = {
      verify: jest.fn<Promise<AuthenticatedUser>, [string]>().mockResolvedValue(VERIFIED_USER),
    };
    const moduleRef = await Test.createTestingModule({
      providers: [
        AccessTokenGuard,
        { provide: ACCESS_TOKEN_VERIFIER, useValue: verifier satisfies AccessTokenVerifier },
      ],
    }).compile();
    guard = moduleRef.get(AccessTokenGuard);
    warn = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
    error = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('when the route is public', () => {
    it.each([
      ['the handler', OpenController],
      ['the whole controller class', OpenByClassController],
    ])(
      'then a route made public on %s passes without touching the verifier or the log',
      async (_label, controller) => {
        const { context } = contextFor({}, controller);

        await expect(guard.canActivate(context)).resolves.toBe(true);

        expect(verifier.verify).not.toHaveBeenCalled();
        expect(warn).not.toHaveBeenCalled();
      },
    );
  });

  describe('when the token verifies', () => {
    it('then the identity is attached to the request and the guard allows it', async () => {
      const { context, request } = contextFor({ authorization: `Bearer ${SECRET_TOKEN}` });

      await expect(guard.canActivate(context)).resolves.toBe(true);

      expect(request.user).toBe(VERIFIED_USER);
      expect(verifier.verify).toHaveBeenCalledWith(SECRET_TOKEN);
      expect(warn).not.toHaveBeenCalled();
    });

    it('then a lowercase scheme and surrounding blanks still reach the verifier trimmed', async () => {
      const { context } = contextFor({ authorization: `bearer   ${SECRET_TOKEN}  ` });

      await guard.canActivate(context);

      expect(verifier.verify).toHaveBeenCalledWith(SECRET_TOKEN);
    });
  });

  describe('when the request carries no usable token', () => {
    it.each([
      ['no Authorization header', {}],
      ['another scheme', { authorization: 'Basic dXNlcjpwYXNz' }],
      ['an empty bearer token', { authorization: 'Bearer ' }],
      ['a blank bearer token', { authorization: 'Bearer    ' }],
      ['an oversize token', { authorization: `Bearer ${'a'.repeat(MAX_BEARER_TOKEN_LENGTH + 1)}` }],
    ])('then %s is rejected with 401 before the verifier runs', async (_label, headers) => {
      const { context } = contextFor(headers);

      const outcome = guard.canActivate(context);

      await expect(outcome).rejects.toBeInstanceOf(UnauthorizedException);
      await expect(outcome).rejects.toMatchObject({ message: AUTHENTICATION_REQUIRED_MESSAGE });
      expect(verifier.verify).not.toHaveBeenCalled();
    });
  });

  describe('when the verifier throws an HTTP exception', () => {
    it.each([
      ['401', new UnauthorizedException(INVALID_CREDENTIALS_MESSAGE)],
      ['403', new ForbiddenException(INSUFFICIENT_SCOPE_MESSAGE)],
      ['503', new ServiceUnavailableException(AUTH_PROVIDER_UNAVAILABLE_MESSAGE)],
    ])('then the %s passes through unchanged', async (_status, exception: HttpException) => {
      verifier.verify.mockRejectedValue(exception);
      const { context } = contextFor({ authorization: `Bearer ${SECRET_TOKEN}` });

      await expect(guard.canActivate(context)).rejects.toBe(exception);

      expect(error).not.toHaveBeenCalled();
    });
  });

  describe('when the verifier throws something else', () => {
    it('then the caller sees a generic 401 and the cause is logged once with its stack', async () => {
      const cause = new TypeError('jwks client exploded');
      verifier.verify.mockRejectedValue(cause);
      const { context } = contextFor({ authorization: `Bearer ${SECRET_TOKEN}` });

      const outcome = guard.canActivate(context);

      await expect(outcome).rejects.toBeInstanceOf(UnauthorizedException);
      await expect(outcome).rejects.toMatchObject({ message: INVALID_CREDENTIALS_MESSAGE });
      expect(error).toHaveBeenCalledTimes(1);
      expect(error.mock.calls[0]).toEqual([expect.any(String), cause.stack]);
    });

    it('then a non-Error value is also reduced to a generic 401', async () => {
      verifier.verify.mockRejectedValue('plain string failure');
      const { context } = contextFor({ authorization: `Bearer ${SECRET_TOKEN}` });

      await expect(guard.canActivate(context)).rejects.toMatchObject({
        message: INVALID_CREDENTIALS_MESSAGE,
      });
      expect(error).toHaveBeenCalledWith(expect.any(String), 'plain string failure');
    });
  });

  describe('when a request is rejected', () => {
    it('then exactly one audit line records status, method, path and request id but never the token', async () => {
      verifier.verify.mockRejectedValue(new ForbiddenException());
      const { context } = contextFor({ authorization: `Bearer ${SECRET_TOKEN}` });

      await guard.canActivate(context).catch(() => undefined);

      expect(warn).toHaveBeenCalledTimes(1);
      expect(warn.mock.calls[0][0]).toMatchObject({
        status: 403,
        method: 'GET',
        path: '/api/v1/items',
        requestId: 'req-1',
      });
      expect(JSON.stringify(warn.mock.calls)).not.toContain(SECRET_TOKEN);
    });

    it('then a missing token is audited once as well', async () => {
      const { context } = contextFor({});

      await guard.canActivate(context).catch(() => undefined);

      expect(warn).toHaveBeenCalledTimes(1);
      expect(warn.mock.calls[0][0]).toMatchObject({ status: 401 });
    });

    it('then a numeric request id is logged as text', async () => {
      const { context } = contextFor({}, ProtectedController, { id: 42 });

      await guard.canActivate(context).catch(() => undefined);

      expect(warn.mock.calls[0][0]).toMatchObject({ requestId: '42' });
    });

    it.each([
      ['absent', {}],
      ['an object', { id: { value: 1 } }],
    ])('then a request id that is %s is left out of the audit line', async (_label, fields) => {
      const { context } = contextFor({}, ProtectedController, fields);

      await guard.canActivate(context).catch(() => undefined);

      expect(warn.mock.calls[0][0]).toMatchObject({ requestId: undefined });
    });
  });
});
