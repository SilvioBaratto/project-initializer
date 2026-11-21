import { Controller, Get, UseFilters } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ApiOperation, ApiTags } from '@nestjs/swagger';
import {
  HealthCheck,
  HealthCheckResult,
  HealthCheckService,
  MemoryHealthIndicator,
} from '@nestjs/terminus';
import { SkipThrottle } from '@nestjs/throttler';
import { Public } from '../../common/decorators/public.decorator';
import type { BaseEnv } from '../../config/env.base';
import { DatabaseHealthIndicator } from './database.health';
import { HealthCheckExceptionFilter } from './health-check-exception.filter';
import { BYTES_PER_MEGABYTE, HEALTH_INDICATOR_KEYS } from './health.constants';

/**
 * Probes for the orchestrator: both are public so they work without credentials, and both skip
 * rate limiting because an orchestrator polls them from one address on a fixed schedule.
 */
@ApiTags('Health')
@SkipThrottle()
@UseFilters(HealthCheckExceptionFilter)
@Controller('health')
export class HealthController {
  constructor(
    private readonly health: HealthCheckService,
    private readonly memory: MemoryHealthIndicator,
    private readonly database: DatabaseHealthIndicator,
    private readonly config: ConfigService<BaseEnv, true>,
  ) {}

  /**
   * Readiness probe: whether this instance should receive traffic.
   *
   * Disk usage is deliberately not checked. Inside a container `/` reports the host's disk, which
   * this instance cannot free, and failing readiness on it would pull every replica out of
   * rotation at once without helping any of them.
   *
   * @returns the Terminus result; a failing indicator makes the response a 503 that carries the
   *   result as its body.
   */
  @Get('readiness')
  @Public()
  @HealthCheck()
  @ApiOperation({ summary: 'Readiness probe: database (with circuit state) and heap' })
  readiness(): Promise<HealthCheckResult> {
    const heapLimitBytes = this.heapLimitBytes('HEALTH_HEAP_READINESS_MB');
    return this.health.check([
      () => this.database.check(HEALTH_INDICATOR_KEYS.database),
      () => this.memory.checkHeap(HEALTH_INDICATOR_KEYS.memoryHeap, heapLimitBytes),
    ]);
  }

  /**
   * Liveness probe: whether this process should be restarted.
   *
   * The heap limit is higher than the readiness one because a failing liveness probe kills the
   * container, while a failing readiness probe only takes it out of rotation, and a watch-mode
   * reload briefly spikes the heap.
   *
   * @returns the Terminus result; an exceeded heap limit makes the response a 503.
   */
  @Get('liveness')
  @Public()
  @HealthCheck()
  @ApiOperation({ summary: 'Liveness probe: heap only' })
  liveness(): Promise<HealthCheckResult> {
    const heapLimitBytes = this.heapLimitBytes('HEALTH_HEAP_LIVENESS_MB');
    return this.health.check([
      () => this.memory.checkHeap(HEALTH_INDICATOR_KEYS.memoryHeap, heapLimitBytes),
    ]);
  }

  private heapLimitBytes(setting: 'HEALTH_HEAP_READINESS_MB' | 'HEALTH_HEAP_LIVENESS_MB'): number {
    return this.config.get(setting, { infer: true }) * BYTES_PER_MEGABYTE;
  }
}
