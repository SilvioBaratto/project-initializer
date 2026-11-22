/** Validates src/common/filters/prisma-exception.filter.ts: PrismaClientExceptionFilter. */
import { HttpStatus, Logger } from '@nestjs/common';
import { Prisma } from '@generated/prisma';
import {
  createFakeResponse,
  httpHostOf,
  sentErrorBody,
} from '../../../test/support/filter-test-doubles';
import { INTERNAL_ERROR_MESSAGE, SERVICE_UNAVAILABLE_MESSAGE } from './error-body';
import { PRISMA_ERROR_MAP, PrismaClientExceptionFilter } from './prisma-exception.filter';

const REQUEST_ID = 'req-456';
const REQUEST_PATH = '/api/v1/items/42';

function fakeRequest(): { method: string; path: string; id: string } {
  return { method: 'DELETE', path: REQUEST_PATH, id: REQUEST_ID };
}

function prismaError(
  code: string,
  meta?: Record<string, unknown>,
): Prisma.PrismaClientKnownRequestError {
  return new Prisma.PrismaClientKnownRequestError(`raw prisma text for ${code}`, {
    code,
    clientVersion: 'test',
    meta,
  });
}

describe('PrismaClientExceptionFilter', () => {
  const filter = new PrismaClientExceptionFilter();
  let warnLog: jest.SpyInstance;
  let errorLog: jest.SpyInstance;

  beforeEach(() => {
    warnLog = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
    errorLog = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  function handle(exception: Prisma.PrismaClientKnownRequestError) {
    const response = createFakeResponse();
    filter.catch(exception, httpHostOf(fakeRequest(), response));
    return response;
  }

  it('when the code is mapped, then the table in PRISMA_ERROR_MAP is the contract', () => {
    expect(PRISMA_ERROR_MAP).toEqual({
      P2002: { status: HttpStatus.CONFLICT, message: 'Resource already exists' },
      P2003: { status: HttpStatus.BAD_REQUEST, message: 'Related resource does not exist' },
      P2025: { status: HttpStatus.NOT_FOUND, message: 'Resource not found' },
    });
  });

  it.each([
    ['P2002', HttpStatus.CONFLICT, 'Conflict', 'Resource already exists'],
    ['P2003', HttpStatus.BAD_REQUEST, 'Bad Request', 'Related resource does not exist'],
    ['P2025', HttpStatus.NOT_FOUND, 'Not Found', 'Resource not found'],
  ])(
    'when the code is %s, then it answers %i with the shared body',
    (code, status, reason, text) => {
      const response = handle(prismaError(code));

      expect(response.status).toHaveBeenCalledWith(status);
      expect(sentErrorBody(response)).toMatchObject({
        statusCode: status,
        error: reason,
        message: text,
        path: REQUEST_PATH,
        requestId: REQUEST_ID,
      });
    },
  );

  it('when the code is mapped, then one warning with the code is logged and no error', () => {
    handle(prismaError('P2002'));

    expect(warnLog).toHaveBeenCalledTimes(1);
    expect(warnLog).toHaveBeenCalledWith(
      `Prisma error P2002 on DELETE ${REQUEST_PATH} (requestId: ${REQUEST_ID})`,
    );
    expect(errorLog).not.toHaveBeenCalled();
  });

  it('when the error carries constraint columns and a cause, then none reaches the client', () => {
    const response = handle(
      prismaError('P2002', { target: ['email'], cause: 'Record to update not found.' }),
    );

    const serialized = JSON.stringify(sentErrorBody(response));
    expect(serialized).not.toContain('email');
    expect(serialized).not.toContain('Record to update');
    expect(serialized).not.toContain('raw prisma text');
  });

  it('when the code is not mapped, then it answers a fixed 500 and logs the error once', () => {
    const exception = prismaError('P2034');

    const response = handle(exception);

    expect(response.status).toHaveBeenCalledWith(HttpStatus.INTERNAL_SERVER_ERROR);
    expect(sentErrorBody(response).message).toBe(INTERNAL_ERROR_MESSAGE);
    expect(JSON.stringify(sentErrorBody(response))).not.toContain('raw prisma text');
    expect(errorLog).toHaveBeenCalledTimes(1);
    expect(errorLog).toHaveBeenCalledWith(
      { err: exception },
      `Unmapped Prisma error P2034 on DELETE ${REQUEST_PATH} (requestId: ${REQUEST_ID})`,
    );
    expect(warnLog).not.toHaveBeenCalled();
  });

  describe('when the database cannot take the work', () => {
    const rawQueryOutage = prismaError('P2010', {
      driverAdapterError: { cause: { kind: 'DatabaseNotReachable', host: 'db', port: 5432 } },
    });
    const unmappedDatabaseError = (sqlState: string): Prisma.PrismaClientKnownRequestError =>
      prismaError('P2039', {
        driverAdapterError: { cause: { kind: 'postgres', code: sqlState, severity: 'FATAL' } },
      });

    it.each([
      ['unreachable', prismaError('P1001')],
      ['timed out', prismaError('P1008')],
      ['closed', prismaError('P1017')],
      ['pool timeout', prismaError('P2024')],
      ['out of connection slots', prismaError('P2037')],
      ['unreachable on a raw query', rawQueryOutage],
      ['refused by a server that is starting or stopping', unmappedDatabaseError('57P03')],
    ])('then %s answers 503 like an open circuit, with one warning line', (_label, exception) => {
      const response = handle(exception);

      expect(response.status).toHaveBeenCalledWith(HttpStatus.SERVICE_UNAVAILABLE);
      expect(sentErrorBody(response).message).toBe(SERVICE_UNAVAILABLE_MESSAGE);
      expect(warnLog).toHaveBeenCalledTimes(1);
      expect(warnLog).toHaveBeenCalledWith(
        `Prisma error ${exception.code} on DELETE ${REQUEST_PATH} (requestId: ${REQUEST_ID}): database unavailable`,
      );
      expect(errorLog).not.toHaveBeenCalled();
    });

    it('then a raw query the database rejected is still an unexpected 500', () => {
      const rejected = prismaError('P2010', {
        driverAdapterError: { cause: { kind: 'TableDoesNotExist', table: 'nope' } },
      });

      const response = handle(rejected);

      expect(response.status).toHaveBeenCalledWith(HttpStatus.INTERNAL_SERVER_ERROR);
      expect(errorLog).toHaveBeenCalledTimes(1);
    });

    it('then an unmapped database error about the query is still an unexpected 500', () => {
      const response = handle(unmappedDatabaseError('42601'));

      expect(response.status).toHaveBeenCalledWith(HttpStatus.INTERNAL_SERVER_ERROR);
      expect(errorLog).toHaveBeenCalledTimes(1);
      expect(warnLog).not.toHaveBeenCalled();
    });
  });

  it.each([['constructor'], ['toString'], ['__proto__']])(
    'when the code is the inherited property name %s, then it is not resolved to a mapping',
    (code) => {
      const response = handle(prismaError(code));

      expect(Object.values(PRISMA_ERROR_MAP).map((mapping) => mapping.message)).not.toContain(
        sentErrorBody(response).message,
      );
    },
  );

  it('when the response has already started, then the connection is ended and no body is written', () => {
    const response = createFakeResponse();
    response.headersSent = true;

    filter.catch(prismaError('P2025'), httpHostOf(fakeRequest(), response));

    expect(response.end).toHaveBeenCalledTimes(1);
    expect(response.json).not.toHaveBeenCalled();
  });
});
