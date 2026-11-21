import { extractBearerToken, MAX_BEARER_TOKEN_LENGTH } from './bearer-token';

/** Validates src/common/auth/bearer-token.ts extractBearerToken. */
describe('extractBearerToken', () => {
  it('when the header is a bearer credential, then the token is returned', () => {
    expect(extractBearerToken('Bearer abc.def.ghi')).toBe('abc.def.ghi');
  });

  it.each(['bearer abc', 'BEARER abc', 'BeArEr abc'])(
    'when the scheme is written as %j, then it is accepted case-insensitively',
    (header) => {
      expect(extractBearerToken(header)).toBe('abc');
    },
  );

  it('when blanks surround the token, then they are trimmed', () => {
    expect(extractBearerToken('Bearer \t abc  ')).toBe('abc');
  });

  it.each([undefined, '', 'Bearer', 'Bearer ', 'Bearer    ', 'Bearer\t'])(
    'when the header is %j, then there is no token',
    (header) => {
      expect(extractBearerToken(header)).toBeNull();
    },
  );

  it.each(['Basic abc', 'Token abc', 'Bearerabc', 'abc', 'Bearer a b'])(
    'when the header is %j, then it is not a single bearer credential',
    (header) => {
      expect(extractBearerToken(header)).toBeNull();
    },
  );

  it('when the header is repeated, then no token is chosen', () => {
    expect(extractBearerToken(['Bearer a', 'Bearer b'])).toBeNull();
  });

  it('when the token has exactly the maximum length, then it is accepted', () => {
    const token = 'a'.repeat(MAX_BEARER_TOKEN_LENGTH);

    expect(extractBearerToken(`Bearer ${token}`)).toBe(token);
  });

  it('when the token is one character over the maximum, then it is rejected', () => {
    const token = 'a'.repeat(MAX_BEARER_TOKEN_LENGTH + 1);

    expect(extractBearerToken(`Bearer ${token}`)).toBeNull();
  });
});
