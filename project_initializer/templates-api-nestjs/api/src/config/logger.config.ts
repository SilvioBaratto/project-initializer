import { randomUUID } from 'node:crypto';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { HttpStatus, RequestMethod } from '@nestjs/common';
import type { Params } from 'nestjs-pino';
import type { DestinationStream } from 'pino';

/** Pino's own level vocabulary, most to least severe; `silent` turns logging off. */
export const LOG_LEVELS = ['fatal', 'error', 'warn', 'info', 'debug', 'trace', 'silent'] as const;

/** One of {@link LOG_LEVELS}. */
export type LogLevel = (typeof LOG_LEVELS)[number];

/** Level used when `LOG_LEVEL` is not set. */
export const DEFAULT_LOG_LEVEL: LogLevel = 'info';

/** Header that carries the correlation id in both directions. */
export const REQUEST_ID_HEADER = 'x-request-id';

/**
 * Shape an incoming correlation id must have to be trusted.
 *
 * The id is echoed in a response header and written to every log line, so anything outside this
 * set (spaces, control characters, an unbounded length) would let a client forge log entries.
 */
export const REQUEST_ID_PATTERN = /^[\w-]{1,64}$/;

/**
 * Credentials that must never reach a log line. Request headers are not logged at all (see
 * {@link serializeRequest}); the request paths stay as a second barrier for any code that logs a
 * raw request object itself.
 */
export const REDACTED_LOG_PATHS: readonly string[] = [
  'req.headers.authorization',
  'req.headers.cookie',
  'res.headers["set-cookie"]',
];

/**
 * Every route, in the wildcard syntax Nest 11 expects. Nest's default for the logger middleware
 * is the legacy `*`, which makes Nest log an "Unsupported route path" warning twice per start-up.
 */
const ALL_ROUTES = [{ path: '{*splat}', method: RequestMethod.ALL }];

const QUERY_SEPARATOR = '?';
const FIRST_SERVER_ERROR_STATUS: number = HttpStatus.INTERNAL_SERVER_ERROR;

const PRETTY_TRANSPORT = {
  target: 'pino-pretty',
  options: { colorize: true, singleLine: true },
};

/**
 * Lowercases and trims a raw `LOG_LEVEL` value so `INFO` and ` Info ` are accepted.
 *
 * Does not validate: the environment schema checks the result against {@link LOG_LEVELS}, which
 * keeps the vocabulary in one place.
 *
 * @param raw - The value as written in the environment.
 * @returns The value in the lowercase form pino expects.
 */
export function normalizeLogLevel(raw: string): string {
  return raw.trim().toLowerCase();
}

/**
 * Picks the correlation id for a request and mirrors it on the response.
 *
 * @param req - The incoming request; its `x-request-id` header is kept when it matches
 *   {@link REQUEST_ID_PATTERN}.
 * @param res - The response, which receives the chosen id in the same header.
 * @returns The incoming id when valid, otherwise a freshly generated UUID. A repeated header
 *   reaches Node as one comma-joined string, fails the pattern and is replaced too.
 */
export function resolveRequestId(req: IncomingMessage, res: ServerResponse): string {
  const incoming = req.headers[REQUEST_ID_HEADER];
  const requestId =
    typeof incoming === 'string' && REQUEST_ID_PATTERN.test(incoming) ? incoming : randomUUID();
  res.setHeader(REQUEST_ID_HEADER, requestId);
  return requestId;
}

/** The parts of the request that pino's serializer hands over; the rest is deliberately ignored. */
interface SerializableRequest {
  id?: unknown;
  method?: unknown;
  url?: unknown;
}

/**
 * Reduces a request to what a log line may keep: correlation id, method and path.
 *
 * pino's default serializer writes the full URL with its query string, the query and route
 * parameters, the client address and every header, which puts user input and addresses into every
 * access line and contradicts the error body, which leaves the query out. Redacting only the
 * credential headers would still leave those. The correlation id is enough to find the request in
 * the rest of the log.
 *
 * @param req - the request as pino's standard serializer maps it.
 * @returns `id`, `method` and `path`, where the path has no query string.
 */
export function serializeRequest(req: SerializableRequest): {
  id: unknown;
  method: unknown;
  path: string;
} {
  const url = typeof req.url === 'string' ? req.url : '';
  const queryStart = url.indexOf(QUERY_SEPARATOR);
  return {
    id: req.id,
    method: req.method,
    path: queryStart === -1 ? url : url.slice(0, queryStart),
  };
}

/**
 * Picks the level of the access line written when a response finishes.
 *
 * pino-http uses `error` for every 5xx, which repeats what the exception filter has already
 * logged with the real stack. A failed request is therefore a `warn` here, and the rest are
 * `info`.
 *
 * @param _req - the request; unused, the response decides.
 * @param res - the finished response.
 * @param error - set when the response ended with an error.
 * @returns `warn` for a 5xx or an error, `info` otherwise.
 */
export function accessLogLevel(
  _req: IncomingMessage,
  res: ServerResponse,
  error?: Error,
): 'info' | 'warn' {
  return error !== undefined || res.statusCode >= FIRST_SERVER_ERROR_STATUS ? 'warn' : 'info';
}

/** Fields pino-http passes to the access line of a failed request. */
interface FailedAccessValues {
  res: unknown;
  responseTime: unknown;
}

/**
 * Chooses what an access line of a failed request carries: the response and its duration, without
 * the synthetic error pino-http would add. That error holds a stack taken inside the logger, never
 * the failure's own, which the exception filter has already logged.
 *
 * @param _req - the request; unused.
 * @param _res - the response; unused, `values.res` holds its serialised form.
 * @param _error - the error pino-http made up; dropped on purpose.
 * @param values - the serialised response and the response time.
 * @returns the fields to log.
 */
export function failedAccessFields(
  _req: IncomingMessage,
  _res: ServerResponse,
  _error: Error,
  values: FailedAccessValues,
): FailedAccessValues {
  return { res: values.res, responseTime: values.responseTime };
}

/**
 * Builds the `nestjs-pino` configuration.
 *
 * @param options.level - Minimum level that is written.
 * @param options.pretty - Human-readable output through `pino-pretty`. Leave it off wherever a
 *   machine collects the output, and in tests, where the transport worker thread outlives the
 *   suite.
 * @param options.destination - Where lines are written; standard output when omitted. Lets a
 *   test read what would be logged.
 * @returns Parameters for `LoggerModule`: requests are logged as id, method and path only, and
 *   credentials are redacted from anything else that carries headers.
 */
export function buildLoggerParams(options: {
  level: LogLevel;
  pretty: boolean;
  destination?: DestinationStream;
}): Params {
  const httpOptions = {
    level: options.level,
    redact: [...REDACTED_LOG_PATHS],
    genReqId: resolveRequestId,
    serializers: { req: serializeRequest },
    customLogLevel: accessLogLevel,
    customErrorObject: failedAccessFields,
    ...(options.pretty ? { transport: PRETTY_TRANSPORT } : {}),
  };
  return {
    pinoHttp: options.destination ? [httpOptions, options.destination] : httpOptions,
    forRoutes: ALL_ROUTES,
  };
}
