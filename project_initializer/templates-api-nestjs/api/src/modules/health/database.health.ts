import { Inject, Injectable } from '@nestjs/common';
import { HealthIndicatorResult, HealthIndicatorService } from '@nestjs/terminus';
import { DATABASE_HEALTH_PORT, DatabaseHealthPort } from './database-health.port';

/** Terminus indicator that reports the database through {@link DatabaseHealthPort}. */
@Injectable()
export class DatabaseHealthIndicator {
  constructor(
    private readonly indicators: HealthIndicatorService,
    @Inject(DATABASE_HEALTH_PORT) private readonly database: DatabaseHealthPort,
  ) {}

  /**
   * Probes the database once.
   *
   * @param key - name under which the result appears in the health response.
   * @returns `up` or `down`, both carrying the circuit breaker state so an operator can tell a
   *   real outage from fail-fast mode.
   */
  async check(key: string): Promise<HealthIndicatorResult> {
    const session = this.indicators.check(key);
    const { up, circuit } = await this.database.check();
    return up ? session.up({ circuit }) : session.down({ circuit });
  }
}
