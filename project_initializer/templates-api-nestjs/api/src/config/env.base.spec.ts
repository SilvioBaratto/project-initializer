/** Validates src/config/env.base.ts: baseEnvSchema, createEnvValidator and blankToUndefined. */
import { z } from 'zod';
import {
  baseEnvSchema,
  blankToUndefined,
  createEnvValidator,
  ENCRYPTED_DATABASE_SSLMODES,
  MIN_QUEUE_MONITOR_PASSWORD_LENGTH,
} from './env.base';

const validate = createEnvValidator(baseEnvSchema);

const VALID_BASE = {
  DATABASE_URL: 'postgresql://localhost:5432/test',
  DIRECT_URL: 'postgresql://localhost:5432/test',
};

const MAX_TCP_PORT = 65_535;

describe('validate (required keys)', () => {
  it('when DATABASE_URL and DIRECT_URL are present, then it returns without throwing', () => {
    expect(() => validate(VALID_BASE)).not.toThrow();
  });

  it('when DATABASE_URL is absent, then it throws naming DATABASE_URL', () => {
    expect(() => validate({ DIRECT_URL: VALID_BASE.DIRECT_URL })).toThrow('DATABASE_URL');
  });

  it('when DIRECT_URL is absent, then it throws naming DIRECT_URL', () => {
    expect(() => validate({ DATABASE_URL: VALID_BASE.DATABASE_URL })).toThrow('DIRECT_URL');
  });

  it('when DATABASE_URL is an empty string, then it throws', () => {
    expect(() => validate({ ...VALID_BASE, DATABASE_URL: '' })).toThrow('DATABASE_URL');
  });

  it('when DATABASE_URL is not a Postgres URL, then it throws', () => {
    expect(() => validate({ ...VALID_BASE, DATABASE_URL: 'mysql://localhost:3306/test' })).toThrow(
      'DATABASE_URL',
    );
  });

  it('when DATABASE_URL uses the postgres scheme with pooler options, then it is accepted', () => {
    const pooled = 'postgres://user.ref:secret@pooler.example.com:6543/postgres?pgbouncer=true';

    expect(validate({ ...VALID_BASE, DATABASE_URL: pooled }).DATABASE_URL).toBe(pooled);
  });

  it('when the config is empty, then the message starts with the descriptive prefix', () => {
    expect(() => validate({})).toThrow('Invalid environment variables:');
  });

  it('when several keys are invalid, then every failing key is named', () => {
    expect(() => validate({ PORT: '0' })).toThrow(/DATABASE_URL.*DIRECT_URL.*PORT/);
  });

  it('when a value is rejected, then the message does not repeat it', () => {
    const credential = 'hunter2-secret';

    let message = '';
    try {
      validate({ ...VALID_BASE, DATABASE_URL: `mysql://user:${credential}@host/db` });
    } catch (error) {
      message = error instanceof Error ? error.message : '';
    }

    expect(message).toContain('DATABASE_URL');
    expect(message).not.toContain(credential);
  });
});

describe('validate (defaults and coercion)', () => {
  it('when only the required keys are set, then the documented defaults apply', () => {
    expect(validate(VALID_BASE)).toMatchObject({
      PORT: 3000,
      NODE_ENV: 'development',
      REDIS_HOST: 'localhost',
      REDIS_PORT: 6379,
      CORS_ORIGINS: ['http://localhost:4200'],
      LOG_LEVEL: 'info',
      QUEUE_MONITOR_USER: 'admin',
      DB_CONNECT_TIMEOUT_MS: 5000,
      DB_QUERY_TIMEOUT_MS: 15000,
      DB_POOL_MAX: 10,
      DB_BREAKER_FAILURE_THRESHOLD: 5,
      DB_BREAKER_RESET_MS: 30000,
      HEALTH_HEAP_READINESS_MB: 300,
      HEALTH_HEAP_LIVENESS_MB: 512,
      TRUST_PROXY_HOPS: 1,
      DB_ALLOW_INSECURE_TRANSPORT: false,
    });
  });

  it('when API_DOCS_ENABLED is not set, then it stays undefined so the environment decides', () => {
    expect(validate(VALID_BASE).API_DOCS_ENABLED).toBeUndefined();
  });

  it('when PORT is a numeric string, then it is coerced to a number', () => {
    expect(validate({ ...VALID_BASE, PORT: '4000' }).PORT).toBe(4000);
  });

  it('when REDIS_PORT is a numeric string, then it is coerced to a number', () => {
    expect(validate({ ...VALID_BASE, REDIS_PORT: '6380' }).REDIS_PORT).toBe(6380);
  });

  it('when unknown keys are present, then they are dropped from the result', () => {
    const validated = validate({ ...VALID_BASE, EXTRA_KEY: 'value' });

    expect(validated).not.toHaveProperty('EXTRA_KEY');
  });
});

describe('validate (ports)', () => {
  it.each([['0'], ['-1'], [String(MAX_TCP_PORT + 1)], ['3.5'], ['abc'], ['']])(
    'when PORT is %j, then it throws naming PORT',
    (port) => {
      expect(() => validate({ ...VALID_BASE, PORT: port })).toThrow('PORT');
    },
  );

  it.each([['1'], [String(MAX_TCP_PORT)]])('when PORT is %j, then it is accepted', (port) => {
    expect(validate({ ...VALID_BASE, PORT: port }).PORT).toBe(Number(port));
  });

  it('when REDIS_PORT is out of range, then it throws naming REDIS_PORT', () => {
    expect(() => validate({ ...VALID_BASE, REDIS_PORT: '70000' })).toThrow('REDIS_PORT');
  });
});

describe('validate (NODE_ENV and LOG_LEVEL)', () => {
  it('when NODE_ENV is not a known mode, then it throws naming NODE_ENV', () => {
    expect(() => validate({ ...VALID_BASE, NODE_ENV: 'staging' })).toThrow('NODE_ENV');
  });

  it.each([
    ['WARN', 'warn'],
    [' Debug ', 'debug'],
    ['silent', 'silent'],
    ['FATAL', 'fatal'],
  ])('when LOG_LEVEL is %j, then it validates as %j', (raw, expected) => {
    expect(validate({ ...VALID_BASE, LOG_LEVEL: raw }).LOG_LEVEL).toBe(expected);
  });

  it('when LOG_LEVEL is not a pino level, then it throws naming LOG_LEVEL', () => {
    expect(() => validate({ ...VALID_BASE, LOG_LEVEL: 'loud' })).toThrow('LOG_LEVEL');
  });
});

describe('validate (TRUST_PROXY_HOPS and API_DOCS_ENABLED)', () => {
  it.each([
    ['0', 0],
    ['1', 1],
    ['10', 10],
  ])('when TRUST_PROXY_HOPS is %j, then it is accepted as %i', (raw, expected) => {
    expect(validate({ ...VALID_BASE, TRUST_PROXY_HOPS: raw }).TRUST_PROXY_HOPS).toBe(expected);
  });

  it.each([['-1'], ['11'], ['1.5'], ['abc']])(
    'when TRUST_PROXY_HOPS is %j, then it throws naming it',
    (raw) => {
      expect(() => validate({ ...VALID_BASE, TRUST_PROXY_HOPS: raw })).toThrow('TRUST_PROXY_HOPS');
    },
  );

  it.each([
    ['true', true],
    ['false', false],
    ['1', true],
    ['0', false],
  ])('when API_DOCS_ENABLED is %j, then it validates as %s', (raw, expected) => {
    expect(validate({ ...VALID_BASE, API_DOCS_ENABLED: raw }).API_DOCS_ENABLED).toBe(expected);
  });

  it('when API_DOCS_ENABLED is blank, then it is treated as not set', () => {
    expect(validate({ ...VALID_BASE, API_DOCS_ENABLED: '' }).API_DOCS_ENABLED).toBeUndefined();
  });

  it('when API_DOCS_ENABLED is not a boolean word, then it throws naming it', () => {
    expect(() => validate({ ...VALID_BASE, API_DOCS_ENABLED: 'maybe' })).toThrow(
      'API_DOCS_ENABLED',
    );
  });
});

describe('validate (CORS_ORIGINS)', () => {
  it('when origins are comma separated with stray spaces, then they are split and trimmed', () => {
    const validated = validate({
      ...VALID_BASE,
      CORS_ORIGINS: 'http://a.example.com, https://b.example.com:4200 ,',
    });

    expect(validated.CORS_ORIGINS).toEqual(['http://a.example.com', 'https://b.example.com:4200']);
  });

  it('when an origin is written with a path or a trailing slash, then it is reduced to the bare origin the browser sends', () => {
    const validated = validate({
      ...VALID_BASE,
      CORS_ORIGINS: 'http://a.example.com/, https://b.example.com:4200/app/index.html',
    });

    expect(validated.CORS_ORIGINS).toEqual(['http://a.example.com', 'https://b.example.com:4200']);
  });

  it('when the same origin is listed twice in different spellings, then it appears once', () => {
    const validated = validate({
      ...VALID_BASE,
      CORS_ORIGINS: 'http://a.example.com,http://a.example.com/',
    });

    expect(validated.CORS_ORIGINS).toEqual(['http://a.example.com']);
  });

  it.each([['localhost:4200'], ['ftp://files.example.com'], ['file:///tmp/x']])(
    'when an origin is %j, which is not an http(s) URL, then it throws',
    (origin) => {
      expect(() => validate({ ...VALID_BASE, CORS_ORIGINS: origin })).toThrow('CORS_ORIGINS');
    },
  );

  it('when an origin is not a URL, then it throws naming CORS_ORIGINS', () => {
    expect(() => validate({ ...VALID_BASE, CORS_ORIGINS: 'http://a.example.com,nope' })).toThrow(
      'CORS_ORIGINS',
    );
  });

  it('when the list is blank, then it throws because CORS would block every browser', () => {
    expect(() => validate({ ...VALID_BASE, CORS_ORIGINS: ' , ' })).toThrow('CORS_ORIGINS');
  });
});

describe('validate (queue dashboard credentials)', () => {
  it('when the password is blank, then it is treated as not set', () => {
    expect(validate({ ...VALID_BASE, QUEUE_MONITOR_PASSWORD: '' }).QUEUE_MONITOR_PASSWORD).toBe(
      undefined,
    );
  });

  it('when the password is one character short of the minimum, then it throws', () => {
    const tooShort = 'x'.repeat(MIN_QUEUE_MONITOR_PASSWORD_LENGTH - 1);

    expect(() => validate({ ...VALID_BASE, QUEUE_MONITOR_PASSWORD: tooShort })).toThrow(
      'QUEUE_MONITOR_PASSWORD',
    );
  });

  it('when the password has exactly the minimum length, then it is accepted', () => {
    const atMinimum = 'x'.repeat(MIN_QUEUE_MONITOR_PASSWORD_LENGTH);

    expect(
      validate({ ...VALID_BASE, QUEUE_MONITOR_PASSWORD: atMinimum }).QUEUE_MONITOR_PASSWORD,
    ).toBe(atMinimum);
  });

  it('when the user is blank, then it throws naming QUEUE_MONITOR_USER', () => {
    expect(() => validate({ ...VALID_BASE, QUEUE_MONITOR_USER: '' })).toThrow('QUEUE_MONITOR_USER');
  });
});

describe('validate (resilience and health numbers)', () => {
  it.each([
    'DB_CONNECT_TIMEOUT_MS',
    'DB_QUERY_TIMEOUT_MS',
    'DB_POOL_MAX',
    'DB_BREAKER_FAILURE_THRESHOLD',
    'DB_BREAKER_RESET_MS',
    'HEALTH_HEAP_READINESS_MB',
    'HEALTH_HEAP_LIVENESS_MB',
  ])('when %s is not a positive integer, then it throws naming it', (key) => {
    expect(() => validate({ ...VALID_BASE, [key]: '0' })).toThrow(key);
    expect(() => validate({ ...VALID_BASE, [key]: '1.5' })).toThrow(key);
  });

  it('when a timeout is overridden with a numeric string, then it is coerced', () => {
    expect(validate({ ...VALID_BASE, DB_QUERY_TIMEOUT_MS: '2500' }).DB_QUERY_TIMEOUT_MS).toBe(2500);
  });
});

describe('validate (database transport in production)', () => {
  const PASSWORD = 'tls-test-password-7731';
  const PRODUCTION = { NODE_ENV: 'production' };

  function withUrl(databaseUrl: string, extra: Record<string, unknown> = {}) {
    return { ...VALID_BASE, ...PRODUCTION, DATABASE_URL: databaseUrl, ...extra };
  }

  function errorMessageOf(config: Record<string, unknown>): string {
    try {
      validate(config);
    } catch (error) {
      return error instanceof Error ? error.message : '';
    }
    return '';
  }

  it.each([...ENCRYPTED_DATABASE_SSLMODES])(
    'when production uses sslmode=%s, then the URL is accepted',
    (sslmode) => {
      const databaseUrl = `postgresql://app:${PASSWORD}@db.example.com:5432/app?sslmode=${sslmode}&schema=public`;

      expect(validate(withUrl(databaseUrl)).DATABASE_URL).toBe(databaseUrl);
    },
  );

  it('when production has no sslmode, then it throws naming DATABASE_URL and the opt-out', () => {
    const message = errorMessageOf(withUrl(`postgresql://app:${PASSWORD}@db.example.com/app`));

    expect(message).toContain('DATABASE_URL must carry sslmode');
    expect(message).toContain('DB_ALLOW_INSECURE_TRANSPORT');
  });

  it.each([['disable'], ['allow'], ['prefer'], ['REQUIRE'], ['']])(
    'when production uses sslmode=%j, then it throws because the link is not encrypted',
    (sslmode) => {
      const databaseUrl = `postgresql://app:${PASSWORD}@db.example.com/app?sslmode=${sslmode}`;

      expect(() => validate(withUrl(databaseUrl))).toThrow('DATABASE_URL must carry sslmode');
    },
  );

  it('when production repeats sslmode with one unencrypted value, then it throws', () => {
    const databaseUrl = 'postgresql://app@db.example.com/app?sslmode=require&sslmode=disable';

    expect(() => validate(withUrl(databaseUrl))).toThrow('DATABASE_URL must carry sslmode');
  });

  it('when the URL is refused, then the message holds neither the password nor the host', () => {
    const message = errorMessageOf(
      withUrl(`postgresql://app:${PASSWORD}@secret-host.example.com/app?sslmode=disable`),
    );

    expect(message).not.toContain(PASSWORD);
    expect(message).not.toContain('secret-host');
  });

  it.each([['true'], ['1'], ['yes']])(
    'when DB_ALLOW_INSECURE_TRANSPORT is %j, then a plaintext URL is accepted in production',
    (optOut) => {
      const databaseUrl = 'postgresql://app:pw@db:5432/app?schema=public';

      const validated = validate(withUrl(databaseUrl, { DB_ALLOW_INSECURE_TRANSPORT: optOut }));

      expect(validated.DB_ALLOW_INSECURE_TRANSPORT).toBe(true);
    },
  );

  it.each([['false'], ['0'], ['']])(
    'when DB_ALLOW_INSECURE_TRANSPORT is %j, then a plaintext URL is still refused',
    (optOut) => {
      const config = withUrl('postgresql://app:pw@db:5432/app', {
        DB_ALLOW_INSECURE_TRANSPORT: optOut,
      });

      expect(() => validate(config)).toThrow('DB_ALLOW_INSECURE_TRANSPORT');
    },
  );

  it('when DB_ALLOW_INSECURE_TRANSPORT is not a boolean word, then it throws naming it', () => {
    const config = withUrl('postgresql://app@db/app?sslmode=require', {
      DB_ALLOW_INSECURE_TRANSPORT: 'maybe',
    });

    expect(() => validate(config)).toThrow('DB_ALLOW_INSECURE_TRANSPORT');
  });

  it.each([['development'], ['test']])(
    'when NODE_ENV is %s, then a URL without sslmode is accepted',
    (nodeEnv) => {
      const config = { ...VALID_BASE, NODE_ENV: nodeEnv };

      expect(validate(config).DB_ALLOW_INSECURE_TRANSPORT).toBe(false);
    },
  );

  it('when NODE_ENV is absent, then the development default applies and the rule stays off', () => {
    expect(() => validate(VALID_BASE)).not.toThrow();
  });

  it('when production has an invalid DATABASE_URL, then only the URL rule reports it', () => {
    const message = errorMessageOf(withUrl('mysql://app:pw@db/app'));

    expect(message).toContain('DATABASE_URL');
    expect(message).not.toContain('sslmode');
  });

  it('when an overlay extends the base schema, then the production rule still applies', () => {
    const overlayValidate = createEnvValidator(baseEnvSchema.extend({ OVERLAY_KEY: z.string() }));

    expect(() => overlayValidate(withUrl('postgresql://app@db/app', { OVERLAY_KEY: 'x' }))).toThrow(
      'DATABASE_URL must carry sslmode',
    );
  });
});

describe('createEnvValidator', () => {
  const overlayValidate = createEnvValidator(
    baseEnvSchema.extend({ OVERLAY_KEY: z.string().min(1) }),
  );

  it('when an overlay extends the base schema, then its own keys are required too', () => {
    expect(() => overlayValidate(VALID_BASE)).toThrow('OVERLAY_KEY');
  });

  it('when an overlay key is present, then base and overlay keys are both returned', () => {
    const validated = overlayValidate({ ...VALID_BASE, OVERLAY_KEY: 'present' });

    expect(validated).toMatchObject({ OVERLAY_KEY: 'present', PORT: 3000 });
  });

  it('when a root-level check fails, then the issue is reported under the root label', () => {
    const rootCheck = createEnvValidator(
      z.object({}).refine(() => false, { error: 'root rule broken' }),
    );

    expect(() => rootCheck({})).toThrow('(root): root rule broken');
  });
});

describe('blankToUndefined', () => {
  it('when the value is an empty string, then it becomes undefined', () => {
    expect(blankToUndefined('')).toBeUndefined();
  });

  it.each([['value'], [' '], [0], [null]])('when the value is %j, then it is unchanged', (raw) => {
    expect(blankToUndefined(raw)).toBe(raw);
  });
});
