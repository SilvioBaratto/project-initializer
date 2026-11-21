import {
  AUTH_TEST_ENV,
  TEST_SUPABASE_PUBLISHABLE_KEY,
  TEST_SUPABASE_URL,
} from '../../test/support/auth-test-env';
import { validate } from './env.validation';

const VALID_CONFIG: Record<string, unknown> = {
  DATABASE_URL: 'postgresql://localhost:5432/test',
  DIRECT_URL: 'postgresql://localhost:5432/test',
  ...AUTH_TEST_ENV,
};

// The shape `.env` generation writes for a Supabase project: the transaction pooler with TLS.
const SUPABASE_POOLER_URL =
  'postgresql://postgres.ref:secret@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?pgbouncer=true&connection_limit=20&schema=public&sslmode=require';

const PRODUCTION_CONFIG: Record<string, unknown> = {
  ...VALID_CONFIG,
  NODE_ENV: 'production',
  DATABASE_URL: SUPABASE_POOLER_URL,
};

function without(config: Record<string, unknown>, key: string): Record<string, unknown> {
  return Object.fromEntries(Object.entries(config).filter(([name]) => name !== key));
}

/** Validates src/config/env.validation.ts for the Supabase variant's keys. */
describe('validate (supabase overlay)', () => {
  it('when all required variables are present, then the Supabase settings are returned', () => {
    const validated = validate(VALID_CONFIG);

    expect(validated.SUPABASE_URL).toBe(TEST_SUPABASE_URL);
    expect(validated.SUPABASE_PUBLISHABLE_KEY).toBe(TEST_SUPABASE_PUBLISHABLE_KEY);
  });

  it.each(['SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'DATABASE_URL', 'DIRECT_URL'])(
    'when %s is absent, then validation throws naming it',
    (key) => {
      expect(() => validate(without(VALID_CONFIG, key))).toThrow(key);
    },
  );

  it.each(['not-a-url', 'ftp://project.supabase.co'])(
    'when SUPABASE_URL is %j, then validation throws naming it',
    (invalidUrl) => {
      expect(() => validate({ ...VALID_CONFIG, SUPABASE_URL: invalidUrl })).toThrow('SUPABASE_URL');
    },
  );

  describe('SUPABASE_URL scheme', () => {
    const LOCAL_CLI_URL = 'http://127.0.0.1:54321';

    it.each(['development', 'test'])(
      'when NODE_ENV is %s, then the plain-http URL of the local Supabase CLI is accepted',
      (nodeEnv) => {
        const validated = validate({
          ...VALID_CONFIG,
          NODE_ENV: nodeEnv,
          SUPABASE_URL: LOCAL_CLI_URL,
        });

        expect(validated.SUPABASE_URL).toBe(LOCAL_CLI_URL);
      },
    );

    it('when NODE_ENV is production, then an https URL is accepted', () => {
      expect(() => validate(PRODUCTION_CONFIG)).not.toThrow();
    });

    it('when NODE_ENV is production, then a plain-http URL is refused naming SUPABASE_URL', () => {
      expect(() => validate({ ...PRODUCTION_CONFIG, SUPABASE_URL: LOCAL_CLI_URL })).toThrow(
        'SUPABASE_URL: SUPABASE_URL must use https',
      );
    });
  });

  describe('database transport', () => {
    it('when NODE_ENV is production and the pooler URL has no sslmode, then it is refused', () => {
      const plaintextUrl = SUPABASE_POOLER_URL.replace('&sslmode=require', '');

      expect(() => validate({ ...PRODUCTION_CONFIG, DATABASE_URL: plaintextUrl })).toThrow(
        'DATABASE_URL must carry sslmode',
      );
    });
  });

  it('when SUPABASE_PUBLISHABLE_KEY is empty, then validation throws naming it', () => {
    expect(() => validate({ ...VALID_CONFIG, SUPABASE_PUBLISHABLE_KEY: '' })).toThrow(
      'SUPABASE_PUBLISHABLE_KEY',
    );
  });

  it('when SUPABASE_SECRET_KEY is present, then it is not part of the validated config', () => {
    const validated = validate({ ...VALID_CONFIG, SUPABASE_SECRET_KEY: 'placeholder-value' });

    expect(validated).not.toHaveProperty('SUPABASE_SECRET_KEY');
  });
});
