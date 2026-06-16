import 'reflect-metadata';

// Provide required env vars so ConfigModule.forRoot validate() does not reject during import.
process.env.DATABASE_URL = process.env.DATABASE_URL || 'postgresql://localhost:5432/test';
process.env.DIRECT_URL = process.env.DIRECT_URL || 'postgresql://localhost:5432/test';

import { ConfigModule } from '@nestjs/config';
import { BullModule } from '@nestjs/bullmq';
import { BullBoardModule } from '@bull-board/nestjs';
import { MonitoringModule } from './modules/monitoring/monitoring.module';
import { AppModule } from './app.module';

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

describe('AppModule (base) — ConfigModule wiring', () => {
  it('when AppModule imports are inspected, ConfigModule is wired as a global dynamic module', async () => {
    const imports = await resolveImports(AppModule);

    const configEntry = imports.find((imp) => imp.module === ConfigModule);

    expect(configEntry).toBeDefined();
    expect(configEntry!.global).toBe(true);
  });

  it('when AppModule imports are inspected, only one ConfigModule entry exists', async () => {
    const imports = await resolveImports(AppModule);

    const configEntries = imports.filter((imp) => imp.module === ConfigModule);

    expect(configEntries).toHaveLength(1);
  });
});

describe('AppModule (base) — BullModule Redis wiring', () => {
  it('when AppModule imports are inspected, BullModule.forRoot is present', async () => {
    const imports = await resolveImports(AppModule);

    // BullModule.forRoot() resolves to { module: BullModule, ... }
    const bullEntry = imports.find((imp) => imp.module === BullModule);

    expect(bullEntry).toBeDefined();
  });

  it('when AppModule source is inspected, REDIS_HOST env var drives the connection host', () => {
    // Read the .ts source alongside this spec — ts-jest keeps __dirname pointing at the
    // original src/ directory, so the .ts file is always co-located with this spec.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const path = require('path');
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require('fs');
    const src: string = fs.readFileSync(
      path.join(__dirname, 'app.module.ts'),
      'utf8',
    );

    expect(src).toContain('REDIS_HOST');
  });

  it('when AppModule source is inspected, REDIS_PORT env var drives the connection port', () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const path = require('path');
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require('fs');
    const src: string = fs.readFileSync(
      path.join(__dirname, 'app.module.ts'),
      'utf8',
    );

    expect(src).toContain('REDIS_PORT');
  });
});

describe('AppModule (base) — MonitoringModule registration', () => {
  it('when AppModule imports are inspected, MonitoringModule is registered', () => {
    // MonitoringModule is a plain (non-dynamic) module, so it appears directly in the raw imports array.
    const raw: unknown[] = Reflect.getMetadata('imports', AppModule) ?? [];

    expect(raw).toContain(MonitoringModule);
  });

  it('when AppModule imports are inspected, BullBoardModule root is wired for the dashboard', async () => {
    const imports = await resolveImports(AppModule);

    const boardEntry = imports.find((imp) => imp.module === BullBoardModule);

    expect(boardEntry).toBeDefined();
  });
});
