import { Controller, Get } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import {
  HealthCheck,
  HealthCheckService,
  HealthIndicatorResult,
  DiskHealthIndicator,
  MemoryHealthIndicator,
} from '@nestjs/terminus';
import { PrismaService } from '../../prisma/prisma.service';
import { Public } from '../../common/decorators/public.decorator';

@ApiTags('Health')
@Controller('health')
export class HealthController {
  constructor(
    private readonly health: HealthCheckService,
    private readonly disk: DiskHealthIndicator,
    private readonly memory: MemoryHealthIndicator,
    private readonly prisma: PrismaService,
  ) {}

  @Get('readiness')
  @Public()
  @HealthCheck()
  @ApiOperation({ summary: 'Readiness probe — DB, disk, and memory' })
  readiness() {
    return this.health.check([
      () => this.dbPing(),
      () => this.disk.checkStorage('disk', { path: '/', thresholdPercent: 0.9 }),
      () => this.memory.checkHeap('memory_heap', 300 * 1024 * 1024),
    ]);
  }

  @Get('liveness')
  @Public()
  @HealthCheck()
  @ApiOperation({ summary: 'Liveness probe — memory only' })
  liveness() {
    // 512 MB threshold avoids false-positives during ts-watch hot-reload spikes in dev.
    return this.health.check([
      () => this.memory.checkHeap('memory_heap', 512 * 1024 * 1024),
    ]);
  }

  private async dbPing(): Promise<HealthIndicatorResult> {
    const isHealthy = await this.prisma.isHealthy();
    if (isHealthy) {
      return { database: { status: 'up' } };
    }
    return { database: { status: 'down' } };
  }
}
