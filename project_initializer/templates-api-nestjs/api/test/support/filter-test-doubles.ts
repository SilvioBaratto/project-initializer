import { ExecutionContextHost } from '@nestjs/core/helpers/execution-context-host';
import type { ErrorBody } from '../../src/common/filters/error-body';

/** Response stand-in with just the Express members the exception filters call. */
export interface FakeResponse {
  headersSent: boolean;
  status: jest.Mock;
  json: jest.Mock;
  end: jest.Mock;
}

/** Creates a {@link FakeResponse} whose `status()` chains to `json()` like Express does. */
export function createFakeResponse(): FakeResponse {
  const response: FakeResponse = {
    headersSent: false,
    status: jest.fn(),
    json: jest.fn(),
    end: jest.fn(),
  };
  response.status.mockReturnValue(response);
  return response;
}

/**
 * Reads back the body a filter passed to `response.json()`.
 *
 * @param response - the response the filter wrote to.
 * @returns the first body written; fails the test through an undefined access when none was.
 */
export function sentErrorBody(response: FakeResponse): ErrorBody {
  const [body] = response.json.mock.calls[0] as [ErrorBody];
  return body;
}

/**
 * Wraps a request and response in the host object Nest hands to a filter.
 *
 * @param request - a plain object with the request fields the filter reads.
 * @param response - the response double the filter writes to.
 */
export function httpHostOf(request: object, response: FakeResponse): ExecutionContextHost {
  return new ExecutionContextHost([request, response]);
}
