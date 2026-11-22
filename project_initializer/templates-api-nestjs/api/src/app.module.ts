import { Module, StandardSchemaSerializerInterceptor } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { APP_GUARD, APP_INTERCEPTOR, APP_PIPE } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { LoggerModule } from 'nestjs-pino';
import { AUTH_GUARDS, AUTH_MODULES } from './app.auth';
import { RolesGuard } from './common/auth/roles.guard';
import { createSchemaValidationPipe } from './common/filters/schema-validation.exception';
import type { BaseEnv } from './config/env.base';
import { validate as validateEnv } from './config/env.validation';
import { ENV_FILE_PATHS } from './config/env-files';
import { buildLoggerParams } from './config/logger.config';
import { THROTTLER_MODULE_OPTIONS } from './config/rate-limit';
import { HealthModule } from './modules/health/health.module';
import { ItemsModule } from './modules/items/items.module';
import { TestModule } from './modules/test/test.module';

/**
 * Root module, identical in every variant. What differs between variants is the authentication
 * wiring, which comes in through `AUTH_MODULES` and `AUTH_GUARDS` from `app.auth.ts`.
 *
 * The rate limiter is the first global guard, ahead of the authentication guards, so that
 * requests with bad credentials are counted and a caller cannot guess tokens at full speed.
 * `RolesGuard` is the last one, so it checks `@Roles(...)` against an identity that is already
 * verified.
 *
 * The validation pipe (Nest's `StandardSchemaValidationPipe`, built by
 * `createSchemaValidationPipe`) checks only the parameters that pass `{ schema }`, and it throws
 * `SchemaValidationException` so the error filter can list each failing field. The serializer
 * applies the schema a handler declares with `@ResponseSchema`.
 */
@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      // The project .env sits at the repository root, one level above api/; a local api/.env is
      // the fallback. In Docker no file is read: compose passes the variables as real ones.
      envFilePath: [...ENV_FILE_PATHS],
      validate: validateEnv,
    }),
    LoggerModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService<BaseEnv, true>) =>
        buildLoggerParams({
          level: config.get('LOG_LEVEL', { infer: true }),
          pretty: config.get('NODE_ENV', { infer: true }) === 'development',
        }),
    }),
    ThrottlerModule.forRoot(THROTTLER_MODULE_OPTIONS),
    HealthModule,
    TestModule,
    ItemsModule,
    ...AUTH_MODULES,
  ],
  providers: [
    { provide: APP_GUARD, useClass: ThrottlerGuard },
    ...AUTH_GUARDS,
    { provide: APP_GUARD, useClass: RolesGuard },
    { provide: APP_PIPE, useFactory: createSchemaValidationPipe },
    { provide: APP_INTERCEPTOR, useClass: StandardSchemaSerializerInterceptor },
  ],
})
export class AppModule {}
