import {
  AUTH_TEST_ENV,
  TEST_ENTRA_API_AUDIENCE,
  TEST_ENTRA_API_CLIENT_ID,
  TEST_ENTRA_API_SCOPE,
  TEST_ENTRA_TENANT_ID,
} from '../../test/support/auth-test-env';
import { validate } from './env.validation';

const VALID_CONFIG: Record<string, unknown> = {
  DATABASE_URL: 'postgresql://localhost:5432/test',
  DIRECT_URL: 'postgresql://localhost:5432/test',
  ...AUTH_TEST_ENV,
};

// The ids in the shared fixtures are all digits, which no case change would alter.
const MIXED_CASE_GUID = 'ABCDEF12-3456-4789-8ABC-DEF012345678';

const REQUIRED_ENTRA_KEYS = [
  'ENTRA_TENANT_ID',
  'ENTRA_API_CLIENT_ID',
  'ENTRA_API_AUDIENCE',
  'ENTRA_API_SCOPE',
];

function without(config: Record<string, unknown>, key: string): Record<string, unknown> {
  return Object.fromEntries(Object.entries(config).filter(([name]) => name !== key));
}

/** Validates src/config/env.validation.ts for the Entra variant's keys. */
describe('validate (entra overlay)', () => {
  it('when all required variables are present, then the Entra identifiers are returned', () => {
    const validated = validate(VALID_CONFIG);

    expect(validated.ENTRA_TENANT_ID).toBe(TEST_ENTRA_TENANT_ID);
    expect(validated.ENTRA_API_SCOPE).toBe(TEST_ENTRA_API_SCOPE);
  });

  it('when NODE_ENV is production and DATABASE_URL has no sslmode, then it is refused', () => {
    expect(() => validate({ ...VALID_CONFIG, NODE_ENV: 'production' })).toThrow(
      'DATABASE_URL must carry sslmode',
    );
  });

  it.each(REQUIRED_ENTRA_KEYS)('when %s is absent, then validation throws naming it', (key) => {
    expect(() => validate(without(VALID_CONFIG, key))).toThrow(key);
  });

  it('when ENTRA_TENANT_ID is not a GUID, then validation throws naming it', () => {
    expect(() => validate({ ...VALID_CONFIG, ENTRA_TENANT_ID: 'your-tenant-id' })).toThrow(
      'ENTRA_TENANT_ID',
    );
  });

  it('when ENTRA_API_CLIENT_ID is not a GUID, then validation throws naming it', () => {
    expect(() => validate({ ...VALID_CONFIG, ENTRA_API_CLIENT_ID: 'your-api-client-id' })).toThrow(
      'ENTRA_API_CLIENT_ID',
    );
  });

  it('when ENTRA_API_AUDIENCE is empty, then validation throws naming it', () => {
    expect(() => validate({ ...VALID_CONFIG, ENTRA_API_AUDIENCE: '' })).toThrow(
      'ENTRA_API_AUDIENCE',
    );
  });

  it.each(['ENTRA_TENANT_ID', 'ENTRA_API_CLIENT_ID'] as const)(
    'when %s is written in uppercase, then it is lowercased to match the issuer and tid claims',
    (key) => {
      const validated = validate({ ...VALID_CONFIG, [key]: MIXED_CASE_GUID });

      expect(validated[key]).toBe(MIXED_CASE_GUID.toLowerCase());
    },
  );

  describe('ENTRA_API_SCOPE', () => {
    it.each([
      ['the full URI the portal shows', `${TEST_ENTRA_API_AUDIENCE}/${TEST_ENTRA_API_SCOPE}`],
      ['a bare name with blanks around it', `  ${TEST_ENTRA_API_SCOPE}  `],
    ])('when it is %s, then the bare scope name is validated', (_label, configured) => {
      expect(validate({ ...VALID_CONFIG, ENTRA_API_SCOPE: configured }).ENTRA_API_SCOPE).toBe(
        TEST_ENTRA_API_SCOPE,
      );
    });

    it.each([
      ['empty', ''],
      ['blank', '   '],
      ['a URI that ends in a slash', `api://${TEST_ENTRA_API_CLIENT_ID}/`],
    ])('when it is %s, then validation throws naming it', (_label, configured) => {
      expect(() => validate({ ...VALID_CONFIG, ENTRA_API_SCOPE: configured })).toThrow(
        'ENTRA_API_SCOPE: ENTRA_API_SCOPE must name a scope',
      );
    });
  });

  it('when a base variable is absent, then validation still throws naming it', () => {
    expect(() => validate(without(VALID_CONFIG, 'DATABASE_URL'))).toThrow('DATABASE_URL');
  });

  it('when POSTGRES_* variables are present, then they are not part of the validated config', () => {
    const validated = validate({ ...VALID_CONFIG, POSTGRES_HOST: 'db', POSTGRES_PASSWORD: 'pw' });

    expect(validated).not.toHaveProperty('POSTGRES_HOST');
    expect(validated).not.toHaveProperty('POSTGRES_PASSWORD');
  });
});
