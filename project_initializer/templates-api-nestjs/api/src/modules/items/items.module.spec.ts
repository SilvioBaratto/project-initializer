/**
 * Validates src/modules/items/items.module.ts together with the shared database circuit breaker.
 */
import { Logger } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { Test } from '@nestjs/testing';
import { AuditLogger } from '../../common/audit/audit-logger';
import { CircuitOpenError } from '../../common/resilience/circuit-breaker';
import { PrismaService } from '../../prisma/prisma.service';
import { DATABASE_HEALTH_PORT, type DatabaseHealthPort } from '../health/database-health.port';
import { HealthModule } from '../health/health.module';
import { ITEM_REPOSITORY, type ItemRepository } from './item.repository';
import { ItemsModule } from './items.module';
import { PrismaItemRepository } from './prisma-item.repository';

const ITEM_ID = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';

describe('ItemsModule', () => {
  const findUnique = jest.fn();
  const queryRaw = jest.fn();
  const outage = new Error('connect ECONNREFUSED');
  let repository: ItemRepository;
  let databaseHealth: DatabaseHealthPort;

  beforeEach(async () => {
    jest.resetAllMocks();
    jest.spyOn(Logger.prototype, 'error').mockImplementation();
    jest.spyOn(Logger.prototype, 'warn').mockImplementation();
    queryRaw.mockRejectedValue(outage);
    const moduleRef = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({
          ignoreEnvFile: true,
          isGlobal: true,
          load: [() => ({ DB_BREAKER_FAILURE_THRESHOLD: 1, DB_BREAKER_RESET_MS: 60_000 })],
        }),
        ItemsModule,
        HealthModule,
      ],
    })
      .overrideProvider(PrismaService)
      .useValue({ $queryRaw: queryRaw, item: { findUnique } })
      .overrideProvider(AuditLogger)
      .useValue({ record: jest.fn() })
      .compile();
    repository = moduleRef.get<ItemRepository>(ITEM_REPOSITORY, { strict: false });
    databaseHealth = moduleRef.get<DatabaseHealthPort>(DATABASE_HEALTH_PORT, { strict: false });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('when the module is compiled, then the item repository is the Prisma implementation', () => {
    expect(repository).toBeInstanceOf(PrismaItemRepository);
  });

  it('when the health probe opens the circuit, then item calls fail fast without reaching the database', async () => {
    await databaseHealth.check();

    await expect(repository.findById(ITEM_ID)).rejects.toBeInstanceOf(CircuitOpenError);
    expect(findUnique).not.toHaveBeenCalled();
  });
});
