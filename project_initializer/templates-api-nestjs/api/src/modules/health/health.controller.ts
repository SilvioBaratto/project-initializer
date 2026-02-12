import { Controller, Get } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { PrismaService } from '../../prisma/prisma.service';

@ApiTags('Health')
@Controller('health')
export class HealthController {
  constructor(private readonly prisma: PrismaService) {}

  @Get()
  @ApiOperation({ summary: 'Health check' })
  async check() {
    const dbHealthy = await this.prisma.isHealthy();
    return {
      status: dbHealthy ? 'ok' : 'degraded',
      database: dbHealthy ? 'connected' : 'disconnected',
    };
  }
}
