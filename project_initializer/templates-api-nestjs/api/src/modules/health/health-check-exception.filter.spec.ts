/** Validates src/modules/health/health-check-exception.filter.ts. */
import { Logger, ServiceUnavailableException } from '@nestjs/common';
import { createFakeResponse, httpHostOf } from '../../../test/support/filter-test-doubles';
import { HealthCheckExceptionFilter } from './health-check-exception.filter';

const REQUEST = { method: 'GET', baseUrl: '', path: '/api/v1/health/readiness', id: 'req-9' };
const REQUEST_SUMMARY = 'GET /api/v1/health/readiness (requestId: req-9)';

describe('HealthCheckExceptionFilter', () => {
  const filter = new HealthCheckExceptionFilter();
  let warnLog: jest.SpyInstance;

  beforeEach(() => {
    warnLog = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  function handle(exception: ServiceUnavailableException) {
    const response = createFakeResponse();
    filter.catch(exception, httpHostOf(REQUEST, response));
    return response;
  }

  it('when Terminus reports failing indicators, then the result is the body and each indicator is named in one warning', () => {
    const result = {
      status: 'error',
      info: {},
      error: { database: { status: 'down' }, memory_heap: { status: 'down' } },
    };

    const response = handle(new ServiceUnavailableException(result));

    expect(response.status).toHaveBeenCalledWith(503);
    expect(response.json).toHaveBeenCalledWith(result);
    expect(warnLog).toHaveBeenCalledTimes(1);
    expect(warnLog).toHaveBeenCalledWith(
      `${REQUEST_SUMMARY} reported unhealthy: database, memory_heap`,
    );
  });

  it.each([
    ['the process is shutting down', { status: 'shutting_down', info: {}, error: {}, details: {} }],
    ['the response has no error section', { status: 'error' }],
    ['the error section is not an object', { error: 'down' }],
    ['the response is plain text', 'Service Unavailable'],
  ])(
    'when %s, then the body is still passed on and the warning says no indicator is to blame',
    (_label, body) => {
      const response = handle(new ServiceUnavailableException(body));

      expect(response.json).toHaveBeenCalledTimes(1);
      expect(warnLog).toHaveBeenCalledWith(`${REQUEST_SUMMARY} reported unhealthy: none`);
    },
  );
});
