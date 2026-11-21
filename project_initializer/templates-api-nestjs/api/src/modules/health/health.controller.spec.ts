/** Validates src/modules/health/health.controller.ts and health-check-exception.filter.ts. */
import type { Server } from 'node:http';
import { INestApplication, Logger } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { APP_GUARD } from '@nestjs/core';
import { TerminusModule } from '@nestjs/terminus';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { Test } from '@nestjs/testing';
import { LoggerModule } from 'nestjs-pino';
import request from 'supertest';
import { API_PREFIX, configureApp } from '../../app.setup';
import { validate } from '../../config/env.validation';
import { buildLoggerParams } from '../../config/logger.config';
import { GLOBAL_REQUESTS_PER_WINDOW, THROTTLER_MODULE_OPTIONS } from '../../config/rate-limit';
import { DATABASE_HEALTH_PORT, type DatabaseHealthPort } from './database-health.port';
import { DatabaseHealthIndicator } from './database.health';
import { HealthController } from './health.controller';

const READINESS_URL = `/${API_PREFIX}/health/readiness`;
const LIVENESS_URL = `/${API_PREFIX}/health/liveness`;
// One megabyte is below any running process's heap, so a limit this small always trips.
const TRIPPING_HEAP_LIMIT_MB = '1';

describe('HealthController', () => {
  const database: jest.Mocked<DatabaseHealthPort> = { check: jest.fn() };
  let app: INestApplication;
  let warnLog: jest.SpyInstance;

  async function startApp(env: Record<string, string> = {}): Promise<INestApplication> {
    const moduleRef = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({
          isGlobal: true,
          ignoreEnvFile: true,
          validate: (raw) => validate({ ...raw, ...env }),
        }),
        LoggerModule.forRoot(buildLoggerParams({ level: 'silent', pretty: false })),
        ThrottlerModule.forRoot(THROTTLER_MODULE_OPTIONS),
        TerminusModule.forRoot({ logger: false }),
      ],
      controllers: [HealthController],
      providers: [
        DatabaseHealthIndicator,
        { provide: DATABASE_HEALTH_PORT, useValue: database },
        { provide: APP_GUARD, useClass: ThrottlerGuard },
      ],
    }).compile();
    const started = moduleRef.createNestApplication();
    configureApp(started);
    await started.init();
    return started;
  }

  const get = (url: string) => request(app.getHttpServer() as Server).get(url);

  beforeEach(async () => {
    jest.clearAllMocks();
    warnLog = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
    database.check.mockResolvedValue({ up: true, circuit: 'closed' });
    app = await startApp();
  });

  afterEach(async () => {
    await app.close();
    jest.restoreAllMocks();
  });

  describe('readiness', () => {
    it('when the database and the heap are fine, then it answers 200 with both indicators and no disk check', async () => {
      const response = await get(READINESS_URL);

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'ok',
        info: {
          database: { status: 'up', circuit: 'closed' },
          memory_heap: { status: 'up' },
        },
      });
      expect(response.body).not.toHaveProperty('info.disk');
    });

    it('when the database is down, then the 503 body names the failing indicator and the circuit state', async () => {
      database.check.mockResolvedValue({ up: false, circuit: 'open' });

      const response = await get(READINESS_URL);

      expect(response.status).toBe(503);
      expect(response.body).toMatchObject({
        status: 'error',
        error: { database: { status: 'down', circuit: 'open' } },
        details: { database: { status: 'down', circuit: 'open' }, memory_heap: { status: 'up' } },
      });
    });

    it('when the database is down, then exactly one warning line is logged and it names the indicator', async () => {
      database.check.mockResolvedValue({ up: false, circuit: 'open' });

      await get(READINESS_URL);

      expect(warnLog).toHaveBeenCalledTimes(1);
      expect(warnLog).toHaveBeenCalledWith(expect.stringContaining('reported unhealthy: database'));
    });

    it('when the heap exceeds the configured readiness limit, then readiness fails on memory_heap', async () => {
      await app.close();
      app = await startApp({ HEALTH_HEAP_READINESS_MB: TRIPPING_HEAP_LIMIT_MB });

      const response = await get(READINESS_URL);

      expect(response.status).toBe(503);
      expect(response.body).toMatchObject({ error: { memory_heap: { status: 'down' } } });
    });
  });

  describe('liveness', () => {
    it('when the heap is fine, then only the heap is checked and the database is left alone', async () => {
      const response = await get(LIVENESS_URL);

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'ok',
        info: { memory_heap: { status: 'up' } },
      });
      expect(database.check).not.toHaveBeenCalled();
    });

    it('when the database is down, then liveness still passes because it must not restart the container for it', async () => {
      database.check.mockResolvedValue({ up: false, circuit: 'open' });

      const response = await get(LIVENESS_URL);

      expect(response.status).toBe(200);
    });

    it('when the heap exceeds the configured liveness limit, then liveness answers 503', async () => {
      await app.close();
      app = await startApp({ HEALTH_HEAP_LIVENESS_MB: TRIPPING_HEAP_LIMIT_MB });

      const response = await get(LIVENESS_URL);

      expect(response.status).toBe(503);
      expect(response.body).toMatchObject({
        status: 'error',
        error: { memory_heap: { status: 'down' } },
      });
    });
  });

  it('when an orchestrator polls far more often than the global limit, then the probes are never rate limited', async () => {
    for (let polled = 0; polled < GLOBAL_REQUESTS_PER_WINDOW + 5; polled += 1) {
      await get(LIVENESS_URL).expect(200);
    }
  });
});
