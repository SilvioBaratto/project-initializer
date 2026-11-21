import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { DATABASE_HEALTH_PORT } from '../modules/health/database-health.port';
import { DATABASE_CIRCUIT_BREAKER, createDatabaseCircuitBreaker } from './database-circuit-breaker';
import { PrismaDatabaseHealth } from './prisma-database-health';
import { PrismaService } from './prisma.service';

/**
 * Database access: the Prisma client, the circuit breaker that guards it and the readiness probe.
 *
 * Deliberately not global. A module that needs the database imports this one, which keeps every
 * dependency on the ORM visible in the module graph instead of reachable from anywhere.
 */
@Module({
  providers: [
    PrismaService,
    {
      provide: DATABASE_CIRCUIT_BREAKER,
      inject: [ConfigService],
      useFactory: createDatabaseCircuitBreaker,
    },
    { provide: DATABASE_HEALTH_PORT, useClass: PrismaDatabaseHealth },
  ],
  exports: [PrismaService, DATABASE_CIRCUIT_BREAKER, DATABASE_HEALTH_PORT],
})
export class PrismaModule {}
