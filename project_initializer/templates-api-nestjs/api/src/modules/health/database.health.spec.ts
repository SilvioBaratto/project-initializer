import { Test } from '@nestjs/testing';
import { TerminusModule } from '@nestjs/terminus';
import { DATABASE_HEALTH_PORT, type DatabaseHealthPort } from './database-health.port';
import { DatabaseHealthIndicator } from './database.health';

/** Validates src/modules/health/database.health.ts. */
describe('DatabaseHealthIndicator', () => {
  const port: jest.Mocked<DatabaseHealthPort> = { check: jest.fn() };
  let indicator: DatabaseHealthIndicator;

  beforeEach(async () => {
    port.check.mockReset();
    const moduleRef = await Test.createTestingModule({
      imports: [TerminusModule],
      providers: [DatabaseHealthIndicator, { provide: DATABASE_HEALTH_PORT, useValue: port }],
    }).compile();
    indicator = moduleRef.get(DatabaseHealthIndicator);
  });

  it('when the database is up, then the result is up under the given key with the circuit state', async () => {
    port.check.mockResolvedValue({ up: true, circuit: 'closed' });

    await expect(indicator.check('database')).resolves.toEqual({
      database: { status: 'up', circuit: 'closed' },
    });
  });

  it('when the database is down, then the result is down and shows an open circuit', async () => {
    port.check.mockResolvedValue({ up: false, circuit: 'open' });

    await expect(indicator.check('database')).resolves.toEqual({
      database: { status: 'down', circuit: 'open' },
    });
  });
});
