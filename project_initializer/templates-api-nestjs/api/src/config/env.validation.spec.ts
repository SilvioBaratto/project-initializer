import { validate } from './env.validation';

const VALID_BASE = {
  DATABASE_URL: 'postgresql://localhost:5432/test',
  DIRECT_URL: 'postgresql://localhost:5432/test',
};

describe('validate', () => {
  it('when DATABASE_URL and DIRECT_URL are present, returns without throwing', () => {
    expect(() => validate(VALID_BASE)).not.toThrow();
  });

  it('when DATABASE_URL is absent, throws naming DATABASE_URL', () => {
    const { DATABASE_URL: _, ...rest } = VALID_BASE;
    expect(() => validate(rest)).toThrow('DATABASE_URL');
  });

  it('when DATABASE_URL is empty string, throws', () => {
    expect(() => validate({ ...VALID_BASE, DATABASE_URL: '' })).toThrow();
  });

  it('when DIRECT_URL is absent, throws naming DIRECT_URL', () => {
    const { DIRECT_URL: _, ...rest } = VALID_BASE;
    expect(() => validate(rest)).toThrow('DIRECT_URL');
  });

  it('when config is empty, throws with descriptive message', () => {
    expect(() => validate({})).toThrow('Invalid environment variables:');
  });

  it('when config is valid, returned data includes default PORT 3000', () => {
    const result = validate(VALID_BASE) as Record<string, unknown>;
    expect(result.PORT).toBe(3000);
  });

  it('when PORT is provided, returned data reflects it', () => {
    const result = validate({ ...VALID_BASE, PORT: '4000' }) as Record<string, unknown>;
    expect(result.PORT).toBe(4000);
  });

  it('when REDIS_HOST is absent, returned data defaults to localhost', () => {
    const result = validate(VALID_BASE) as Record<string, unknown>;
    expect(result.REDIS_HOST).toBe('localhost');
  });

  it('when REDIS_PORT is absent, returned data defaults to 6379', () => {
    const result = validate(VALID_BASE) as Record<string, unknown>;
    expect(result.REDIS_PORT).toBe(6379);
  });

  it('when REDIS_PORT is provided as a string, it is coerced to a number', () => {
    const result = validate({ ...VALID_BASE, REDIS_PORT: '6380' }) as Record<string, unknown>;
    expect(result.REDIS_PORT).toBe(6380);
  });

  it('when unknown keys are present, they are passed through', () => {
    const result = validate({ ...VALID_BASE, EXTRA_KEY: 'value' }) as Record<string, unknown>;
    expect(result.EXTRA_KEY).toBe('value');
  });
});
