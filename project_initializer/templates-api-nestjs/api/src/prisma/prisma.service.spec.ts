import { Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Client } from 'pg';
import type { BaseEnv } from '../config/env.base';
import { PrismaService, buildPoolConfig, logIdlePoolConnectionError } from './prisma.service';

/** Validates src/prisma/prisma.service.ts. */
const CONNECT_TIMEOUT_MS = 2_500;
const QUERY_TIMEOUT_MS = 7_500;
const POOL_MAX = 4;
const LOCAL_URL = 'postgresql://postgres:postgres@localhost:5432/app_db';
const REMOTE_URL = 'postgresql://user:pw@db.example.com:5432/postgres?sslmode=verify-full';

describe('buildPoolConfig', () => {
  it('when the URL is local, then the pool gets the URL, the size and the timeouts and no ssl', () => {
    const poolConfig = buildPoolConfig({
      DATABASE_URL: LOCAL_URL,
      DB_CONNECT_TIMEOUT_MS: CONNECT_TIMEOUT_MS,
      DB_QUERY_TIMEOUT_MS: QUERY_TIMEOUT_MS,
      DB_POOL_MAX: POOL_MAX,
    });

    expect(poolConfig).toEqual({
      connectionString: LOCAL_URL,
      ssl: undefined,
      max: POOL_MAX,
      connectionTimeoutMillis: CONNECT_TIMEOUT_MS,
      query_timeout: QUERY_TIMEOUT_MS,
    });
  });

  it('when the URL asks for certificate verification, then the pool verifies the server certificate', () => {
    const poolConfig = buildPoolConfig({
      DATABASE_URL: REMOTE_URL,
      DB_CONNECT_TIMEOUT_MS: CONNECT_TIMEOUT_MS,
      DB_QUERY_TIMEOUT_MS: QUERY_TIMEOUT_MS,
      DB_POOL_MAX: POOL_MAX,
    });

    expect(poolConfig.ssl).toEqual({ rejectUnauthorized: true });
  });

  it.each([
    ['require', 'sslmode=require', { rejectUnauthorized: false }],
    ['verify-full', 'sslmode=verify-full', { rejectUnauthorized: true }],
  ])(
    'when the URL says sslmode %s, then a client built from the pool config really uses the derived ssl',
    (_mode, query, expected) => {
      const poolConfig = buildPoolConfig({
        DATABASE_URL: `postgresql://user:pw@db.example.com:6543/postgres?${query}`,
        DB_CONNECT_TIMEOUT_MS: CONNECT_TIMEOUT_MS,
        DB_QUERY_TIMEOUT_MS: QUERY_TIMEOUT_MS,
        DB_POOL_MAX: POOL_MAX,
      });

      const client = new Client(poolConfig) as unknown as {
        connectionParameters: { ssl: unknown };
      };

      expect(client.connectionParameters.ssl).toEqual(expected);
    },
  );

  it('when a timeout is configured, then it is enforced by the client rather than as a statement_timeout parameter', () => {
    const poolConfig = buildPoolConfig({
      DATABASE_URL: LOCAL_URL,
      DB_CONNECT_TIMEOUT_MS: CONNECT_TIMEOUT_MS,
      DB_QUERY_TIMEOUT_MS: QUERY_TIMEOUT_MS,
      DB_POOL_MAX: POOL_MAX,
    });

    expect(poolConfig).not.toHaveProperty('statement_timeout');
  });
});

describe('logIdlePoolConnectionError', () => {
  let warnLog: jest.SpyInstance;

  beforeEach(() => {
    warnLog = jest.spyOn(Logger.prototype, 'warn').mockImplementation();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('when the error has a code, then one warning carries the code and not the message', () => {
    const reset = Object.assign(new Error('read ECONNRESET from 10.0.0.5:5432'), {
      code: 'ECONNRESET',
    });

    logIdlePoolConnectionError(reset);

    expect(warnLog).toHaveBeenCalledTimes(1);
    expect(warnLog).toHaveBeenCalledWith(expect.stringContaining('ECONNRESET'));
    expect(warnLog).not.toHaveBeenCalledWith(expect.stringContaining('10.0.0.5'));
  });

  it('when the error has no code, then its name is logged instead', () => {
    logIdlePoolConnectionError(new TypeError('x'));

    expect(warnLog).toHaveBeenCalledWith(expect.stringContaining('TypeError'));
  });
});

describe('PrismaService', () => {
  const config = new ConfigService<BaseEnv, true>({
    DATABASE_URL: LOCAL_URL,
    DB_CONNECT_TIMEOUT_MS: CONNECT_TIMEOUT_MS,
    DB_QUERY_TIMEOUT_MS: QUERY_TIMEOUT_MS,
    DB_POOL_MAX: POOL_MAX,
  });

  beforeEach(() => {
    jest.spyOn(Logger.prototype, 'log').mockImplementation();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('when the module initialises, then the client connects', async () => {
    const service = new PrismaService(config);
    const connect = jest.spyOn(service, '$connect').mockResolvedValue();

    await service.onModuleInit();

    expect(connect).toHaveBeenCalledTimes(1);
  });

  it('when the module is destroyed, then the client disconnects', async () => {
    const service = new PrismaService(config);
    const disconnect = jest.spyOn(service, '$disconnect').mockResolvedValue();

    await service.onModuleDestroy();

    expect(disconnect).toHaveBeenCalledTimes(1);
  });

  it('when a connection fails at start-up, then the error reaches the caller', async () => {
    const service = new PrismaService(config);
    jest.spyOn(service, '$connect').mockRejectedValue(new Error('connect ECONNREFUSED'));

    await expect(service.onModuleInit()).rejects.toThrow('connect ECONNREFUSED');
  });
});
