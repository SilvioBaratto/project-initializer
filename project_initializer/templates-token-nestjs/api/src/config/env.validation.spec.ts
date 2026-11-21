import { MIN_AUTH_TOKEN_LENGTH, validate } from './env.validation';

const VALID_ENV = {
  DATABASE_URL: 'postgresql://localhost:5432/test',
  DIRECT_URL: 'postgresql://localhost:5432/test',
  AUTH_TOKEN: 'a'.repeat(MIN_AUTH_TOKEN_LENGTH),
};

function failureMessage(config: Record<string, unknown>): string {
  try {
    validate(config);
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
  throw new Error('validate accepted a configuration that should have failed');
}

/** Validates src/config/env.validation.ts for the token variant's AUTH_TOKEN rule. */
describe('validate (token variant)', () => {
  it('when AUTH_TOKEN has the minimum length, then the environment is accepted', () => {
    expect(validate(VALID_ENV).AUTH_TOKEN).toBe(VALID_ENV.AUTH_TOKEN);
  });

  it('when NODE_ENV is production and DATABASE_URL has no sslmode, then it is refused', () => {
    expect(failureMessage({ ...VALID_ENV, NODE_ENV: 'production' })).toContain(
      'DATABASE_URL must carry sslmode',
    );
  });

  it('when AUTH_TOKEN is one character short, then validation fails naming the minimum', () => {
    const tooShort = 'a'.repeat(MIN_AUTH_TOKEN_LENGTH - 1);

    expect(failureMessage({ ...VALID_ENV, AUTH_TOKEN: tooShort })).toContain(
      `AUTH_TOKEN: AUTH_TOKEN must be at least ${MIN_AUTH_TOKEN_LENGTH} characters`,
    );
  });

  it('when AUTH_TOKEN is the legacy placeholder, then validation fails', () => {
    expect(failureMessage({ ...VALID_ENV, AUTH_TOKEN: 'changeme' })).toContain('AUTH_TOKEN');
  });

  it.each([
    ['absent', undefined],
    ['empty', ''],
  ])('when AUTH_TOKEN is %s, then validation fails naming AUTH_TOKEN', (_label, value) => {
    expect(failureMessage({ ...VALID_ENV, AUTH_TOKEN: value })).toContain('AUTH_TOKEN');
  });

  it.each([
    ['base64url characters', `${'aB3-_'.repeat(8)}`],
    ['base64 characters with padding', `${'aB3+/'.repeat(8)}==`],
    ['token68 punctuation', `${'a.b~c'.repeat(8)}`],
  ])('when AUTH_TOKEN is made of %s, then it is accepted', (_label, secret) => {
    expect(validate({ ...VALID_ENV, AUTH_TOKEN: secret }).AUTH_TOKEN).toBe(secret);
  });

  it.each([
    ['a blank inside', `${'a'.repeat(MIN_AUTH_TOKEN_LENGTH)} ${'b'.repeat(MIN_AUTH_TOKEN_LENGTH)}`],
    ['a leading blank', ` ${'a'.repeat(MIN_AUTH_TOKEN_LENGTH)}`],
    ['a trailing newline', `${'a'.repeat(MIN_AUTH_TOKEN_LENGTH)}\n`],
    ['a non-ASCII letter', `${'a'.repeat(MIN_AUTH_TOKEN_LENGTH)}é`],
    ['an equals sign before the end', `${'a'.repeat(MIN_AUTH_TOKEN_LENGTH)}=a`],
    ['a quote', `${'a'.repeat(MIN_AUTH_TOKEN_LENGTH)}"`],
  ])(
    'when AUTH_TOKEN has %s, then validation fails because no client could send it',
    (_label, secret) => {
      expect(failureMessage({ ...VALID_ENV, AUTH_TOKEN: secret })).toContain(
        'AUTH_TOKEN: AUTH_TOKEN must contain only',
      );
    },
  );

  it('when AUTH_TOKEN is rejected, then the error does not echo the secret', () => {
    const rejectedSecret = 'too-short-secret';

    expect(failureMessage({ ...VALID_ENV, AUTH_TOKEN: rejectedSecret })).not.toContain(
      rejectedSecret,
    );
  });

  it('when a base variable is invalid, then the base rules still apply', () => {
    expect(failureMessage({ ...VALID_ENV, DATABASE_URL: 'not-a-url' })).toContain('DATABASE_URL');
  });
});
