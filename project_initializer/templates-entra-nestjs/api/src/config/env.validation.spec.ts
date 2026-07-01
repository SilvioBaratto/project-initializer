import { validate } from './env.validation';

const VALID_CONFIG = {
  DATABASE_URL: 'postgresql://localhost:5432/test',
  DIRECT_URL: 'postgresql://localhost:5432/test',
  ENTRA_TENANT_ID: 'test-tenant-id',
  ENTRA_API_CLIENT_ID: 'test-api-client-id',
  ENTRA_API_AUDIENCE: 'api://test-api-client-id',
  ENTRA_API_SCOPE: 'access_as_user',
};

describe('validate (entra overlay)', () => {
  it('when all required vars are present, returns without throwing', () => {
    expect(() => validate(VALID_CONFIG)).not.toThrow();
  });

  it('when ENTRA_TENANT_ID is absent, throws naming ENTRA_TENANT_ID', () => {
    const { ENTRA_TENANT_ID: _, ...rest } = VALID_CONFIG;
    expect(() => validate(rest)).toThrow('ENTRA_TENANT_ID');
  });

  it('when ENTRA_API_CLIENT_ID is absent, throws naming ENTRA_API_CLIENT_ID', () => {
    const { ENTRA_API_CLIENT_ID: _, ...rest } = VALID_CONFIG;
    expect(() => validate(rest)).toThrow('ENTRA_API_CLIENT_ID');
  });

  it('when ENTRA_API_AUDIENCE is absent, throws naming ENTRA_API_AUDIENCE', () => {
    const { ENTRA_API_AUDIENCE: _, ...rest } = VALID_CONFIG;
    expect(() => validate(rest)).toThrow('ENTRA_API_AUDIENCE');
  });

  it('when ENTRA_API_SCOPE is absent, throws naming ENTRA_API_SCOPE', () => {
    const { ENTRA_API_SCOPE: _, ...rest } = VALID_CONFIG;
    expect(() => validate(rest)).toThrow('ENTRA_API_SCOPE');
  });

  it('when DATABASE_URL is absent, throws naming DATABASE_URL', () => {
    const { DATABASE_URL: _, ...rest } = VALID_CONFIG;
    expect(() => validate(rest)).toThrow('DATABASE_URL');
  });

  it('when DIRECT_URL is absent, throws naming DIRECT_URL', () => {
    const { DIRECT_URL: _, ...rest } = VALID_CONFIG;
    expect(() => validate(rest)).toThrow('DIRECT_URL');
  });

  it('when config is empty, throws with descriptive message', () => {
    expect(() => validate({})).toThrow('Invalid environment variables:');
  });

  it('when unknown keys are present, they are passed through', () => {
    const result = validate({ ...VALID_CONFIG, EXTRA_KEY: 'value' }) as Record<string, unknown>;
    expect(result.EXTRA_KEY).toBe('value');
  });

  it('when valid config is given, returned data includes default PORT 3000', () => {
    const result = validate(VALID_CONFIG) as Record<string, unknown>;
    expect(result.PORT).toBe(3000);
  });

  it('when REDIS_HOST is absent, returned data defaults to localhost', () => {
    const result = validate(VALID_CONFIG) as Record<string, unknown>;
    expect(result.REDIS_HOST).toBe('localhost');
  });

  it('when REDIS_PORT is absent, returned data defaults to 6379', () => {
    const result = validate(VALID_CONFIG) as Record<string, unknown>;
    expect(result.REDIS_PORT).toBe(6379);
  });

  it('when REDIS_PORT is provided as a string, it is coerced to a number', () => {
    const result = validate({ ...VALID_CONFIG, REDIS_PORT: '6380' }) as Record<string, unknown>;
    expect(result.REDIS_PORT).toBe(6380);
  });
});
