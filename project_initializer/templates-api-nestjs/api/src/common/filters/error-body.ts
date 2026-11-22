import { STATUS_CODES } from 'node:http';
import type { Request, Response } from 'express';

/** Message of every 500 response: the cause stays in the server log, never in the body. */
export const INTERNAL_ERROR_MESSAGE = 'Internal server error';

/**
 * Message of a 404 for a path no route serves. Nest's own text echoes the request URL including
 * its query string, which may carry credentials, so it is never sent.
 */
export const ROUTE_NOT_FOUND_MESSAGE = 'Route not found';

/** Message of a 503 caused by a dependency that is failing or failing fast. */
export const SERVICE_UNAVAILABLE_MESSAGE = 'Service temporarily unavailable';

const UNKNOWN_STATUS_LABEL = 'Error';
const QUERY_OR_FRAGMENT = /[?#]/;

/** One rejected field of a request, as reported to the client. */
export interface FieldError {
  /** Dot-separated location of the field in the payload. */
  path: string;
  message: string;
}

/** The single error shape every filter returns, so a client parses one format. */
export interface ErrorBody {
  statusCode: number;
  /** Standard reason phrase of `statusCode`. */
  error: string;
  message: string;
  /** Request path without the query string, which may carry credentials. */
  path: string;
  timestamp: string;
  /** Correlation id of the request, when the logger assigned one. */
  requestId?: string;
  /** Per-field detail of a validation failure. */
  errors?: readonly FieldError[];
}

/**
 * Reads the correlation id the logger assigned to a request.
 *
 * @param request - The request being answered.
 * @returns The id, or `undefined` when the logger did not run for this route.
 */
export function requestIdOf(request: Request): string | undefined {
  return typeof request.id === 'string' ? request.id : undefined;
}

/**
 * Reads the full path of a request, without the query string, which may carry credentials.
 *
 * It is taken from the original URL rather than `request.path`: Nest answers an unknown path under
 * the global prefix from a router mounted at that prefix, and there Express reports `request.path`
 * relative to the mount, without the prefix.
 *
 * @param request - The request being answered.
 * @returns The path as the client sent it, e.g. `/api/v1/items/42`.
 */
function requestPathOf(request: Request): string {
  const [path = ''] = request.originalUrl.split(QUERY_OR_FRAGMENT);
  return path;
}

/**
 * Describes a request for a log line: method, path without the query string, and correlation id.
 *
 * @param request - The request being answered.
 * @returns A single line free of headers, body and query, none of which are safe to log.
 */
export function describeRequest(request: Request): string {
  return `${request.method} ${requestPathOf(request)} (requestId: ${requestIdOf(request) ?? 'none'})`;
}

/**
 * Builds the error body for a response.
 *
 * @param input.status - HTTP status of the response.
 * @param input.message - Text safe to show a client; never the message of an unexpected error.
 * @param input.request - The failed request, for its path and correlation id.
 * @param input.errors - Per-field detail to include, for validation failures.
 * @returns The body, stamped with the current time.
 */
export function buildErrorBody(input: {
  status: number;
  message: string;
  request: Request;
  errors?: readonly FieldError[];
}): ErrorBody {
  const requestId = requestIdOf(input.request);
  return {
    statusCode: input.status,
    error: STATUS_CODES[input.status] ?? UNKNOWN_STATUS_LABEL,
    message: input.message,
    path: requestPathOf(input.request),
    timestamp: new Date().toISOString(),
    ...(requestId === undefined ? {} : { requestId }),
    ...(input.errors === undefined ? {} : { errors: input.errors }),
  };
}

/**
 * Writes an error body as the response.
 *
 * When the headers are already out, as happens when a stream fails midway, a status line cannot
 * be sent any more, so the connection is ended instead of throwing from inside the filter.
 *
 * @param response - The response to write to.
 * @param body - The body to send; its `statusCode` becomes the HTTP status.
 */
export function sendErrorBody(response: Response, body: ErrorBody): void {
  if (response.headersSent) {
    response.end();
    return;
  }
  response.status(body.statusCode).json(body);
}
