import { Inject, Injectable, Logger } from '@nestjs/common';
import { CircuitBreaker, CircuitOpenError } from '../common/resilience/circuit-breaker';
import { DatabaseHealthPort, DatabaseHealthStatus } from '../modules/health/database-health.port';
import { DATABASE_CIRCUIT_BREAKER } from './database-circuit-breaker';
import { PrismaService } from './prisma.service';

/**
 * Probes Postgres with `SELECT 1` through the shared circuit breaker.
 *
 * Going through the breaker means a probe made while the circuit is open fails fast without
 * touching the database, and probes after an outage double as the half-open trial.
 */
@Injectable()
export class PrismaDatabaseHealth implements DatabaseHealthPort {
  private readonly logger = new Logger(PrismaDatabaseHealth.name);

  constructor(
    private readonly prisma: PrismaService,
    @Inject(DATABASE_CIRCUIT_BREAKER) private readonly breaker: CircuitBreaker,
  ) {}

  async check(): Promise<DatabaseHealthStatus> {
    try {
      await this.breaker.execute(() => this.prisma.$queryRaw`SELECT 1`);
      return { up: true, circuit: this.breaker.state };
    } catch (error) {
      this.logFailure(error);
      return { up: false, circuit: this.breaker.state };
    }
  }

  private logFailure(error: unknown): void {
    // The probe reports only `database: down`, so the reason has to be in the log. A rejected
    // probe while the circuit is open is expected and was already logged when it opened.
    if (error instanceof CircuitOpenError) {
      this.logger.warn('Database health check skipped: circuit is open');
      return;
    }
    // `{ err }` rather than a stack string: nestjs-pino keeps a second argument only when it
    // looks like a stack, so the reason for a non-Error rejection would vanish from the log.
    this.logger.error({ err: error }, 'Database health check failed');
  }
}
