import 'reflect-metadata';

// Set valid env vars before AppModule is loaded so ConfigModule.forRoot validate() passes.
process.env.DATABASE_URL = process.env.DATABASE_URL || 'postgresql://localhost:5432/test';
process.env.DIRECT_URL = process.env.DIRECT_URL || 'postgresql://localhost:5432/test';
if (!process.env.AUTH_TOKEN || process.env.AUTH_TOKEN.length < 16) {
  process.env.AUTH_TOKEN = 'test-token-for-spec-setup!!';
}

import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard } from '@nestjs/throttler';
import { ConfigModule } from '@nestjs/config';
import { AppModule } from './app.module';
import { AuthGuard } from './modules/auth/auth.guard';

// NestJS stores forRoot() return values as Promises in the @Module imports metadata.
// Resolve each entry before comparing to ConfigModule.
async function resolveImports(
  mod: object,
): Promise<{ module?: unknown; global?: boolean }[]> {
  const raw: unknown[] = Reflect.getMetadata('imports', mod) ?? [];
  return Promise.all(
    raw.map((imp) =>
      Promise.resolve(imp as { module?: unknown; global?: boolean }),
    ),
  );
}

describe('AppModule — global guard registration', () => {
  it('when providers are read, APP_GUARD with AuthGuard is registered', () => {
    const providers: { provide: unknown; useClass?: unknown }[] =
      Reflect.getMetadata('providers', AppModule) ?? [];

    const authGuardEntry = providers.find(
      (p) => p.provide === APP_GUARD && p.useClass === AuthGuard,
    );

    expect(authGuardEntry).toBeDefined();
  });

  // ThrottlerGuard must be registered before AuthGuard so rate-limiting is
  // evaluated first; guards execute in provider-registration order.
  it('when providers are read, ThrottlerGuard is listed before AuthGuard', () => {
    const providers: { provide: unknown; useClass?: unknown }[] =
      Reflect.getMetadata('providers', AppModule) ?? [];

    const appGuards = providers.filter((p) => p.provide === APP_GUARD);
    const throttlerIdx = appGuards.findIndex((p) => p.useClass === ThrottlerGuard);
    const authIdx = appGuards.findIndex((p) => p.useClass === AuthGuard);

    expect(throttlerIdx).toBeGreaterThanOrEqual(0);
    expect(authIdx).toBeGreaterThanOrEqual(0);
    expect(throttlerIdx).toBeLessThan(authIdx);
  });
});

describe('AppModule (token) — ConfigModule wiring', () => {
  it('when AppModule imports are inspected, ConfigModule is wired as a global dynamic module', async () => {
    const imports = await resolveImports(AppModule);

    const configEntry = imports.find((imp) => imp.module === ConfigModule);

    expect(configEntry).toBeDefined();
    expect(configEntry!.global).toBe(true);
  });
});
