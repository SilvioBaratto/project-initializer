import 'reflect-metadata';

// Set valid env vars before AppModule is loaded so ConfigModule.forRoot validate() passes.
process.env.DATABASE_URL = process.env.DATABASE_URL || 'postgresql://localhost:5432/test';
process.env.DIRECT_URL = process.env.DIRECT_URL || 'postgresql://localhost:5432/test';
process.env.SUPABASE_URL = process.env.SUPABASE_URL || 'https://test.supabase.co';
process.env.SUPABASE_PUBLISHABLE_KEY = process.env.SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_test';

import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard } from '@nestjs/throttler';
import { ConfigModule } from '@nestjs/config';
import { AppModule } from './app.module';
import { SupabaseAuthGuard } from './modules/auth/auth.guard';

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
  it('when providers are read, APP_GUARD with SupabaseAuthGuard is registered', () => {
    const providers: { provide: unknown; useClass?: unknown }[] =
      Reflect.getMetadata('providers', AppModule) ?? [];

    const supabaseGuardEntry = providers.find(
      (p) => p.provide === APP_GUARD && p.useClass === SupabaseAuthGuard,
    );

    expect(supabaseGuardEntry).toBeDefined();
  });

  // ThrottlerGuard must be registered before SupabaseAuthGuard so rate-limiting is
  // evaluated first; guards execute in provider-registration order.
  it('when providers are read, ThrottlerGuard is listed before SupabaseAuthGuard', () => {
    const providers: { provide: unknown; useClass?: unknown }[] =
      Reflect.getMetadata('providers', AppModule) ?? [];

    const appGuards = providers.filter((p) => p.provide === APP_GUARD);
    const throttlerIdx = appGuards.findIndex((p) => p.useClass === ThrottlerGuard);
    const supabaseIdx = appGuards.findIndex((p) => p.useClass === SupabaseAuthGuard);

    expect(throttlerIdx).toBeGreaterThanOrEqual(0);
    expect(supabaseIdx).toBeGreaterThanOrEqual(0);
    expect(throttlerIdx).toBeLessThan(supabaseIdx);
  });

  // SupabaseAuthGuard must appear exactly once as APP_GUARD. A duplicate registration
  // (e.g. a leftover @UseGuards on a controller) causes canActivate to run twice per
  // request, doubling Supabase JWT-validation round-trips.
  it('when providers are read, SupabaseAuthGuard appears exactly once as APP_GUARD', () => {
    const providers: { provide: unknown; useClass?: unknown }[] =
      Reflect.getMetadata('providers', AppModule) ?? [];

    const supabaseGuardEntries = providers.filter(
      (p) => p.provide === APP_GUARD && p.useClass === SupabaseAuthGuard,
    );

    expect(supabaseGuardEntries).toHaveLength(1);
  });
});

describe('AppModule (supabase) — ConfigModule wiring', () => {
  it('when AppModule imports are inspected, ConfigModule is wired as a global dynamic module', async () => {
    const imports = await resolveImports(AppModule);

    const configEntry = imports.find((imp) => imp.module === ConfigModule);

    expect(configEntry).toBeDefined();
    expect(configEntry!.global).toBe(true);
  });
});
