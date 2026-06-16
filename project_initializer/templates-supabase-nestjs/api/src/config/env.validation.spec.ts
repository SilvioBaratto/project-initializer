import { validate } from './env.validation';

const VALID_CONFIG = {
  DATABASE_URL: 'postgresql://localhost:5432/test',
  DIRECT_URL: 'postgresql://localhost:5432/test',
  SUPABASE_URL: 'https://your-project.supabase.co',
  SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test_key',
};

describe('validate (supabase overlay)', () => {
  it('when all required vars are present, returns without throwing', () => {
    expect(() => validate(VALID_CONFIG)).not.toThrow();
  });

  it('when SUPABASE_URL is absent, throws naming SUPABASE_URL', () => {
    const { SUPABASE_URL: _, ...rest } = VALID_CONFIG;
    expect(() => validate(rest)).toThrow('SUPABASE_URL');
  });

  it('when SUPABASE_URL is not a valid URL, throws', () => {
    expect(() => validate({ ...VALID_CONFIG, SUPABASE_URL: 'not-a-url' })).toThrow();
  });

  it('when SUPABASE_PUBLISHABLE_KEY is absent, throws naming SUPABASE_PUBLISHABLE_KEY', () => {
    const { SUPABASE_PUBLISHABLE_KEY: _, ...rest } = VALID_CONFIG;
    expect(() => validate(rest)).toThrow('SUPABASE_PUBLISHABLE_KEY');
  });

  it('when SUPABASE_PUBLISHABLE_KEY is empty string, throws', () => {
    expect(() => validate({ ...VALID_CONFIG, SUPABASE_PUBLISHABLE_KEY: '' })).toThrow();
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

  it('when SUPABASE_SECRET_KEY is absent, returns without throwing', () => {
    expect(() => validate(VALID_CONFIG)).not.toThrow();
  });

  it('when SUPABASE_SECRET_KEY is provided, returns without throwing', () => {
    expect(() =>
      validate({ ...VALID_CONFIG, SUPABASE_SECRET_KEY: 'sb_secret_key' }),
    ).not.toThrow();
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
