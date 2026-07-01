import 'reflect-metadata';

// Set valid env vars before AppModule is loaded so ConfigModule.forRoot validate() passes.
process.env.DATABASE_URL = process.env.DATABASE_URL || 'postgresql://localhost:5432/test';
process.env.DIRECT_URL = process.env.DIRECT_URL || 'postgresql://localhost:5432/test';
process.env.ENTRA_TENANT_ID = process.env.ENTRA_TENANT_ID || 'test-tenant-id';
process.env.ENTRA_API_CLIENT_ID = process.env.ENTRA_API_CLIENT_ID || 'test-api-client-id';
process.env.ENTRA_API_AUDIENCE = process.env.ENTRA_API_AUDIENCE || 'api://test-api-client-id';
process.env.ENTRA_API_SCOPE = process.env.ENTRA_API_SCOPE || 'access_as_user';

import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard } from '@nestjs/throttler';
import { ConfigModule } from '@nestjs/config';
import { AppModule } from './app.module';
import { EntraAuthGuard } from './modules/auth/auth.guard';

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
  it('when providers are read, APP_GUARD with EntraAuthGuard is registered', () => {
    const providers: { provide: unknown; useClass?: unknown }[] =
      Reflect.getMetadata('providers', AppModule) ?? [];

    const entraGuardEntry = providers.find(
      (p) => p.provide === APP_GUARD && p.useClass === EntraAuthGuard,
    );

    expect(entraGuardEntry).toBeDefined();
  });

  // ThrottlerGuard must be registered before EntraAuthGuard so rate-limiting is
  // evaluated first; guards execute in provider-registration order.
  it('when providers are read, ThrottlerGuard is listed before EntraAuthGuard', () => {
    const providers: { provide: unknown; useClass?: unknown }[] =
      Reflect.getMetadata('providers', AppModule) ?? [];

    const appGuards = providers.filter((p) => p.provide === APP_GUARD);
    const throttlerIdx = appGuards.findIndex((p) => p.useClass === ThrottlerGuard);
    const entraIdx = appGuards.findIndex((p) => p.useClass === EntraAuthGuard);

    expect(throttlerIdx).toBeGreaterThanOrEqual(0);
    expect(entraIdx).toBeGreaterThanOrEqual(0);
    expect(throttlerIdx).toBeLessThan(entraIdx);
  });

  // EntraAuthGuard must appear exactly once as APP_GUARD.
  it('when providers are read, EntraAuthGuard appears exactly once as APP_GUARD', () => {
    const providers: { provide: unknown; useClass?: unknown }[] =
      Reflect.getMetadata('providers', AppModule) ?? [];

    const entraGuardEntries = providers.filter(
      (p) => p.provide === APP_GUARD && p.useClass === EntraAuthGuard,
    );

    expect(entraGuardEntries).toHaveLength(1);
  });
});

describe('AppModule (entra) — ConfigModule wiring', () => {
  it('when AppModule imports are inspected, ConfigModule is wired as a global dynamic module', async () => {
    const imports = await resolveImports(AppModule);

    const configEntry = imports.find((imp) => imp.module === ConfigModule);

    expect(configEntry).toBeDefined();
    expect(configEntry!.global).toBe(true);
  });
});
