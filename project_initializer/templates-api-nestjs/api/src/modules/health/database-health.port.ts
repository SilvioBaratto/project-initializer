import type { CircuitState } from '../../common/resilience/circuit-breaker';

/** Injection token for the {@link DatabaseHealthPort} implementation. */
export const DATABASE_HEALTH_PORT = Symbol('DATABASE_HEALTH_PORT');

/** Outcome of one database probe. */
export interface DatabaseHealthStatus {
  /** Whether the database answered the probe. */
  readonly up: boolean;
  /** State of the circuit breaker guarding database calls, so readiness shows fail-fast mode. */
  readonly circuit: CircuitState;
}

/** What the readiness probe needs from the database, free of any ORM or driver type. */
export interface DatabaseHealthPort {
  /**
   * Probes the database once.
   *
   * @returns the outcome; never throws, a failed probe is reported as `up: false`.
   */
  check(): Promise<DatabaseHealthStatus>;
}
