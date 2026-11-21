import { Module } from '@nestjs/common';
import { TerminusModule } from '@nestjs/terminus';
import { PrismaModule } from '../../prisma/prisma.module';
import { DatabaseHealthIndicator } from './database.health';
import { HealthController } from './health.controller';

/** Liveness and readiness probes. */
@Module({
  // Terminus would log every failed probe at `error` as well; the exception filter on the
  // controller already writes the one line a failed probe should produce, at `warn`.
  imports: [TerminusModule.forRoot({ logger: false }), PrismaModule],
  controllers: [HealthController],
  providers: [DatabaseHealthIndicator],
})
export class HealthModule {}
