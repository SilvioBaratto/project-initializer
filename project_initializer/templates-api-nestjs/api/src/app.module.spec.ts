/** Validates src/app.module.ts: the metadata AppModule declares, read without booting the app. */
import 'reflect-metadata';
import { BullModule } from '@nestjs/bullmq';
import { DynamicModule, FactoryProvider, Provider, Type } from '@nestjs/common';
import { MODULE_METADATA } from '@nestjs/common/constants';
import { ConfigModule } from '@nestjs/config';
import { APP_GUARD, APP_INTERCEPTOR, APP_PIPE } from '@nestjs/core';
import { getOptionsToken, ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { LoggerModule } from 'nestjs-pino';
import { ZodSerializerInterceptor, ZodValidationPipe } from 'nestjs-zod';
import { AUTH_GUARDS, AUTH_MODULES } from './app.auth';
import { AppModule } from './app.module';
import { RolesGuard } from './common/auth/roles.guard';
import { THROTTLER_MODULE_OPTIONS } from './config/rate-limit';
import { ChatbotModule } from './modules/chatbot/chatbot.module';
import { HealthModule } from './modules/health/health.module';
import { ItemsModule } from './modules/items/items.module';
import { MonitoringModule } from './modules/monitoring/monitoring.module';
import { TestModule } from './modules/test/test.module';

function metadataOf(key: string): unknown[] {
  const value: unknown = Reflect.getMetadata(key, AppModule);
  return Array.isArray(value) ? value : [];
}

// ConfigModule.forRoot returns a promise, so an entry may need awaiting before it can be read.
async function resolvedImports(): Promise<unknown[]> {
  return Promise.all(metadataOf(MODULE_METADATA.IMPORTS).map((entry) => Promise.resolve(entry)));
}

function isDynamicModule(entry: unknown): entry is DynamicModule {
  return typeof entry === 'object' && entry !== null && 'module' in entry;
}

async function dynamicModuleOf(module: Type<unknown>): Promise<DynamicModule> {
  const entry = (await resolvedImports())
    .filter(isDynamicModule)
    .find((candidate) => candidate.module === module);
  if (!entry) {
    throw new Error(`AppModule does not import ${module.name} as a dynamic module`);
  }
  return entry;
}

function isFactoryProvider(provider: Provider): provider is FactoryProvider {
  return typeof provider === 'object' && 'useFactory' in provider;
}

function factoryOf(dynamicModule: DynamicModule): FactoryProvider['useFactory'] {
  const provider = (dynamicModule.providers ?? []).find(isFactoryProvider);
  if (!provider) {
    throw new Error('the dynamic module declares no factory provider');
  }
  return provider.useFactory;
}

function isAppGuardProvider(provider: unknown): boolean {
  return (
    typeof provider === 'object' &&
    provider !== null &&
    'provide' in provider &&
    provider.provide === APP_GUARD
  );
}

function configWith(values: Record<string, unknown>): { get: (key: string) => unknown } {
  return { get: (key) => values[key] };
}

describe('AppModule imports', () => {
  it('when imports are read, then ConfigModule is registered once and globally', async () => {
    const configModules = (await resolvedImports())
      .filter(isDynamicModule)
      .filter((entry) => entry.module === ConfigModule);

    expect(configModules).toHaveLength(1);
    expect(configModules[0]).toHaveProperty('global', true);
  });

  it('when imports are read, then every feature module and the variant auth modules are listed', () => {
    const imported = metadataOf(MODULE_METADATA.IMPORTS);

    expect(imported).toEqual(
      expect.arrayContaining([
        HealthModule,
        TestModule,
        ItemsModule,
        ChatbotModule,
        MonitoringModule,
        ...AUTH_MODULES,
      ]),
    );
  });

  it('when the throttler is registered, then it uses the global rate limit and its message', async () => {
    const throttler = await dynamicModuleOf(ThrottlerModule);

    expect(throttler.providers).toContainEqual({
      provide: getOptionsToken(),
      useValue: THROTTLER_MODULE_OPTIONS,
    });
  });
});

describe('AppModule Redis connection', () => {
  it('when the queue module is configured, then host and port come from REDIS_HOST and REDIS_PORT', async () => {
    const factory = factoryOf(await dynamicModuleOf(BullModule));

    const options: unknown = await factory(configWith({ REDIS_HOST: 'redis', REDIS_PORT: 6380 }));

    expect(options).toEqual({ connection: { host: 'redis', port: 6380 } });
  });
});

describe('AppModule logger', () => {
  async function loggerOptions(values: Record<string, unknown>): Promise<unknown> {
    const factory = factoryOf(await dynamicModuleOf(LoggerModule));
    return factory(configWith(values));
  }

  it('when the logger is configured, then the level comes from LOG_LEVEL', async () => {
    const options = await loggerOptions({ LOG_LEVEL: 'warn', NODE_ENV: 'production' });

    expect(options).toHaveProperty('pinoHttp.level', 'warn');
  });

  it('when running in development, then output is pretty printed', async () => {
    const options = await loggerOptions({ LOG_LEVEL: 'info', NODE_ENV: 'development' });

    expect(options).toHaveProperty('pinoHttp.transport.target', 'pino-pretty');
  });

  it.each([['production'], ['test']])(
    'when running in %s, then output stays machine readable',
    async (nodeEnv) => {
      const options = await loggerOptions({ LOG_LEVEL: 'info', NODE_ENV: nodeEnv });

      expect(options).not.toHaveProperty('pinoHttp.transport');
    },
  );
});

describe('AppModule providers', () => {
  it('when global guards are read, then the rate limiter comes first, the auth guards follow and the roles guard is last', () => {
    const guards = metadataOf(MODULE_METADATA.PROVIDERS).filter(isAppGuardProvider);

    expect(guards).toEqual([
      { provide: APP_GUARD, useClass: ThrottlerGuard },
      ...AUTH_GUARDS,
      { provide: APP_GUARD, useClass: RolesGuard },
    ]);
  });

  it('when providers are read, then request bodies are validated and responses serialised through Zod', () => {
    const providers = metadataOf(MODULE_METADATA.PROVIDERS);

    expect(providers).toContainEqual({ provide: APP_PIPE, useClass: ZodValidationPipe });
    expect(providers).toContainEqual({
      provide: APP_INTERCEPTOR,
      useClass: ZodSerializerInterceptor,
    });
  });
});
