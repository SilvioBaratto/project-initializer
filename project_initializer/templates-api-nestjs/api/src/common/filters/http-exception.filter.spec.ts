/** Validates src/common/filters/http-exception.filter.ts and src/common/filters/resolve-error.ts. */
import {
  BadRequestException,
  ForbiddenException,
  HttpException,
  HttpStatus,
  InternalServerErrorException,
  Logger,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { Prisma } from '@generated/prisma';
import { z } from 'zod';
import {
  createFakeResponse,
  httpHostOf,
  sentErrorBody,
} from '../../../test/support/filter-test-doubles';
import { CircuitOpenError } from '../resilience/circuit-breaker';
import {
  INTERNAL_ERROR_MESSAGE,
  ROUTE_NOT_FOUND_MESSAGE,
  SERVICE_UNAVAILABLE_MESSAGE,
} from './error-body';
import { HttpExceptionFilter } from './http-exception.filter';
import { type SchemaIssues, SchemaValidationException } from './schema-validation.exception';

const REQUEST_ID = 'req-123';
const REQUEST_PATH = '/api/v1/items';
const REQUEST_SUMMARY = `POST ${REQUEST_PATH} (requestId: ${REQUEST_ID})`;

function fakeRequest(id: unknown = REQUEST_ID): {
  method: string;
  baseUrl: string;
  path: string;
  originalUrl: string;
  id: unknown;
} {
  return { method: 'POST', baseUrl: '', path: REQUEST_PATH, originalUrl: REQUEST_PATH, id };
}

async function schemaIssues(): Promise<SchemaIssues> {
  const schema = z.object({ user: z.object({ name: z.string().min(1) }) });
  const result = await schema['~standard'].validate({ user: { name: '' } });
  if (result.issues === undefined) {
    throw new Error('the fixture must fail validation');
  }
  return result.issues;
}

/** Shape of the errors body-parser raises, which Express hands to the error handlers. */
function middlewareError(statusCode: number, message: string, expose = true): Error {
  return Object.assign(new Error(message), { statusCode, status: statusCode, expose });
}

/** What the Express adapter makes of a middleware error before the filters see it. */
function adapterMappedError(statusCode: number, message: string): HttpException {
  return new HttpException(message, statusCode, { cause: middlewareError(statusCode, message) });
}

describe('HttpExceptionFilter', () => {
  const filter = new HttpExceptionFilter();
  let errorLog: jest.SpyInstance;
  let warnLog: jest.SpyInstance;

  beforeEach(() => {
    errorLog = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
    warnLog = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  function handle(exception: unknown, request: object = fakeRequest()) {
    const response = createFakeResponse();
    filter.catch(exception, httpHostOf(request, response));
    return response;
  }

  describe('when an HttpException is thrown', () => {
    it('then it answers with the exception status, reason phrase and message', () => {
      const response = handle(new NotFoundException('Item not found'));

      expect(response.status).toHaveBeenCalledWith(HttpStatus.NOT_FOUND);
      expect(sentErrorBody(response)).toMatchObject({
        statusCode: HttpStatus.NOT_FOUND,
        error: 'Not Found',
        message: 'Item not found',
        path: REQUEST_PATH,
      });
    });

    it('then the body carries the request id and an ISO timestamp', () => {
      const body = sentErrorBody(handle(new ForbiddenException('Insufficient permissions')));

      expect(body.requestId).toBe(REQUEST_ID);
      expect(new Date(body.timestamp).toISOString()).toBe(body.timestamp);
    });

    it('then a 4xx answer is not logged', () => {
      handle(new BadRequestException('Bad input'));

      expect(errorLog).not.toHaveBeenCalled();
      expect(warnLog).not.toHaveBeenCalled();
    });

    it('then a 5xx without a cause is one warning line, since nothing unexpected happened', () => {
      const response = handle(new ServiceUnavailableException('Service is down'));

      expect(sentErrorBody(response).message).toBe('Service is down');
      expect(warnLog).toHaveBeenCalledTimes(1);
      expect(warnLog).toHaveBeenCalledWith(`${REQUEST_SUMMARY} failed with 503`);
      expect(errorLog).not.toHaveBeenCalled();
    });

    it('then a 5xx with a cause logs that cause once at error level and nothing else', () => {
      const cause = new Error('upstream refused');

      handle(new InternalServerErrorException('Operation failed', { cause }));

      expect(errorLog).toHaveBeenCalledTimes(1);
      expect(errorLog).toHaveBeenCalledWith({ err: cause }, `${REQUEST_SUMMARY} failed with 500`);
      expect(warnLog).not.toHaveBeenCalled();
    });
  });

  describe('when the router finds no route', () => {
    it('then the message is fixed and does not echo the query string', () => {
      const request = { ...fakeRequest(), method: 'GET', originalUrl: '/api/v1/nope?token=secret' };

      const body = sentErrorBody(
        handle(new NotFoundException('Cannot GET /api/v1/nope?token=secret'), request),
      );

      expect(body.message).toBe(ROUTE_NOT_FOUND_MESSAGE);
      expect(JSON.stringify(body)).not.toContain('secret');
    });

    it('then a not-found message chosen by application code is kept', () => {
      const body = sentErrorBody(handle(new NotFoundException('Cannot GET the moon')));

      expect(body.message).toBe('Cannot GET the moon');
    });

    it('then the body names the full path even when the handler sits under the prefix mount', () => {
      const originalUrl = '/api/v1/nope?token=secret';
      // Express reports the path relative to the router the not-found handler is mounted on.
      const request = { method: 'GET', path: '/nope', baseUrl: '/api/v1', originalUrl, id: 'r' };

      const body = sentErrorBody(
        handle(new NotFoundException(`Cannot GET ${originalUrl}`), request),
      );

      expect(body.path).toBe('/api/v1/nope');
      expect(JSON.stringify(body)).not.toContain('secret');
    });
  });

  describe('when request validation fails', () => {
    it('then it answers 400 with one entry per failing field and nothing else', async () => {
      const response = handle(new SchemaValidationException(await schemaIssues()));
      const body = sentErrorBody(response);

      expect(response.status).toHaveBeenCalledWith(HttpStatus.BAD_REQUEST);
      expect(body.message).toBe('Validation failed');
      expect(body.errors).toEqual([
        { path: 'user.name', message: 'Too small: expected string to have >=1 characters' },
      ]);
    });

    it('then a path segment given as an object contributes its key', () => {
      const issues = [{ message: 'Required', path: [{ key: 'user' }, { key: 0 }, 'name'] }];

      const body = sentErrorBody(handle(new SchemaValidationException(issues)));

      expect(body.errors).toEqual([{ path: 'user.0.name', message: 'Required' }]);
    });

    it('then an issue about the whole payload has an empty path', () => {
      const body = sentErrorBody(handle(new SchemaValidationException([{ message: 'Required' }])));

      expect(body.errors).toEqual([{ path: '', message: 'Required' }]);
    });

    it('then a 400 that is not a validation failure carries no field detail', () => {
      const body = sentErrorBody(handle(new BadRequestException('Validation failed')));

      expect(body.statusCode).toBe(HttpStatus.BAD_REQUEST);
      expect(body).not.toHaveProperty('errors');
    });
  });

  describe('when the database cannot take the work', () => {
    it.each([
      ['the circuit breaker rejects a call', new CircuitOpenError()],
      [
        'the client cannot initialise',
        new Prisma.PrismaClientInitializationError("Can't reach database server", 'test'),
      ],
    ])('then %s answers 503 with the fixed message and one warning line', (_label, exception) => {
      const response = handle(exception);

      expect(response.status).toHaveBeenCalledWith(HttpStatus.SERVICE_UNAVAILABLE);
      expect(sentErrorBody(response).message).toBe(SERVICE_UNAVAILABLE_MESSAGE);
      expect(warnLog).toHaveBeenCalledTimes(1);
      expect(warnLog).toHaveBeenCalledWith(`${REQUEST_SUMMARY} failed with 503: ${exception.name}`);
      expect(errorLog).not.toHaveBeenCalled();
    });
  });

  describe('when Express middleware rejects the request itself', () => {
    it.each([
      [HttpStatus.PAYLOAD_TOO_LARGE, 'request entity too large', 'Payload Too Large'],
      [HttpStatus.UNSUPPORTED_MEDIA_TYPE, 'unsupported charset "UTF-7"', 'Unsupported Media Type'],
      [HttpStatus.BAD_REQUEST, 'Unexpected token } in JSON at position 17', 'Bad Request'],
    ])('then a %i keeps its status under the fixed reason phrase', (status, text, phrase) => {
      const response = handle(middlewareError(status, text));
      const body = sentErrorBody(response);

      expect(response.status).toHaveBeenCalledWith(status);
      expect(body.message).toBe(phrase);
      expect(JSON.stringify(body)).not.toContain(text);
      expect(errorLog).not.toHaveBeenCalled();
    });

    it.each([
      [HttpStatus.PAYLOAD_TOO_LARGE, 'request entity too large', 'Payload Too Large'],
      [
        HttpStatus.UNSUPPORTED_MEDIA_TYPE,
        'unsupported charset "ISO-8859-1"',
        'Unsupported Media Type',
      ],
    ])(
      'then a %i the adapter wrapped in an HttpException still answers the fixed reason phrase',
      (status, text, phrase) => {
        const response = handle(adapterMappedError(status, text));
        const body = sentErrorBody(response);

        expect(response.status).toHaveBeenCalledWith(status);
        expect(body.message).toBe(phrase);
        expect(JSON.stringify(body)).not.toContain(text);
        expect(errorLog).not.toHaveBeenCalled();
      },
    );

    it('then an HttpException whose cause is not a middleware rejection keeps its own message', () => {
      const exception = new BadRequestException('Name is taken', { cause: new Error('detail') });

      expect(sentErrorBody(handle(exception)).message).toBe('Name is taken');
    });

    it.each([
      ['it is not marked for exposure', middlewareError(413, 'too large', false)],
      ['it is a server error', middlewareError(502, 'bad gateway')],
      [
        'its status is not a number',
        Object.assign(new Error('x'), { statusCode: '413', expose: true }),
      ],
    ])('then an error whose %s is still a fixed 500', (_label, exception) => {
      const response = handle(exception);

      expect(response.status).toHaveBeenCalledWith(HttpStatus.INTERNAL_SERVER_ERROR);
      expect(sentErrorBody(response).message).toBe(INTERNAL_ERROR_MESSAGE);
    });
  });

  describe('when an unexpected error is thrown', () => {
    it('then the client gets a fixed 500 message and never the error text', () => {
      const secretDetail = 'password authentication failed for user "app"';

      const response = handle(new Error(secretDetail));
      const body = sentErrorBody(response);

      expect(response.status).toHaveBeenCalledWith(HttpStatus.INTERNAL_SERVER_ERROR);
      expect(body.message).toBe(INTERNAL_ERROR_MESSAGE);
      expect(JSON.stringify(body)).not.toContain(secretDetail);
    });

    it('then the error object is logged once with the request summary', () => {
      const exception = new Error('boom');

      handle(exception);

      expect(errorLog).toHaveBeenCalledTimes(1);
      expect(errorLog).toHaveBeenCalledWith(
        { err: exception },
        `${REQUEST_SUMMARY} failed with 500`,
      );
    });

    it('then a thrown value that is not an Error is still logged', () => {
      const response = handle('plain string');

      expect(sentErrorBody(response).message).toBe(INTERNAL_ERROR_MESSAGE);
      expect(errorLog).toHaveBeenCalledWith({ err: "'plain string'" }, expect.any(String));
    });
  });

  describe('when a Prisma validation error is thrown', () => {
    const email = 'jane.doe@example.com';
    const exception = new Prisma.PrismaClientValidationError(
      `Invalid \`prisma.user.create()\` invocation:\n\n{\n  data: {\n    email: "${email}"\n  }\n}\n\nArgument \`name\` is missing.`,
      { clientVersion: 'test' },
    );

    it('then the client gets the fixed 500 message', () => {
      expect(sentErrorBody(handle(exception)).message).toBe(INTERNAL_ERROR_MESSAGE);
    });

    it('then the log names the error and its call site but carries none of the arguments', () => {
      handle(exception);

      expect(errorLog).toHaveBeenCalledTimes(1);
      const [line] = errorLog.mock.calls[0] as [string];
      expect(line).toContain(
        `${REQUEST_SUMMARY} failed with 500: PrismaClientValidationError raised at`,
      );
      expect(line).toContain('http-exception.filter.spec.ts');
      expect(line).not.toContain(email);
    });
  });

  describe('when the request has no usable id', () => {
    it('then a request without an id property is answered without one', () => {
      const request = { method: 'GET', baseUrl: '', path: REQUEST_PATH, originalUrl: REQUEST_PATH };

      expect(sentErrorBody(handle(new Error('boom'), request))).not.toHaveProperty('requestId');
    });

    it.each([[null], [42], [{ nested: true }]])(
      'then an id of %j is left out of the body and logged as none',
      (id) => {
        const response = handle(new Error('boom'), fakeRequest(id));

        expect(sentErrorBody(response)).not.toHaveProperty('requestId');
        expect(errorLog).toHaveBeenCalledWith(
          expect.anything(),
          expect.stringContaining('(requestId: none)'),
        );
      },
    );
  });

  describe('when the response has already started', () => {
    it('then the connection is ended and no second body is written', () => {
      const response = createFakeResponse();
      response.headersSent = true;

      filter.catch(new NotFoundException(), httpHostOf(fakeRequest(), response));

      expect(response.end).toHaveBeenCalledTimes(1);
      expect(response.status).not.toHaveBeenCalled();
      expect(response.json).not.toHaveBeenCalled();
    });
  });
});
