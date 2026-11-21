import { Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Test } from '@nestjs/testing';
import { Prisma } from '@generated/prisma';
import { CircuitBreaker } from '../common/resilience/circuit-breaker';
import type { BaseEnv } from '../config/env.base';
import { createDatabaseCircuitBreaker, DATABASE_CIRCUIT_BREAKER } from './database-circuit-breaker';
import { PrismaDatabaseHealth } from './prisma-database-health';
import { PrismaService } from './prisma.service';

/** Validates src/prisma/prisma-database-health.ts. */
const FAILURE_THRESHOLD = 2;
const RESET_TIMEOUT_MS = 60_000;

/** What Prisma 7 throws when `SELECT 1` cannot reach Postgres: always `P2010`, whatever the cause. */
function unreachableDatabaseError(): Prisma.PrismaClientKnownRequestError {
  return new Prisma.PrismaClientKnownRequestError(
    "Raw query failed. Message: `Can't reach database server`",
    {
      code: 'P2010',
      clientVersion: 'test',
      meta: {
        driverAdapterError: {
          name: 'DriverAdapterError',
          cause: { kind: 'DatabaseNotReachable', host: '127.0.0.1', port: 5432 },
        },
      },
    },
  );
}

describe('PrismaDatabaseHealth', () => {
  const queryRaw = jest.fn();
  let health: PrismaDatabaseHealth;
  let breaker: CircuitBreaker;
  let errorSpy: jest.SpiedFunction<Logger['error']>;
  let warnSpy: jest.SpiedFunction<Logger['warn']>;

  async function createHealth(guard: CircuitBreaker): Promise<PrismaDatabaseHealth> {
    const moduleRef = await Test.createTestingModule({
      providers: [
        PrismaDatabaseHealth,
        { provide: PrismaService, useValue: { $queryRaw: queryRaw } },
        { provide: DATABASE_CIRCUIT_BREAKER, useValue: guard },
      ],
    }).compile();
    return moduleRef.get(PrismaDatabaseHealth);
  }

  beforeEach(async () => {
    queryRaw.mockReset();
    errorSpy = jest.spyOn(Logger.prototype, 'error').mockImplementation();
    warnSpy = jest.spyOn(Logger.prototype, 'warn').mockImplementation();
    breaker = new CircuitBreaker({
      failureThreshold: FAILURE_THRESHOLD,
      resetTimeoutMs: RESET_TIMEOUT_MS,
    });
    health = await createHealth(breaker);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('when SELECT 1 succeeds, then the database is up and the circuit closed', async () => {
    queryRaw.mockResolvedValue([{ '?column?': 1 }]);

    await expect(health.check()).resolves.toEqual({ up: true, circuit: 'closed' });
  });

  it('when SELECT 1 fails, then the database is down and the error is logged', async () => {
    const outage = new Error('connect ECONNREFUSED');
    queryRaw.mockRejectedValue(outage);

    await expect(health.check()).resolves.toEqual({ up: false, circuit: 'closed' });

    expect(errorSpy).toHaveBeenCalledWith({ err: outage }, 'Database health check failed');
  });

  it('when a non-Error value is thrown, then the probe still reports down and the value is logged', async () => {
    queryRaw.mockRejectedValue('socket hang up');

    await expect(health.check()).resolves.toEqual({ up: false, circuit: 'closed' });

    expect(errorSpy).toHaveBeenCalledWith(
      { err: 'socket hang up' },
      'Database health check failed',
    );
  });

  it('when failures open the circuit, then later probes report it without touching the database', async () => {
    queryRaw.mockRejectedValue(new Error('connect ECONNREFUSED'));
    for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
      await health.check();
    }
    queryRaw.mockClear();

    await expect(health.check()).resolves.toEqual({ up: false, circuit: 'open' });

    expect(queryRaw).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith('Database health check skipped: circuit is open');
  });
});

describe('PrismaDatabaseHealth with the production circuit breaker', () => {
  const queryRaw = jest.fn();
  const config = new ConfigService<BaseEnv, true>({
    DB_BREAKER_FAILURE_THRESHOLD: FAILURE_THRESHOLD,
    DB_BREAKER_RESET_MS: RESET_TIMEOUT_MS,
  });
  let health: PrismaDatabaseHealth;
  let breaker: CircuitBreaker;

  beforeEach(async () => {
    jest.useFakeTimers({ now: 0 });
    jest.spyOn(Logger.prototype, 'error').mockImplementation();
    jest.spyOn(Logger.prototype, 'warn').mockImplementation();
    jest.spyOn(Logger.prototype, 'log').mockImplementation();
    queryRaw.mockReset();
    breaker = createDatabaseCircuitBreaker(config);
    const moduleRef = await Test.createTestingModule({
      providers: [
        PrismaDatabaseHealth,
        { provide: PrismaService, useValue: { $queryRaw: queryRaw } },
        { provide: DATABASE_CIRCUIT_BREAKER, useValue: breaker },
      ],
    }).compile();
    health = moduleRef.get(PrismaDatabaseHealth);
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it('when the database stays unreachable, then consecutive probes open the circuit', async () => {
    queryRaw.mockRejectedValue(unreachableDatabaseError());

    for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
      await health.check();
    }

    expect(breaker.state).toBe('open');
  });

  it('when the half-open trial probe finds the database still down, then the circuit stays open', async () => {
    queryRaw.mockRejectedValue(unreachableDatabaseError());
    for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
      await health.check();
    }
    jest.advanceTimersByTime(RESET_TIMEOUT_MS);

    await expect(health.check()).resolves.toEqual({ up: false, circuit: 'open' });
  });

  it('when the database comes back, then the trial probe closes the circuit', async () => {
    queryRaw.mockRejectedValue(unreachableDatabaseError());
    for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
      await health.check();
    }
    jest.advanceTimersByTime(RESET_TIMEOUT_MS);
    queryRaw.mockResolvedValue([{ '?column?': 1 }]);

    await expect(health.check()).resolves.toEqual({ up: true, circuit: 'closed' });
  });
});
