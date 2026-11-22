import { Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Prisma } from '@generated/prisma';
import type { BaseEnv } from '../config/env.base';
import { CircuitBreaker } from '../common/resilience/circuit-breaker';

/** Injection token for the single {@link CircuitBreaker} that guards every database call. */
export const DATABASE_CIRCUIT_BREAKER = Symbol('DATABASE_CIRCUIT_BREAKER');

/** Prisma codes of the request family (`P2xxx`) that answer "your query was wrong", not "I am down". */
const QUERY_ERROR_CODE_PREFIX = 'P2';

/**
 * `P2` codes that nevertheless mean the database cannot take the work: the pool timed out waiting
 * for a connection (`P2024`) or Postgres has no connection slots left (`P2037`).
 */
const CAPACITY_ERROR_CODES = new Set(['P2024', 'P2037']);

/**
 * Prisma wraps every driver failure of a raw query (`$queryRaw`, which the readiness probe uses)
 * in this one code, whatever the cause, so the code alone cannot tell an outage from a bad query.
 */
const RAW_QUERY_ERROR_CODE = 'P2010';

/**
 * Prisma code of a failed query whose database error the driver adapter has no kind for (Prisma
 * 7.9 and later), so a server that is shutting down or starting up surfaces under it too.
 */
export const UNMAPPED_DATABASE_ERROR_CODE = 'P2039';

/** Kind the pg adapter gives every Postgres error it does not map; the SQLSTATE is in `code`. */
const UNMAPPED_POSTGRES_ERROR_KIND = 'postgres';

/** SQLSTATE class `08`, connection exception: the session could not be set up or was lost. */
const CONNECTION_EXCEPTION_SQLSTATE_CLASS = '08';

/**
 * SQLSTATEs that mean the server itself is going away or not yet back: administrator shutdown
 * (`57P01`), crash shutdown (`57P02`) and "cannot connect now" while it starts or stops (`57P03`).
 */
const SERVER_STOPPING_OR_STARTING_SQLSTATES = new Set(['57P01', '57P02', '57P03']);

/**
 * Driver adapter error kinds that describe the connection and not the query: the server cannot be
 * reached, dropped or refused the session, or has no room for it.
 */
const CONNECTIVITY_ERROR_KINDS = new Set([
  'DatabaseNotReachable',
  'SocketTimeout',
  'ConnectionClosed',
  'TlsConnectionError',
  'AuthenticationFailed',
  'DatabaseDoesNotExist',
  'DatabaseAccessDenied',
  'TooManyConnections',
]);

/**
 * Reads what the driver adapter reported for a failed query, from `meta.driverAdapterError.cause`.
 *
 * @returns the cause, or `undefined` when the error carries none.
 */
function driverErrorCauseOf(error: Prisma.PrismaClientKnownRequestError): object | undefined {
  const adapterError = error.meta?.driverAdapterError;
  if (typeof adapterError !== 'object' || adapterError === null || !('cause' in adapterError)) {
    return undefined;
  }
  const { cause } = adapterError;
  return typeof cause === 'object' && cause !== null ? cause : undefined;
}

/**
 * Reads the kind the driver adapter reported for a failed query.
 *
 * @returns the kind (for example `DatabaseNotReachable`), or `undefined` when the error carries
 *   none.
 */
function driverErrorKindOf(error: Prisma.PrismaClientKnownRequestError): string | undefined {
  const cause = driverErrorCauseOf(error);
  if (cause === undefined || !('kind' in cause)) {
    return undefined;
  }
  return typeof cause.kind === 'string' ? cause.kind : undefined;
}

/**
 * Reads the SQLSTATE of a Postgres error the pg adapter did not map to a kind of its own, the
 * kind of error Prisma reports as {@link UNMAPPED_DATABASE_ERROR_CODE}.
 *
 * @param error - a known request error thrown by a Prisma call.
 * @returns the SQLSTATE (for example `57P03`), or `undefined` when the error carries no unmapped
 *   Postgres error or that error has no text SQLSTATE.
 */
export function unmappedPostgresSqlStateOf(
  error: Prisma.PrismaClientKnownRequestError,
): string | undefined {
  const cause = driverErrorCauseOf(error);
  if (
    cause === undefined ||
    !('kind' in cause) ||
    cause.kind !== UNMAPPED_POSTGRES_ERROR_KIND ||
    !('code' in cause)
  ) {
    return undefined;
  }
  return typeof cause.code === 'string' ? cause.code : undefined;
}

function isRawQueryOutage(error: Prisma.PrismaClientKnownRequestError): boolean {
  const kind = driverErrorKindOf(error);
  // Without a kind there is nothing to prove the database answered, and the only raw query this
  // template runs is the readiness probe, so an unreadable failure counts as an outage.
  return kind === undefined || CONNECTIVITY_ERROR_KINDS.has(kind);
}

function isUnmappedConnectionFailure(error: Prisma.PrismaClientKnownRequestError): boolean {
  const sqlState = unmappedPostgresSqlStateOf(error);
  // Prisma builds this code only from an error response of the server, so an error without a
  // connection SQLSTATE proves the database answered, like any other rejected query.
  if (sqlState === undefined) {
    return false;
  }
  return (
    sqlState.startsWith(CONNECTION_EXCEPTION_SQLSTATE_CLASS) ||
    SERVER_STOPPING_OR_STARTING_SQLSTATES.has(sqlState)
  );
}

/**
 * Tells outages from rejected queries.
 *
 * A unique-constraint violation, a missing row or a validation error proves the database is
 * reachable, so it must not push the circuit towards open. A raw query (`P2010`) is judged by what
 * the driver reported, because an unreachable database surfaces under that same code. A database
 * error the adapter has no kind for (`P2039`) is judged by its SQLSTATE, because a server that is
 * restarting refuses new sessions under that code.
 *
 * @param error - anything thrown by a Prisma call.
 * @returns `true` when the error suggests the database is unavailable.
 */
export function isDatabaseUnavailableError(error: unknown): boolean {
  if (error instanceof Prisma.PrismaClientValidationError) {
    return false;
  }
  if (!(error instanceof Prisma.PrismaClientKnownRequestError)) {
    return true;
  }
  if (error.code === RAW_QUERY_ERROR_CODE) {
    return isRawQueryOutage(error);
  }
  if (error.code === UNMAPPED_DATABASE_ERROR_CODE) {
    return isUnmappedConnectionFailure(error);
  }
  return !error.code.startsWith(QUERY_ERROR_CODE_PREFIX) || CAPACITY_ERROR_CODES.has(error.code);
}

/**
 * Creates the breaker shared by the repositories and the readiness probe, so one outage opens it
 * for both and readiness can report its state.
 *
 * @param config - validated configuration supplying the failure threshold and reset timeout.
 */
export function createDatabaseCircuitBreaker(config: ConfigService<BaseEnv, true>): CircuitBreaker {
  const logger = new Logger('DatabaseCircuitBreaker');
  return new CircuitBreaker({
    failureThreshold: config.get('DB_BREAKER_FAILURE_THRESHOLD', { infer: true }),
    resetTimeoutMs: config.get('DB_BREAKER_RESET_MS', { infer: true }),
    isFailure: isDatabaseUnavailableError,
    onStateChange: (from, to) => {
      if (to === 'open') {
        logger.warn(`Circuit opened (was ${from}): database calls fail fast until the next trial`);
        return;
      }
      logger.log(`Circuit ${to} (was ${from})`);
    },
  });
}
