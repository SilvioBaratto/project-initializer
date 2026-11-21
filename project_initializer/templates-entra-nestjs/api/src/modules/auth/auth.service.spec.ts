import { generateKeyPairSync } from 'node:crypto';
import {
  ForbiddenException,
  Logger,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import type { ConfigService } from '@nestjs/config';
import * as jwt from 'jsonwebtoken';
import { JwksClient, JwksRateLimitError, SigningKeyNotFoundError } from 'jwks-rsa';
import {
  AUTH_TEST_ENV,
  TEST_ENTRA_API_AUDIENCE,
  TEST_ENTRA_API_CLIENT_ID,
  TEST_ENTRA_API_SCOPE,
  TEST_ENTRA_TENANT_ID,
} from '../../../test/support/auth-test-env';
import {
  AUTH_PROVIDER_UNAVAILABLE_MESSAGE,
  INSUFFICIENT_SCOPE_MESSAGE,
  INVALID_CREDENTIALS_MESSAGE,
} from '../../common/auth/auth-messages';
import { type Env, validate } from '../../config/env.validation';
import {
  AuthService,
  createJwksSigningKeyResolver,
  entraIssuer,
  entraJwksUri,
} from './auth.service';

jest.mock('jwks-rsa', () => ({
  ...jest.requireActual<typeof import('jwks-rsa')>('jwks-rsa'),
  JwksClient: jest.fn(),
}));

const KEY_ID = 'test-signing-key';
const RSA_MODULUS_BITS = 2048;
const TOKEN_LIFETIME_SECONDS = 3600;
const USER_OBJECT_ID = '33333333-3333-4333-8333-333333333333';
const USER_EMAIL = 'ada@example.com';
const OTHER_TENANT_ID = '44444444-4444-4444-8444-444444444444';
const OTHER_AUDIENCE = 'api://55555555-5555-4555-8555-555555555555';
const WITHIN_TOLERANCE_SECONDS = 10;
const BEYOND_TOLERANCE_SECONDS = 60;

function generateRsaKeyPair(): { publicKey: string; privateKey: string } {
  return generateKeyPairSync('rsa', {
    modulusLength: RSA_MODULUS_BITS,
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
}

const signingPair = generateRsaKeyPair();
const attackerPair = generateRsaKeyPair();
const ellipticCurvePair = generateKeyPairSync('ec', {
  namedCurve: 'P-256',
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

interface TokenSpec {
  claims?: Record<string, unknown>;
  signOptions?: jwt.SignOptions;
  /** `null` leaves the `kid` header out. */
  keyId?: string | null;
  privateKey?: string;
  /** Leaves `exp` out, which `jsonwebtoken` itself would accept. */
  withoutExpiry?: boolean;
}

function signToken(spec: TokenSpec = {}): string {
  const keyId = spec.keyId === undefined ? KEY_ID : spec.keyId;
  const expiry = spec.withoutExpiry ? {} : { expiresIn: TOKEN_LIFETIME_SECONDS };
  return jwt.sign(
    {
      tid: TEST_ENTRA_TENANT_ID,
      oid: USER_OBJECT_ID,
      scp: TEST_ENTRA_API_SCOPE,
      preferred_username: USER_EMAIL,
      roles: ['Reader'],
      ...spec.claims,
    },
    spec.privateKey ?? signingPair.privateKey,
    {
      algorithm: 'RS256',
      audience: TEST_ENTRA_API_AUDIENCE,
      issuer: entraIssuer(TEST_ENTRA_TENANT_ID),
      ...expiry,
      ...(keyId === null ? {} : { keyid: keyId }),
      ...spec.signOptions,
    },
  );
}

// Classic algorithm-confusion forgery: HMAC-sign with the RSA public key as the shared secret.
function signWithPublicKeyAsHmacSecret(): string {
  return jwt.sign({ oid: USER_OBJECT_ID, tid: TEST_ENTRA_TENANT_ID }, signingPair.publicKey, {
    algorithm: 'HS256',
    keyid: KEY_ID,
    audience: TEST_ENTRA_API_AUDIENCE,
    issuer: entraIssuer(TEST_ENTRA_TENANT_ID),
  });
}

// Same claims and `kid` as a real token, signed with another algorithm than the one Entra uses.
function signWithAlgorithm(algorithm: jwt.Algorithm, privateKey: string): string {
  return signToken({ privateKey, signOptions: { algorithm } });
}

function signUnsigned(): string {
  return jwt.sign({ oid: USER_OBJECT_ID, tid: TEST_ENTRA_TENANT_ID }, '', {
    algorithm: 'none',
    keyid: KEY_ID,
    audience: TEST_ENTRA_API_AUDIENCE,
    issuer: entraIssuer(TEST_ENTRA_TENANT_ID),
  });
}

// The service reads the validated configuration, so the stub serves what `validate` produces. It
// is a hand-rolled stub because `ConfigService` would read process.env before anything passed to it.
const validatedEnv = validate({
  DATABASE_URL: 'postgresql://localhost:5432/test',
  DIRECT_URL: 'postgresql://localhost:5432/test',
  ...AUTH_TEST_ENV,
});
const configService = {
  get: (key: keyof Env) => validatedEnv[key],
} as unknown as ConfigService<Env, true>;

async function rejection(attempt: Promise<unknown>): Promise<unknown> {
  try {
    await attempt;
  } catch (error) {
    return error;
  }
  throw new Error('Expected the promise to reject');
}

/** Validates src/modules/auth/auth.service.ts AuthService (Entra access token verification). */
describe('AuthService.verify', () => {
  const keyResolver = jest.fn<Promise<string>, [string]>();
  let errorLog: jest.SpyInstance;

  function createService(): AuthService {
    return new AuthService(configService, keyResolver);
  }

  beforeAll(() => {
    Logger.overrideLogger(false);
  });

  beforeEach(() => {
    keyResolver.mockReset();
    keyResolver.mockResolvedValue(signingPair.publicKey);
    errorLog = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('accepted tokens', () => {
    it('when the token is valid, then the identity comes from the oid, username and roles claims', async () => {
      const user = await createService().verify(signToken());

      expect(user).toEqual({ id: USER_OBJECT_ID, email: USER_EMAIL, roles: ['Reader'] });
      expect(keyResolver).toHaveBeenCalledWith(KEY_ID);
    });

    it('when aud is the client id, then the token is accepted', async () => {
      const token = signToken({ signOptions: { audience: TEST_ENTRA_API_CLIENT_ID } });

      await expect(createService().verify(token)).resolves.toMatchObject({ id: USER_OBJECT_ID });
    });

    it('when the username claim and roles are absent, then email is undefined and roles is empty', async () => {
      const token = signToken({ claims: { preferred_username: undefined, roles: undefined } });

      await expect(createService().verify(token)).resolves.toEqual({
        id: USER_OBJECT_ID,
        email: undefined,
        roles: [],
      });
    });

    it('when the username is an address the strict grammar refuses, then it is still returned', async () => {
      const token = signToken({ claims: { preferred_username: 'first!last@example.com' } });

      const user = await createService().verify(token);

      expect(user.email).toBe('first!last@example.com');
    });

    it('when the username claim is not an email address, then email is undefined', async () => {
      const token = signToken({ claims: { preferred_username: 'not-an-email' } });

      const user = await createService().verify(token);

      expect(user.email).toBeUndefined();
    });
  });

  describe('clock tolerance', () => {
    it.each([
      ['expired a few seconds ago', { expiresIn: -WITHIN_TOLERANCE_SECONDS }],
      ['valid only a few seconds from now', { notBefore: WITHIN_TOLERANCE_SECONDS }],
    ])('when the token is %s, then it is still accepted', async (_label, signOptions) => {
      const token = signToken({ signOptions });

      await expect(createService().verify(token)).resolves.toMatchObject({ id: USER_OBJECT_ID });
    });
  });

  describe('tokens rejected before any key lookup', () => {
    const forgedTokens: ReadonlyArray<[string, string]> = [
      ['is not a JWT', 'not-a-jwt'],
      ['is an HS256 token keyed with the public key', signWithPublicKeyAsHmacSecret()],
      ['declares alg none', signUnsigned()],
      ['has no kid header', signToken({ keyId: null })],
      ['is signed with RS512', signWithAlgorithm('RS512', signingPair.privateKey)],
      ['is signed with PS256', signWithAlgorithm('PS256', signingPair.privateKey)],
      ['is signed with ES256', signWithAlgorithm('ES256', ellipticCurvePair.privateKey)],
    ];

    it.each(forgedTokens)(
      'when the token %s, then it is rejected with 401 and no key is fetched',
      async (_label, token) => {
        const error = await rejection(createService().verify(token));

        expect(error).toBeInstanceOf(UnauthorizedException);
        expect(error).toHaveProperty('message', INVALID_CREDENTIALS_MESSAGE);
        expect(keyResolver).not.toHaveBeenCalled();
      },
    );
  });

  describe('tokens rejected after the key lookup', () => {
    const invalidTokens: ReadonlyArray<[string, string]> = [
      ['is expired', signToken({ signOptions: { expiresIn: -TOKEN_LIFETIME_SECONDS } })],
      ['has the wrong audience', signToken({ signOptions: { audience: OTHER_AUDIENCE } })],
      [
        'has the wrong issuer',
        signToken({ signOptions: { issuer: entraIssuer(OTHER_TENANT_ID) } }),
      ],
      ['is signed with another key', signToken({ privateKey: attackerPair.privateKey })],
      ['has no oid claim', signToken({ claims: { oid: undefined } })],
      ['has an oid that is not a GUID', signToken({ claims: { oid: 'user-1' } })],
      ['has a tid of another tenant', signToken({ claims: { tid: OTHER_TENANT_ID } })],
      ['has no exp claim', signToken({ withoutExpiry: true })],
      ['has no iat claim', signToken({ signOptions: { noTimestamp: true } })],
      [
        'expired beyond the clock tolerance',
        signToken({ signOptions: { expiresIn: -BEYOND_TOLERANCE_SECONDS } }),
      ],
      [
        'is not valid yet beyond the clock tolerance',
        signToken({ signOptions: { notBefore: BEYOND_TOLERANCE_SECONDS } }),
      ],
    ];

    it.each(invalidTokens)(
      'when the token %s, then it is rejected with the generic 401',
      async (_label, token) => {
        const error = await rejection(createService().verify(token));

        expect(error).toBeInstanceOf(UnauthorizedException);
        expect(error).toHaveProperty('message', INVALID_CREDENTIALS_MESSAGE);
      },
    );
  });

  describe('signing key retrieval', () => {
    it('when the kid is unknown, then the token is rejected with 401', async () => {
      keyResolver.mockRejectedValue(new SigningKeyNotFoundError('no key for kid'));

      const error = await rejection(createService().verify(signToken()));

      expect(error).toBeInstanceOf(UnauthorizedException);
      expect(error).toHaveProperty('message', INVALID_CREDENTIALS_MESSAGE);
    });

    it.each([
      ['the key set cannot be fetched', new Error('connect ECONNREFUSED')],
      ['the refetch rate limit is reached', new JwksRateLimitError('Too many requests')],
      ['the resolver rejects with something that is not an Error', 'connection reset'],
    ])(
      'when %s, then 503 carries the cause and the verifier logs nothing',
      async (_label, cause) => {
        keyResolver.mockRejectedValue(cause);

        const error = await rejection(createService().verify(signToken()));

        expect(error).toBeInstanceOf(ServiceUnavailableException);
        expect(error).not.toBeInstanceOf(UnauthorizedException);
        expect(error).toHaveProperty('message', AUTH_PROVIDER_UNAVAILABLE_MESSAGE);
        expect(error).toHaveProperty('cause', cause);
        expect(errorLog).not.toHaveBeenCalled();
      },
    );
  });

  describe('required scope', () => {
    it('when scp lacks the required scope, then the token is rejected with 403', async () => {
      const token = signToken({ claims: { scp: 'Files.Read' } });

      const error = await rejection(createService().verify(token));

      expect(error).toBeInstanceOf(ForbiddenException);
      expect(error).toHaveProperty('message', INSUFFICIENT_SCOPE_MESSAGE);
    });

    it('when scp is absent, then the token is rejected with 403', async () => {
      const token = signToken({ claims: { scp: undefined } });

      await expect(createService().verify(token)).rejects.toBeInstanceOf(ForbiddenException);
    });

    it('when scp only contains a longer scope name, then the token is rejected with 403', async () => {
      const token = signToken({ claims: { scp: `${TEST_ENTRA_API_SCOPE}_admin` } });

      await expect(createService().verify(token)).rejects.toBeInstanceOf(ForbiddenException);
    });

    it('when scp lists several scopes including the required one, then the token is accepted', async () => {
      const token = signToken({ claims: { scp: `Files.Read ${TEST_ENTRA_API_SCOPE}` } });

      await expect(createService().verify(token)).resolves.toMatchObject({ id: USER_OBJECT_ID });
    });
  });
});

describe('Entra authority URLs', () => {
  it('when a tenant id is given, then the issuer is its v2.0 authority', () => {
    expect(entraIssuer(TEST_ENTRA_TENANT_ID)).toBe(
      `https://login.microsoftonline.com/${TEST_ENTRA_TENANT_ID}/v2.0`,
    );
  });

  it('when a tenant id is given, then the key set lives under the same authority', () => {
    expect(entraJwksUri(TEST_ENTRA_TENANT_ID)).toBe(
      `https://login.microsoftonline.com/${TEST_ENTRA_TENANT_ID}/discovery/v2.0/keys`,
    );
  });
});

describe('createJwksSigningKeyResolver', () => {
  const getSigningKey = jest.fn<Promise<{ getPublicKey(): string }>, [string]>();

  beforeEach(() => {
    getSigningKey.mockReset();
    jest.mocked(JwksClient).mockReset();
    jest.mocked(JwksClient).mockImplementation(() => ({ getSigningKey }) as unknown as JwksClient);
  });

  it('when the resolver is created, then keys are cached for a day and each fetch is bounded', () => {
    createJwksSigningKeyResolver(TEST_ENTRA_TENANT_ID);

    expect(JwksClient).toHaveBeenCalledWith({
      jwksUri: entraJwksUri(TEST_ENTRA_TENANT_ID),
      cache: true,
      cacheMaxAge: 24 * 60 * 60 * 1000,
      rateLimit: true,
      timeout: 5_000,
    });
  });

  it('when the key id is known, then the PEM public key is returned', async () => {
    getSigningKey.mockResolvedValue({ getPublicKey: () => signingPair.publicKey });

    const publicKey = await createJwksSigningKeyResolver(TEST_ENTRA_TENANT_ID)(KEY_ID);

    expect(publicKey).toBe(signingPair.publicKey);
    expect(getSigningKey).toHaveBeenCalledWith(KEY_ID);
  });

  it('when the key id is unknown, then the not-found error reaches the caller', async () => {
    getSigningKey.mockRejectedValue(new SigningKeyNotFoundError('no key for kid'));

    await expect(createJwksSigningKeyResolver(TEST_ENTRA_TENANT_ID)(KEY_ID)).rejects.toBeInstanceOf(
      SigningKeyNotFoundError,
    );
  });
});
