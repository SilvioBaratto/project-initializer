/** Validates src/common/filters/error-body.ts: the path an error body and a log line report. */
import type { Request } from 'express';
import { buildErrorBody, describeRequest, requestPathOf } from './error-body';

const CREDENTIAL = 'hunter2';

function expressRequest(fields: { baseUrl: string; path: string; originalUrl: string }): Request {
  return { method: 'GET', id: 'req-1', ...fields } as unknown as Request;
}

describe('requestPathOf', () => {
  it.each([
    [
      'a route matched at the application level',
      { baseUrl: '', path: '/api/v1/items/42', originalUrl: '/api/v1/items/42?token=secret' },
      '/api/v1/items/42',
    ],
    [
      'the not-found handler NestJS 12 mounts under the global prefix',
      { baseUrl: '/api/v1', path: '/missing', originalUrl: '/api/v1/missing?token=secret' },
      '/api/v1/missing',
    ],
    [
      'an absolute-form request target that carries credentials',
      {
        baseUrl: '/api/v1',
        path: '/missing',
        originalUrl: `http://user:${CREDENTIAL}@host/api/v1/missing?token=secret`,
      },
      '/api/v1/missing',
    ],
  ])(
    'when the request comes through %s, then the path is the full path alone',
    (_label, fields, path) => {
      expect(requestPathOf(expressRequest(fields))).toBe(path);
    },
  );
});

describe('error body and log line', () => {
  const absoluteForm = expressRequest({
    baseUrl: '',
    path: '/api/v1/items',
    originalUrl: `http://user:${CREDENTIAL}@host/api/v1/items?token=secret`,
  });

  it('when the target is in absolute form, then the body names the path and no credential', () => {
    const body = buildErrorBody({
      status: 500,
      message: 'Internal server error',
      request: absoluteForm,
    });

    expect(body.path).toBe('/api/v1/items');
    expect(JSON.stringify(body)).not.toMatch(new RegExp(`${CREDENTIAL}|secret`));
  });

  it('when the target is in absolute form, then the log line names the path and no credential', () => {
    expect(describeRequest(absoluteForm)).toBe('GET /api/v1/items (requestId: req-1)');
  });
});
