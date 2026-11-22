/** Validates src/app.setup.ts: configureApp, setupOpenApi and readPackageVersion. */
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import type { Server } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  Body,
  Controller,
  Get,
  INestApplication,
  Post,
  Req,
  StandardSchemaValidationPipe,
} from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { APP_GUARD, APP_PIPE } from '@nestjs/core';
import { Test } from '@nestjs/testing';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { Prisma } from '@generated/prisma';
import type { Request } from 'express';
import { Logger, LoggerModule } from 'nestjs-pino';
import request from 'supertest';
import { z } from 'zod';
import {
  API_PREFIX,
  CORS_ALLOWED_HEADERS,
  CORS_EXPOSED_HEADERS,
  CORS_MAX_AGE_SECONDS,
  CORS_METHODS,
  configureApp,
  isOpenApiEnabled,
  readPackageVersion,
  setupOpenApi,
} from './app.setup';
import { INTERNAL_ERROR_MESSAGE, ROUTE_NOT_FOUND_MESSAGE } from './common/filters/error-body';
import { MALFORMED_JSON_MESSAGE } from './common/filters/malformed-json.middleware';
import { SchemaValidationException } from './common/filters/schema-validation.exception';
import { validate } from './config/env.validation';
import { MAX_REQUEST_BODY_BYTES } from './config/http-limits';
import { buildLoggerParams } from './config/logger.config';
import {
  GLOBAL_REQUESTS_PER_WINDOW,
  RATE_LIMIT_EXCEEDED_MESSAGE,
  THROTTLER_MODULE_OPTIONS,
} from './config/rate-limit';

const ALLOWED_ORIGIN = 'http://localhost:4200';
const FOREIGN_ORIGIN = 'http://untrusted.example.com';
const PROBE_BASE = `/${API_PREFIX}/probe`;

const ProbeBodySchema = z.object({ name: z.string().min(1) });
type ProbeBody = z.infer<typeof ProbeBodySchema>;

@Controller('probe')
class ProbeController {
  @Get('ok')
  ok(): { ok: boolean } {
    return { ok: true };
  }

  @Get('duplicate')
  duplicate(): never {
    throw new Prisma.PrismaClientKnownRequestError('raw text with email column', {
      code: 'P2002',
      clientVersion: 'test',
      meta: { target: ['email'] },
    });
  }

  @Get('crash')
  crash(): never {
    throw new Error('internal detail that must stay server side');
  }

  @Post('named')
  named(@Body({ schema: ProbeBodySchema }) body: ProbeBody): ProbeBody {
    return body;
  }

  @Get('client-ip')
  clientIp(@Req() incoming: Request): { ip: string | undefined } {
    return { ip: incoming.ip };
  }
}

function httpServerOf(app: INestApplication): Server {
  return app.getHttpServer() as Server;
}

interface ProbeAppOptions {
  /** Environment keys layered over the test defaults, as strings like a real environment. */
  env?: Record<string, string>;
  /** Registers the production rate limiter as the app-wide guard. */
  rateLimited?: boolean;
}

async function createProbeApp(options: ProbeAppOptions = {}): Promise<INestApplication> {
  const moduleRef = await Test.createTestingModule({
    imports: [
      ConfigModule.forRoot({
        isGlobal: true,
        ignoreEnvFile: true,
        validate: (raw) => validate({ ...raw, ...options.env }),
      }),
      LoggerModule.forRoot(buildLoggerParams({ level: 'silent', pretty: false })),
      ...(options.rateLimited ? [ThrottlerModule.forRoot(THROTTLER_MODULE_OPTIONS)] : []),
    ],
    controllers: [ProbeController],
    providers: [
      {
        provide: APP_PIPE,
        useFactory: () =>
          new StandardSchemaValidationPipe({
            exceptionFactory: (issues) => new SchemaValidationException(issues),
          }),
      },
      ...(options.rateLimited ? [{ provide: APP_GUARD, useClass: ThrottlerGuard }] : []),
    ],
  }).compile();
  return moduleRef.createNestApplication();
}

async function startProbeApp(options: ProbeAppOptions = {}): Promise<INestApplication> {
  const app = await createProbeApp(options);
  configureApp(app);
  await app.init();
  return app;
}

describe('configureApp', () => {
  let app: INestApplication;

  beforeAll(async () => {
    app = await startProbeApp();
  });

  afterAll(async () => {
    await app.close();
  });

  describe('routing', () => {
    it('when a route is called under the api prefix, then it is served', async () => {
      const response = await request(httpServerOf(app)).get(`${PROBE_BASE}/ok`);

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ ok: true });
    });

    it('when a route is called without the prefix, then it is not found', async () => {
      const response = await request(httpServerOf(app)).get('/probe/ok');

      expect(response.status).toBe(404);
    });

    it('when the root path is called, then no welcome route answers', async () => {
      const response = await request(httpServerOf(app)).get('/');

      expect(response.status).toBe(404);
    });
  });

  describe('security headers', () => {
    it('when any route answers, then helmet headers are present and the framework is not announced', async () => {
      const response = await request(httpServerOf(app)).get(`${PROBE_BASE}/ok`);

      expect(response.headers['x-content-type-options']).toBe('nosniff');
      expect(response.headers['x-powered-by']).toBeUndefined();
    });
  });

  describe('CORS', () => {
    it('when a preflight comes from an allowed origin, then methods, headers and max age are granted', async () => {
      const response = await request(httpServerOf(app))
        .options(`${PROBE_BASE}/ok`)
        .set('Origin', ALLOWED_ORIGIN)
        .set('Access-Control-Request-Method', 'PUT');

      expect(response.headers['access-control-allow-origin']).toBe(ALLOWED_ORIGIN);
      expect(response.headers['access-control-allow-credentials']).toBe('true');
      expect(response.headers['access-control-allow-methods']).toBe(CORS_METHODS.join(','));
      expect(response.headers['access-control-allow-headers']).toBe(CORS_ALLOWED_HEADERS.join(','));
      expect(response.headers['access-control-max-age']).toBe(String(CORS_MAX_AGE_SECONDS));
    });

    it('when a request comes from an origin that is not listed, then no CORS grant is given', async () => {
      const response = await request(httpServerOf(app))
        .get(`${PROBE_BASE}/ok`)
        .set('Origin', FOREIGN_ORIGIN);

      expect(response.headers['access-control-allow-origin']).toBeUndefined();
    });

    it('when an allowed origin calls a route, then the request id and rate-limit headers are exposed', async () => {
      const response = await request(httpServerOf(app))
        .get(`${PROBE_BASE}/ok`)
        .set('Origin', ALLOWED_ORIGIN);

      expect(response.headers['access-control-expose-headers']).toBe(
        CORS_EXPOSED_HEADERS.join(','),
      );
    });
  });

  describe('error filters', () => {
    it('when a handler throws a Prisma unique-constraint error, then the specific filter answers 409', async () => {
      const response = await request(httpServerOf(app)).get(`${PROBE_BASE}/duplicate`);

      expect(response.status).toBe(409);
      expect(response.body).toMatchObject({
        statusCode: 409,
        error: 'Conflict',
        message: 'Resource already exists',
        path: `${PROBE_BASE}/duplicate`,
      });
      expect(JSON.stringify(response.body)).not.toContain('email');
    });

    it('when a handler throws an unexpected error, then the catch-all answers a fixed 500', async () => {
      const response = await request(httpServerOf(app)).get(`${PROBE_BASE}/crash`);

      expect(response.status).toBe(500);
      expect(response.body).toMatchObject({ message: INTERNAL_ERROR_MESSAGE });
      expect(JSON.stringify(response.body)).not.toContain('internal detail');
    });

    it('when a body fails validation, then the answer is a 400 listing the failing field', async () => {
      const response = await request(httpServerOf(app))
        .post(`${PROBE_BASE}/named`)
        .send({ name: '' });

      expect(response.status).toBe(400);
      expect(response.body).toMatchObject({
        message: 'Validation failed',
        errors: [{ path: 'name', message: 'Too small: expected string to have >=1 characters' }],
      });
    });

    it('when the route does not exist, then the body has the shared shape', async () => {
      const response = await request(httpServerOf(app)).get(`${PROBE_BASE}/missing`);

      expect(response.status).toBe(404);
      expect(response.body).toMatchObject({ statusCode: 404, error: 'Not Found' });
    });

    it('when an unknown path is called with a query string, then the 404 message does not echo it', async () => {
      const response = await request(httpServerOf(app)).get(`${PROBE_BASE}/missing?token=secret`);

      expect(response.body).toHaveProperty('message', ROUTE_NOT_FOUND_MESSAGE);
      expect(JSON.stringify(response.body)).not.toContain('secret');
    });

    it('when the URL carries a query string, then the body path leaves it out', async () => {
      const response = await request(httpServerOf(app)).get(`${PROBE_BASE}/crash?token=secret`);

      expect(response.body).toHaveProperty('path', `${PROBE_BASE}/crash`);
    });
  });

  describe('request bodies', () => {
    const OVERSIZE_BYTES = MAX_REQUEST_BODY_BYTES + 1_024;
    // A valid body far beyond Express's 100 kB default but under the raised limit.
    const LARGE_VALID_NAME_LENGTH = 160 * 1_024;

    it('when a valid body is well above the Express default, then it is accepted', async () => {
      const response = await request(httpServerOf(app))
        .post(`${PROBE_BASE}/named`)
        .send({ name: 'x'.repeat(LARGE_VALID_NAME_LENGTH) });

      expect(response.status).toBe(201);
    });

    it('when the body exceeds the limit, then the answer is a generic 413 and not a 500', async () => {
      const response = await request(httpServerOf(app))
        .post(`${PROBE_BASE}/named`)
        .set('Origin', ALLOWED_ORIGIN)
        .send({ name: 'x'.repeat(OVERSIZE_BYTES) });

      expect(response.status).toBe(413);
      expect(response.body).toMatchObject({
        statusCode: 413,
        error: 'Payload Too Large',
        message: 'Payload Too Large',
        path: `${PROBE_BASE}/named`,
      });
      expect(response.headers['access-control-allow-origin']).toBe(ALLOWED_ORIGIN);
      expect(JSON.stringify(response.body)).not.toContain('request entity too large');
    });

    it('when the body declares a charset the parser refuses, then the answer is a generic 415 that does not echo the header', async () => {
      const response = await request(httpServerOf(app))
        .post(`${PROBE_BASE}/named`)
        .set('Content-Type', 'application/json; charset=iso-8859-1')
        .send('{"name":"x"}');

      expect(response.status).toBe(415);
      expect(response.body).toMatchObject({
        statusCode: 415,
        error: 'Unsupported Media Type',
        message: 'Unsupported Media Type',
        path: `${PROBE_BASE}/named`,
      });
      expect(JSON.stringify(response.body)).not.toMatch(/iso-8859-1|charset/i);
    });

    it('when the body is malformed JSON, then the answer is a 400 that does not echo the parser text', async () => {
      const response = await request(httpServerOf(app))
        .post(`${PROBE_BASE}/named`)
        .set('Content-Type', 'application/json')
        .send('{"name": "oops", }');

      expect(response.status).toBe(400);
      expect(response.body).toMatchObject({ statusCode: 400, message: MALFORMED_JSON_MESSAGE });
      expect(JSON.stringify(response.body)).not.toContain('oops');
      expect(JSON.stringify(response.body)).not.toMatch(/token|position/i);
    });
  });

  describe('client address behind a proxy', () => {
    const REAL_CLIENT = '203.0.113.7';

    async function clientIpSeenBehind(
      hops: string | undefined,
      forwardedFor: string,
    ): Promise<string | undefined> {
      const proxied = await startProbeApp(
        hops === undefined ? {} : { env: { TRUST_PROXY_HOPS: hops } },
      );
      const response = await request(httpServerOf(proxied))
        .get(`${PROBE_BASE}/client-ip`)
        .set('X-Forwarded-For', forwardedFor);
      await proxied.close();
      return (response.body as { ip?: string }).ip;
    }

    it('when one proxy is trusted by default, then the address it appended is the client', async () => {
      await expect(clientIpSeenBehind(undefined, `10.9.9.9, ${REAL_CLIENT}`)).resolves.toBe(
        REAL_CLIENT,
      );
    });

    it('when no proxy is trusted, then a forwarded address is ignored', async () => {
      const seen = await clientIpSeenBehind('0', REAL_CLIENT);

      expect(seen).not.toContain(REAL_CLIENT);
    });
  });

  describe('request id', () => {
    it('when the client sends a valid id, then the error body and the header both carry it', async () => {
      const response = await request(httpServerOf(app))
        .get(`${PROBE_BASE}/crash`)
        .set('X-Request-Id', 'client-id-1');

      expect(response.headers['x-request-id']).toBe('client-id-1');
      expect(response.body).toHaveProperty('requestId', 'client-id-1');
    });

    it('when the client sends an id with illegal characters, then a generated id is used instead', async () => {
      const response = await request(httpServerOf(app))
        .get(`${PROBE_BASE}/crash`)
        .set('X-Request-Id', 'not valid!');

      expect(response.headers['x-request-id']).not.toBe('not valid!');
      expect(response.body).toHaveProperty('requestId', response.headers['x-request-id']);
    });
  });
});

describe('rate limiting behind a proxy', () => {
  let app: INestApplication;

  beforeAll(async () => {
    app = await startProbeApp({ rateLimited: true });
  });

  afterAll(async () => {
    await app.close();
  });

  const getFrom = (client: string) =>
    request(httpServerOf(app)).get(`${PROBE_BASE}/ok`).set('X-Forwarded-For', client);

  it('when one client exceeds the limit, then it gets 429 with the fixed message and another client is unaffected', async () => {
    const BUSY_CLIENT = '198.51.100.1';
    const OTHER_CLIENT = '198.51.100.2';
    for (let sent = 0; sent < GLOBAL_REQUESTS_PER_WINDOW; sent += 1) {
      await getFrom(BUSY_CLIENT).expect(200);
    }

    const limited = await getFrom(BUSY_CLIENT);
    const other = await getFrom(OTHER_CLIENT);

    expect(limited.status).toBe(429);
    expect(limited.body).toMatchObject({
      statusCode: 429,
      error: 'Too Many Requests',
      message: RATE_LIMIT_EXCEEDED_MESSAGE,
    });
    expect(other.status).toBe(200);
  });
});

describe('isOpenApiEnabled', () => {
  it.each([
    ['development', undefined, true],
    ['test', undefined, true],
    ['production', undefined, false],
    ['production', true, true],
    ['development', false, false],
  ] as const)(
    'when NODE_ENV is %s and API_DOCS_ENABLED is %s, then the UI is published: %s',
    (nodeEnv, flag, expected) => {
      expect(isOpenApiEnabled({ NODE_ENV: nodeEnv, API_DOCS_ENABLED: flag })).toBe(expected);
    },
  );
});

describe('configureApp (wiring)', () => {
  it('when applied, then the pino logger replaces the default one and shutdown hooks are enabled', async () => {
    const app = await createProbeApp();
    const useLogger = jest.spyOn(app, 'useLogger');
    const enableShutdownHooks = jest.spyOn(app, 'enableShutdownHooks');

    configureApp(app);

    expect(useLogger).toHaveBeenCalledWith(app.get(Logger));
    expect(enableShutdownHooks).toHaveBeenCalledTimes(1);
    await app.close();
  });
});

describe('setupOpenApi', () => {
  async function documentFor(bearerAuthRequired: boolean): Promise<Record<string, unknown>> {
    const app = await createProbeApp();
    configureApp(app);
    setupOpenApi(app, { version: '9.8.7', bearerAuthRequired });
    await app.init();
    const response = await request(httpServerOf(app)).get('/docs-json');
    await app.close();
    return response.body as Record<string, unknown>;
  }

  it('when the variant is protected, then the document requires a bearer token globally', async () => {
    const document = await documentFor(true);

    expect(document).toMatchObject({
      info: { version: '9.8.7' },
      security: [{ bearer: [] }],
      components: { securitySchemes: { bearer: { type: 'http', scheme: 'bearer' } } },
    });
  });

  it('when the variant has no auth, then the document declares no global requirement', async () => {
    const document = await documentFor(false);

    expect(document).not.toHaveProperty('security');
  });
});

describe('readPackageVersion', () => {
  let scratchDir: string;

  beforeEach(() => {
    scratchDir = mkdtempSync(join(tmpdir(), 'app-setup-spec-'));
  });

  afterEach(() => {
    rmSync(scratchDir, { recursive: true, force: true });
  });

  function manifest(contents: string): string {
    const manifestPath = join(scratchDir, 'package.json');
    writeFileSync(manifestPath, contents);
    return manifestPath;
  }

  it('when the manifest declares a version, then it is returned', () => {
    expect(readPackageVersion(manifest('{"name":"api","version":"3.2.1"}'))).toBe('3.2.1');
  });

  it('when no path is given, then the manifest of the working directory is read', () => {
    expect(readPackageVersion()).toMatch(/^\d+\.\d+\.\d+/);
  });

  it.each([
    ['the version is missing', '{"name":"api"}'],
    ['the version is empty', '{"version":""}'],
    ['the version is not a string', '{"version":3}'],
    ['the file is not JSON', 'not json'],
  ])('when %s, then it throws', (_label, contents) => {
    expect(() => readPackageVersion(manifest(contents))).toThrow();
  });

  it('when the file does not exist, then it throws', () => {
    expect(() => readPackageVersion(join(scratchDir, 'absent.json'))).toThrow();
  });
});
