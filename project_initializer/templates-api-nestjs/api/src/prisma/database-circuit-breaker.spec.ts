import { Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Prisma } from '@generated/prisma';
import type { BaseEnv } from '../config/env.base';
import {
  createDatabaseCircuitBreaker,
  isDatabaseUnavailableError,
} from './database-circuit-breaker';

/** Validates src/prisma/database-circuit-breaker.ts. */
const CLIENT_VERSION = 'test';
const FAILURE_THRESHOLD = 2;
const RESET_MS = 1_000;

const requestError = (code: string): Prisma.PrismaClientKnownRequestError =>
  new Prisma.PrismaClientKnownRequestError('request failed', {
    code,
    clientVersion: CLIENT_VERSION,
  });

/**
 * Shape Prisma 7 gives a failed raw query on the pg adapter: the code is always `P2010` and the
 * driver's verdict sits in `meta.driverAdapterError.cause`. Captured from real failures.
 */
const rawQueryError = (cause: Record<string, unknown>): Prisma.PrismaClientKnownRequestError =>
  new Prisma.PrismaClientKnownRequestError('Raw query failed. Code: `N/A`', {
    code: 'P2010',
    clientVersion: CLIENT_VERSION,
    meta: { driverAdapterError: { name: 'DriverAdapterError', cause } },
  });

describe('isDatabaseUnavailableError', () => {
  it.each(['P2002', 'P2003', 'P2025'])(
    'when Prisma rejects the query with %s, then the database is considered reachable',
    (code) => {
      expect(isDatabaseUnavailableError(requestError(code))).toBe(false);
    },
  );

  it.each(['P1001', 'P1002', 'P1017'])(
    'when Prisma reports the connection problem %s, then the database is considered unavailable',
    (code) => {
      expect(isDatabaseUnavailableError(requestError(code))).toBe(true);
    },
  );

  it.each(['P2024', 'P2037'])(
    'when Prisma reports the capacity problem %s, then the database is considered unavailable',
    (code) => {
      expect(isDatabaseUnavailableError(requestError(code))).toBe(true);
    },
  );

  it.each([
    ['DatabaseNotReachable', { kind: 'DatabaseNotReachable', host: '127.0.0.1', port: 5432 }],
    ['SocketTimeout', { kind: 'SocketTimeout' }],
    ['ConnectionClosed', { kind: 'ConnectionClosed' }],
    ['TlsConnectionError', { kind: 'TlsConnectionError', reason: 'self signed certificate' }],
    ['AuthenticationFailed', { kind: 'AuthenticationFailed', user: 'app' }],
    ['TooManyConnections', { kind: 'TooManyConnections' }],
    ['DatabaseDoesNotExist', { kind: 'DatabaseDoesNotExist', db: 'app_db' }],
  ])(
    'when a raw query fails with the driver kind %s, then the database is considered unavailable',
    (_kind, cause) => {
      expect(isDatabaseUnavailableError(rawQueryError(cause))).toBe(true);
    },
  );

  it('when a raw query is rejected by the database itself, then it is considered reachable', () => {
    const rejected = rawQueryError({ kind: 'TableDoesNotExist', table: 'nope' });

    expect(isDatabaseUnavailableError(rejected)).toBe(false);
  });

  it.each([
    ['carries no driver detail', undefined],
    ['has a driver error without a cause', { driverAdapterError: { name: 'DriverAdapterError' } }],
    ['has a cause without a kind', { driverAdapterError: { cause: { host: 'db' } } }],
    ['has a non-text kind', { driverAdapterError: { cause: { kind: 7 } } }],
  ])('when a raw query error %s, then nothing proves the database answered', (_label, meta) => {
    const unreadable = new Prisma.PrismaClientKnownRequestError('Raw query failed', {
      code: 'P2010',
      clientVersion: CLIENT_VERSION,
      meta,
    });

    expect(isDatabaseUnavailableError(unreadable)).toBe(true);
  });

  it('when the query fails client-side validation, then the database is considered reachable', () => {
    const validationError = new Prisma.PrismaClientValidationError('invalid argument', {
      clientVersion: CLIENT_VERSION,
    });

    expect(isDatabaseUnavailableError(validationError)).toBe(false);
  });

  it('when a driver or network error is thrown, then the database is considered unavailable', () => {
    expect(isDatabaseUnavailableError(new Error('connect ECONNREFUSED'))).toBe(true);
  });
});

describe('createDatabaseCircuitBreaker', () => {
  const config = new ConfigService<BaseEnv, true>({
    DB_BREAKER_FAILURE_THRESHOLD: FAILURE_THRESHOLD,
    DB_BREAKER_RESET_MS: RESET_MS,
  });
  const outage = new Error('connect ECONNREFUSED');
  const failingQuery = (): Promise<void> => Promise.reject(outage);
  const succeedingQuery = (): Promise<void> => Promise.resolve();

  let warnSpy: jest.SpiedFunction<Logger['warn']>;
  let logSpy: jest.SpiedFunction<Logger['log']>;

  beforeEach(() => {
    jest.useFakeTimers({ now: 0 });
    warnSpy = jest.spyOn(Logger.prototype, 'warn').mockImplementation();
    logSpy = jest.spyOn(Logger.prototype, 'log').mockImplementation();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it('when outages reach the configured threshold, then the circuit opens and a warning is logged', async () => {
    const breaker = createDatabaseCircuitBreaker(config);

    for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
      await expect(breaker.execute(failingQuery)).rejects.toBe(outage);
    }

    expect(breaker.state).toBe('open');
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  it('when Prisma rejects queries repeatedly, then the circuit stays closed', async () => {
    const breaker = createDatabaseCircuitBreaker(config);
    const duplicate = requestError('P2002');

    for (let attempt = 0; attempt < FAILURE_THRESHOLD * 2; attempt += 1) {
      await expect(breaker.execute(() => Promise.reject(duplicate))).rejects.toBe(duplicate);
    }

    expect(breaker.state).toBe('closed');
  });

  it('when a raw-query outage keeps failing, then the circuit opens and a failed trial reopens it', async () => {
    const breaker = createDatabaseCircuitBreaker(config);
    const rawOutage = rawQueryError({ kind: 'DatabaseNotReachable', host: 'db', port: 5432 });
    const failingProbe = (): Promise<void> => Promise.reject(rawOutage);
    for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
      await expect(breaker.execute(failingProbe)).rejects.toBe(rawOutage);
    }
    expect(breaker.state).toBe('open');
    jest.advanceTimersByTime(RESET_MS);

    await expect(breaker.execute(failingProbe)).rejects.toBe(rawOutage);

    expect(breaker.state).toBe('open');
  });

  it('when the reset timeout elapses and the trial succeeds, then the circuit closes and is logged', async () => {
    const breaker = createDatabaseCircuitBreaker(config);
    for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
      await expect(breaker.execute(failingQuery)).rejects.toBe(outage);
    }
    jest.advanceTimersByTime(RESET_MS);

    await breaker.execute(succeedingQuery);

    expect(breaker.state).toBe('closed');
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('closed'));
  });
});
