import type { Server } from 'node:http';
import { INestApplication, Type } from '@nestjs/common';
import { Test, TestingModuleBuilder } from '@nestjs/testing';
import { AppModule } from '../../src/app.module';
import { configureApp } from '../../src/app.setup';
import {
  ACCESS_TOKEN_VERIFIER,
  AccessTokenVerifier,
} from '../../src/common/auth/access-token-verifier';
import { DATABASE_HEALTH_PORT } from '../../src/modules/health/database-health.port';
import { ITEM_REPOSITORY } from '../../src/modules/items/item.repository';
import { PrismaService } from '../../src/prisma/prisma.service';
import { acceptAllVerifier, InMemoryItemRepository, upDatabaseHealth } from './test-doubles';

/** Options for {@link createE2eApp}. */
export interface E2eAppOptions {
  /**
   * Verifier that replaces the variant's own. Defaults to {@link acceptAllVerifier}; pass `null`
   * to keep the variant's real verifier, which is what an auth overlay's own e2e suite exercises.
   */
  verifier?: AccessTokenVerifier | null;
  /** Test-only controllers mounted next to the application's own, to probe a cross-cutting guard. */
  controllers?: Type<unknown>[];
  /** Hook for a suite that needs to override one more provider before the module compiles. */
  customize?(builder: TestingModuleBuilder): TestingModuleBuilder;
}

/** A running application plus the doubles behind it, so a test can inspect or steer them. */
export interface E2eApp {
  app: INestApplication;
  items: InMemoryItemRepository;
}

/**
 * Returns the HTTP server of an initialised app with a concrete type, because Nest declares it
 * `any` and supertest would otherwise receive an untyped argument.
 */
export function httpServerOf(app: INestApplication): Server {
  return app.getHttpServer() as Server;
}

const prismaServiceStub = {
  $connect: () => Promise.resolve(),
  $disconnect: () => Promise.resolve(),
  onModuleInit: () => Promise.resolve(),
  onModuleDestroy: () => Promise.resolve(),
};

/**
 * Boots the whole `AppModule` over in-memory doubles, so e2e runs need no Postgres.
 *
 * The app is configured through the same `configureApp` as `main.ts`, so prefix, filters and CORS
 * match production.
 *
 * @param options - See {@link E2eAppOptions}.
 * @returns The initialised application; the caller closes it in `afterAll`.
 */
export async function createE2eApp(options: E2eAppOptions = {}): Promise<E2eApp> {
  const doubles = {
    items: new InMemoryItemRepository(),
  };
  const verifier = options.verifier === undefined ? acceptAllVerifier : options.verifier;

  let builder = overrideInfrastructure(
    Test.createTestingModule({ imports: [AppModule], controllers: options.controllers }),
    doubles,
  );
  // Overriding a token that is not registered is ignored, which is what the base variant needs.
  if (verifier !== null) {
    builder = builder.overrideProvider(ACCESS_TOKEN_VERIFIER).useValue(verifier);
  }
  if (options.customize) {
    builder = options.customize(builder);
  }

  const moduleRef = await builder.compile();
  const app = moduleRef.createNestApplication();
  configureApp(app);
  await app.init();
  return { app, ...doubles };
}

/** Replaces every provider that would reach Postgres with its in-memory double. */
function overrideInfrastructure(
  builder: TestingModuleBuilder,
  doubles: Omit<E2eApp, 'app'>,
): TestingModuleBuilder {
  return builder
    .overrideProvider(PrismaService)
    .useValue(prismaServiceStub)
    .overrideProvider(DATABASE_HEALTH_PORT)
    .useValue(upDatabaseHealth)
    .overrideProvider(ITEM_REPOSITORY)
    .useValue(doubles.items);
}
