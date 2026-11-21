import { Logger, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Test } from '@nestjs/testing';
import { INVALID_CREDENTIALS_MESSAGE } from '../../common/auth/auth-messages';
import {
  AuthService,
  TOKEN_ACCEPTED_MESSAGE,
  TOKEN_CLIENT,
  TOKEN_REJECTED_MESSAGE,
} from './auth.service';

const CONFIGURED_TOKEN = 'configured-secret-with-more-than-32-characters';

async function createService(configuredToken: string): Promise<AuthService> {
  const moduleRef = await Test.createTestingModule({
    providers: [AuthService, { provide: ConfigService, useValue: { get: () => configuredToken } }],
  }).compile();
  return moduleRef.get(AuthService);
}

/** Validates src/modules/auth/auth.service.ts AuthService for the token variant. */
describe('AuthService', () => {
  let service: AuthService;
  let warn: jest.SpyInstance;

  beforeEach(async () => {
    service = await createService(CONFIGURED_TOKEN);
    warn = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('verify', () => {
    it('when the token matches the configured secret, then the service identity is returned', async () => {
      await expect(service.verify(CONFIGURED_TOKEN)).resolves.toBe(TOKEN_CLIENT);
    });

    it.each([
      ['a same-length mismatch', 'x'.repeat(CONFIGURED_TOKEN.length)],
      ['a shorter token', CONFIGURED_TOKEN.slice(0, -1)],
      ['a longer token', `${CONFIGURED_TOKEN}!`],
      ['the secret with different case', CONFIGURED_TOKEN.toUpperCase()],
      ['an empty token', ''],
    ])('when the token is %s, then it is rejected with 401', async (_label, candidate) => {
      const outcome = service.verify(candidate);

      await expect(outcome).rejects.toBeInstanceOf(UnauthorizedException);
      await expect(outcome).rejects.toMatchObject({ message: INVALID_CREDENTIALS_MESSAGE });
    });

    it('when a multibyte secret is configured, then only the identical string matches', async () => {
      const multibyteService = await createService('sécret-日本語-🔐-0123456789abcdef');

      await expect(multibyteService.verify('sécret-日本語-🔐-0123456789abcdef')).resolves.toBe(
        TOKEN_CLIENT,
      );
      await expect(multibyteService.verify('secret-日本語-🔐-0123456789abcdef')).rejects.toThrow(
        UnauthorizedException,
      );
    });

    it('when the secret differs only in Unicode normalisation, then it is rejected', async () => {
      const composed = 'café-secret-0123456789abcdef-0123456789';
      const decomposed = 'café-secret-0123456789abcdef-0123456789';
      const normalisingService = await createService(composed);

      await expect(normalisingService.verify(decomposed)).rejects.toThrow(UnauthorizedException);
    });

    it('when the token is rejected, then the service itself writes no log line', async () => {
      await service.verify('wrong').catch(() => undefined);

      expect(warn).not.toHaveBeenCalled();
    });
  });

  describe('validateToken', () => {
    it('when the token matches, then the answer is authenticated and nothing is logged', () => {
      expect(service.validateToken(CONFIGURED_TOKEN)).toEqual({
        authenticated: true,
        message: TOKEN_ACCEPTED_MESSAGE,
      });
      expect(warn).not.toHaveBeenCalled();
    });

    it('when the token does not match, then the answer is not authenticated', () => {
      expect(service.validateToken('wrong')).toEqual({
        authenticated: false,
        message: TOKEN_REJECTED_MESSAGE,
      });
    });

    it('when the token does not match, then one audit line is written without token material', () => {
      const attempt = 'attempted-secret-value';

      service.validateToken(attempt);

      expect(warn).toHaveBeenCalledTimes(1);
      const logged = JSON.stringify(warn.mock.calls);
      expect(logged).not.toContain(attempt);
      expect(logged).not.toContain(CONFIGURED_TOKEN);
    });

    it('when the token is empty, then it is answered as not authenticated without throwing', () => {
      expect(service.validateToken('').authenticated).toBe(false);
    });
  });
});
