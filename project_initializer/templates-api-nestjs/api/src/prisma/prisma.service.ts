import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaClient } from '@generated/prisma';
import { PrismaPg } from '@prisma/adapter-pg';
import type { PoolConfig } from 'pg';
import type { BaseEnv } from '../config/env.base';
import { deriveSslOption, stripSslParameters } from './prisma-ssl.util';

/** The slice of the validated environment that shapes the connection pool. */
type PoolEnv = Pick<
  BaseEnv,
  'DATABASE_URL' | 'DB_CONNECT_TIMEOUT_MS' | 'DB_QUERY_TIMEOUT_MS' | 'DB_POOL_MAX'
>;

// The pool exists before the service does, so its error hook cannot use the service's logger.
const poolLogger = new Logger('PrismaPool');

/**
 * Builds the node-postgres pool configuration for the Prisma adapter.
 *
 * `query_timeout` is enforced by the client, not by Postgres: node-postgres would send
 * `statement_timeout` as a startup parameter, which the Supabase pooler and pgbouncer may reject.
 *
 * TLS is derived from the URL by {@link deriveSslOption} and the URL's own TLS parameters are
 * removed, because node-postgres would otherwise let them override the derived option.
 *
 * @param env - validated connection URL, timeouts in milliseconds and the pool size. The adapter
 *   ignores Prisma's `connection_limit` URL parameter, so `DB_POOL_MAX` is the only pool size.
 * @returns the pool configuration.
 */
export function buildPoolConfig(env: PoolEnv): PoolConfig {
  return {
    connectionString: stripSslParameters(env.DATABASE_URL),
    ssl: deriveSslOption(env.DATABASE_URL),
    max: env.DB_POOL_MAX,
    connectionTimeoutMillis: env.DB_CONNECT_TIMEOUT_MS,
    query_timeout: env.DB_QUERY_TIMEOUT_MS,
  };
}

/**
 * Logs a failure of an idle pooled connection, such as Postgres restarting or a pooler dropping
 * it. The pool discards the connection and opens a new one on demand, so this is a warning; the
 * adapter swallows the error silently unless a handler is given.
 *
 * @param error - the error the pool reported. Only its code is logged: its message can carry the
 *   host name.
 */
export function logIdlePoolConnectionError(error: Error): void {
  const code = 'code' in error && typeof error.code === 'string' ? error.code : error.name;
  poolLogger.warn(`Idle database connection failed (${code}); the pool replaces it on next use`);
}

/**
 * Prisma client wired to a pooled node-postgres connection and to the validated configuration.
 *
 * Initialises the client when the module initialises and disconnects on shutdown. The driver
 * adapter opens connections lazily, so start-up succeeds while Postgres is down and the readiness
 * probe reports it instead; liveness must not restart the container for it. Only repositories and
 * health indicators should depend on it; domain services go through their repository port.
 */
@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(PrismaService.name);

  constructor(config: ConfigService<BaseEnv, true>) {
    super({
      adapter: new PrismaPg(
        buildPoolConfig({
          DATABASE_URL: config.get('DATABASE_URL', { infer: true }),
          DB_CONNECT_TIMEOUT_MS: config.get('DB_CONNECT_TIMEOUT_MS', { infer: true }),
          DB_QUERY_TIMEOUT_MS: config.get('DB_QUERY_TIMEOUT_MS', { infer: true }),
          DB_POOL_MAX: config.get('DB_POOL_MAX', { infer: true }),
        }),
        { onPoolError: logIdlePoolConnectionError },
      ),
    });
  }

  async onModuleInit(): Promise<void> {
    await this.$connect();
    this.logger.log('Database client initialised; connections open on first use');
  }

  async onModuleDestroy(): Promise<void> {
    await this.$disconnect();
    this.logger.log('Database client disconnected');
  }
}
