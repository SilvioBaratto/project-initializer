import { Test, TestingModule } from '@nestjs/testing';
import { HealthCheckService, DiskHealthIndicator, MemoryHealthIndicator } from '@nestjs/terminus';
import { HealthController } from './health.controller';
import { PrismaService } from '../../prisma/prisma.service';

const mockHealthCheckService = {
  check: jest.fn(),
};

const mockDisk = { checkStorage: jest.fn() };
const mockMemory = { checkHeap: jest.fn() };
const mockPrisma = { isHealthy: jest.fn() };

describe('HealthController', () => {
  let controller: HealthController;
  let healthCheck: typeof mockHealthCheckService;

  beforeEach(async () => {
    jest.clearAllMocks();
    mockHealthCheckService.check.mockResolvedValue({ status: 'ok', info: {}, error: {}, details: {} });

    const module: TestingModule = await Test.createTestingModule({
      controllers: [HealthController],
      providers: [
        { provide: HealthCheckService, useValue: mockHealthCheckService },
        { provide: DiskHealthIndicator, useValue: mockDisk },
        { provide: MemoryHealthIndicator, useValue: mockMemory },
        { provide: PrismaService, useValue: mockPrisma },
      ],
    }).compile();

    controller = module.get<HealthController>(HealthController);
    healthCheck = module.get(HealthCheckService);
  });

  describe('readiness()', () => {
    it('when readiness is called, HealthCheckService.check is invoked with 3 indicators', async () => {
      await controller.readiness();

      expect(healthCheck.check).toHaveBeenCalledTimes(1);
      const [indicators] = healthCheck.check.mock.calls[0];
      expect(indicators).toHaveLength(3);
    });

    it('when readiness is called, the result from HealthCheckService.check is returned', async () => {
      const expected = { status: 'ok', info: {}, error: {}, details: {} };
      mockHealthCheckService.check.mockResolvedValue(expected);

      const result = await controller.readiness();

      expect(result).toBe(expected);
    });
  });

  describe('liveness()', () => {
    it('when liveness is called, HealthCheckService.check is invoked with 1 indicator', async () => {
      await controller.liveness();

      expect(healthCheck.check).toHaveBeenCalledTimes(1);
      const [indicators] = healthCheck.check.mock.calls[0];
      expect(indicators).toHaveLength(1);
    });

    it('when liveness is called, the result from HealthCheckService.check is returned', async () => {
      const expected = { status: 'ok', info: {}, error: {}, details: {} };
      mockHealthCheckService.check.mockResolvedValue(expected);

      const result = await controller.liveness();

      expect(result).toBe(expected);
    });
  });
});
