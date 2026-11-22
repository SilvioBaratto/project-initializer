/** Validates src/config/logger.config.ts: normalizeLogLevel, resolveRequestId and buildLoggerParams. */
import { IncomingMessage, ServerResponse } from 'node:http';
import type { Server } from 'node:http';
import { Socket } from 'node:net';
import { Controller, Get, HttpException, INestApplication, Res } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import type { Response } from 'express';
import { LoggerModule } from 'nestjs-pino';
import request from 'supertest';
import { API_PREFIX } from '../app.setup';
import {
  accessLogLevel,
  buildLoggerParams,
  DEFAULT_LOG_LEVEL,
  LOG_LEVELS,
  normalizeLogLevel,
  REQUEST_ID_HEADER,
  resolveRequestId,
  serializeRequest,
} from './logger.config';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const MAX_VALID_ID_LENGTH = 64;

function requestWithRequestId(value?: string): { req: IncomingMessage; res: ServerResponse } {
  const req = new IncomingMessage(new Socket());
  if (value !== undefined) {
    req.headers[REQUEST_ID_HEADER] = value;
  }
  return { req, res: new ServerResponse(req) };
}

describe('normalizeLogLevel', () => {
  it.each([
    ['INFO', 'info'],
    ['Warn', 'warn'],
    ['  debug  ', 'debug'],
    ['silent', 'silent'],
  ])('when the raw level is %j, then it normalises to %j', (raw, expected) => {
    expect(normalizeLogLevel(raw)).toBe(expected);
  });

  it('when the result is normalised again, then it does not change', () => {
    const once = normalizeLogLevel(' TRACE ');

    expect(normalizeLogLevel(once)).toBe(once);
  });

  it('when the default level is read, then it is part of the vocabulary', () => {
    expect(LOG_LEVELS).toContain(DEFAULT_LOG_LEVEL);
    expect(DEFAULT_LOG_LEVEL).toBe('info');
  });
});

describe('resolveRequestId', () => {
  it('when the incoming id is well formed, then it is kept and echoed on the response', () => {
    const { req, res } = requestWithRequestId('client-id_42');

    expect(resolveRequestId(req, res)).toBe('client-id_42');
    expect(res.getHeader(REQUEST_ID_HEADER)).toBe('client-id_42');
  });

  it('when the incoming id is exactly 64 characters, then it is kept', () => {
    const boundaryId = 'a'.repeat(MAX_VALID_ID_LENGTH);
    const { req, res } = requestWithRequestId(boundaryId);

    expect(resolveRequestId(req, res)).toBe(boundaryId);
  });

  it.each([
    ['too long', 'a'.repeat(MAX_VALID_ID_LENGTH + 1)],
    ['empty', ''],
    ['containing a space', 'two words'],
    ['containing a log-forging newline', 'abc\nlevel=fatal'],
    ['a comma-joined repeated header', 'first-id, second-id'],
  ])('when the incoming id is %s, then a fresh UUID replaces it', (_label, hostileId) => {
    const { req, res } = requestWithRequestId(hostileId);

    const requestId = resolveRequestId(req, res);

    expect(requestId).toMatch(UUID_PATTERN);
    expect(res.getHeader(REQUEST_ID_HEADER)).toBe(requestId);
  });

  it('when no id is sent, then a UUID is generated and echoed on the response', () => {
    const { req, res } = requestWithRequestId();

    const requestId = resolveRequestId(req, res);

    expect(requestId).toMatch(UUID_PATTERN);
    expect(res.getHeader(REQUEST_ID_HEADER)).toBe(requestId);
  });
});

describe('serializeRequest', () => {
  it('when the URL has a query string, then only the path is kept', () => {
    expect(
      serializeRequest({ id: 'r1', method: 'GET', url: '/api/v1/items?token=secret&q=a' }),
    ).toEqual({
      id: 'r1',
      method: 'GET',
      path: '/api/v1/items',
    });
  });

  it('when the URL has no query string, then it is the path', () => {
    expect(serializeRequest({ id: 'r1', method: 'GET', url: '/api/v1/items' }).path).toBe(
      '/api/v1/items',
    );
  });

  it('when the request carries no URL, then the path is empty rather than a thrown error', () => {
    expect(serializeRequest({}).path).toBe('');
  });
});

describe('accessLogLevel', () => {
  function respondedWith(statusCode: number): ServerResponse {
    const res = new ServerResponse(new IncomingMessage(new Socket()));
    res.statusCode = statusCode;
    return res;
  }
  const req = new IncomingMessage(new Socket());

  it.each([
    [200, 'info'],
    [404, 'info'],
    [429, 'info'],
    [500, 'warn'],
    [503, 'warn'],
  ])('when the response status is %i, then the access line is logged at %s', (status, level) => {
    expect(accessLogLevel(req, respondedWith(status))).toBe(level);
  });

  it('when the response ended with an error, then the access line is a warning', () => {
    expect(accessLogLevel(req, respondedWith(200), new Error('aborted'))).toBe('warn');
  });
});

describe('buildLoggerParams', () => {
  it('when built, then the level and the request-id generator are passed to pino', () => {
    const { pinoHttp } = buildLoggerParams({ level: 'warn', pretty: false });

    expect(pinoHttp).toHaveProperty('level', 'warn');
    expect(pinoHttp).toHaveProperty('genReqId', resolveRequestId);
  });

  it('when pretty output is on, then pino-pretty is configured as the transport', () => {
    const { pinoHttp } = buildLoggerParams({ level: 'debug', pretty: true });

    expect(pinoHttp).toHaveProperty('transport.target', 'pino-pretty');
  });

  it('when pretty output is off, then no transport is configured', () => {
    const { pinoHttp } = buildLoggerParams({ level: 'info', pretty: false });

    expect(pinoHttp).not.toHaveProperty('transport');
  });

  it('when built, then the routes are left to the nestjs-pino default', () => {
    expect(buildLoggerParams({ level: 'info', pretty: false })).not.toHaveProperty('forRoutes');
  });
});

@Controller('logged')
class LoggedController {
  @Get('ok')
  ok(@Res({ passthrough: true }) res: Response): { ok: boolean } {
    res.cookie('session', 'cookie-secret-value');
    return { ok: true };
  }

  @Get('boom')
  boom(): never {
    throw new HttpException('unavailable', 503);
  }
}

describe('what a request writes to the log', () => {
  const BEARER_SECRET = 'bearer-secret-value';
  const COOKIE_SECRET = 'cookie-secret-value';
  const QUERY_SECRET = 'query-secret-value';
  const PREFIX_ROOT = `/${API_PREFIX}`;
  let app: INestApplication;
  let lines: Array<Record<string, unknown>>;

  beforeAll(async () => {
    lines = [];
    const destination = {
      write: (line: string): void => {
        lines.push(JSON.parse(line) as Record<string, unknown>);
      },
    };
    const moduleRef = await Test.createTestingModule({
      imports: [
        LoggerModule.forRoot(buildLoggerParams({ level: 'info', pretty: false, destination })),
      ],
      controllers: [LoggedController],
    }).compile();
    app = moduleRef.createNestApplication();
    // As in configureApp: the routes the logger middleware covers are derived from the prefix.
    app.setGlobalPrefix(API_PREFIX);
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(() => {
    lines.length = 0;
  });

  async function accessLineOf(path: string): Promise<Record<string, unknown>> {
    await request(app.getHttpServer() as Server)
      .get(path)
      .set('Authorization', `Bearer ${BEARER_SECRET}`)
      .set('Cookie', `sid=${COOKIE_SECRET}`)
      .set('X-Forwarded-For', '198.51.100.23');
    const accessLine = lines.find((line) => 'res' in line);
    if (accessLine === undefined) {
      throw new Error('the request wrote no access line');
    }
    return accessLine;
  }

  it('when a request carries credentials and a query string, then the line holds only id, method and path', async () => {
    const line = await accessLineOf(`${PREFIX_ROOT}/logged/ok?token=${QUERY_SECRET}`);

    const requestFields = line.req as Record<string, unknown>;
    expect(Object.keys(requestFields).sort()).toEqual(['id', 'method', 'path']);
    expect(requestFields).toMatchObject({ method: 'GET', path: `${PREFIX_ROOT}/logged/ok` });
  });

  it('when a request finishes, then no secret, query or address appears anywhere in the line', async () => {
    const serialized = JSON.stringify(
      await accessLineOf(`${PREFIX_ROOT}/logged/ok?token=${QUERY_SECRET}`),
    );

    for (const secret of [BEARER_SECRET, COOKIE_SECRET, QUERY_SECRET, '198.51.100.23']) {
      expect(serialized).not.toContain(secret);
    }
  });

  it('when the response sets a cookie, then the response header is redacted', async () => {
    const line = await accessLineOf(`${PREFIX_ROOT}/logged/ok`);

    expect(line.res).toHaveProperty(['headers', 'set-cookie'], '[Redacted]');
  });

  it('when the response is a success, then the line is at info level', async () => {
    const line = await accessLineOf(`${PREFIX_ROOT}/logged/ok`);

    expect(line.level).toBe(30);
  });

  it('when the response is a 5xx, then the line is a warning without a synthetic error', async () => {
    const line = await accessLineOf(`${PREFIX_ROOT}/logged/boom`);

    expect(line.level).toBe(40);
    expect(line).not.toHaveProperty('err');
    expect(line).toHaveProperty('res.statusCode', 503);
  });

  it('when a request hits the root of the global prefix, then it is logged as well', async () => {
    const line = await accessLineOf(PREFIX_ROOT);

    expect(line.req).toMatchObject({ method: 'GET', path: PREFIX_ROOT });
  });
});
