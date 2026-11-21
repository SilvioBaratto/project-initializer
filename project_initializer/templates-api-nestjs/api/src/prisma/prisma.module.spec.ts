import { Injectable, Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { Test } from '@nestjs/testing';
import { CircuitBreaker } from '../common/resilience/circuit-breaker';
import { DATABASE_HEALTH_PORT } from '../modules/health/database-health.port';
import { DATABASE_CIRCUIT_BREAKER } from './database-circuit-breaker';
import { PrismaDatabaseHealth } from './prisma-database-health';
import { PrismaModule } from './prisma.module';
import { PrismaService } from './prisma.service';

/** Validates src/prisma/prisma.module.ts. */
const breakerSettings = { DB_BREAKER_FAILURE_THRESHOLD: 3, DB_BREAKER_RESET_MS: 1_000 };

const configModule = ConfigModule.forRoot({
  ignoreEnvFile: true,
  isGlobal: true,
  load: [() => breakerSettings],
});

@Injectable()
class ClientConsumer {
  constructor(readonly prisma: PrismaService) {}
}

@Module({ providers: [ClientConsumer] })
class ModuleWithoutPrismaImport {}

describe('PrismaModule', () => {
  const prismaStub = {};

  it('when the module is compiled, then the breaker and the health port are provided', async () => {
    const moduleRef = await Test.createTestingModule({ imports: [configModule, PrismaModule] })
      .overrideProvider(PrismaService)
      .useValue(prismaStub)
      .compile();

    expect(moduleRef.get(DATABASE_CIRCUIT_BREAKER)).toBeInstanceOf(CircuitBreaker);
    expect(moduleRef.get(DATABASE_HEALTH_PORT)).toBeInstanceOf(PrismaDatabaseHealth);
  });

  it('when another module does not import PrismaModule, then it cannot inject the client', async () => {
    const compilation = Test.createTestingModule({
      imports: [configModule, PrismaModule, ModuleWithoutPrismaImport],
    })
      .overrideProvider(PrismaService)
      .useValue(prismaStub)
      .compile();

    await expect(compilation).rejects.toThrow(/PrismaService/);
  });
});
