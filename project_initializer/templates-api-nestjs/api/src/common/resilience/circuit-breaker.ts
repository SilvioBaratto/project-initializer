/** Position of a {@link CircuitBreaker}: calls flow, calls are rejected, or one trial call runs. */
export type CircuitState = 'closed' | 'open' | 'half-open';

/** Tuning and hooks for a {@link CircuitBreaker}. */
export interface CircuitBreakerOptions {
  /** Consecutive failures that open the circuit. */
  readonly failureThreshold: number;
  /** How long the circuit stays open before one trial call is allowed through. */
  readonly resetTimeoutMs: number;
  /**
   * Decides whether a thrown error means the dependency is unavailable. An error that returns
   * `false` is rethrown as-is and counts as an answer from the dependency, which ends the current
   * failure streak: the dependency replied, the caller asked for something it cannot have.
   * Defaults to treating every error as a failure.
   */
  isFailure?: (error: unknown) => boolean;
  /** Clock in epoch milliseconds; replaceable so tests need no fake timers. */
  now?: () => number;
  /** Called after every state transition, for logging and metrics. */
  onStateChange?: (from: CircuitState, to: CircuitState) => void;
}

/** Thrown instead of running the operation while the circuit rejects calls. */
export class CircuitOpenError extends Error {
  constructor(message = 'Circuit is open') {
    super(message);
    this.name = 'CircuitOpenError';
  }
}

/**
 * Stops calling a failing dependency so callers fail fast instead of piling up on timeouts.
 *
 * Consecutive failures reaching `failureThreshold` open the circuit. While open every call
 * rejects with {@link CircuitOpenError}. After `resetTimeoutMs` the next call becomes the single
 * half-open trial: its success closes the circuit, its failure reopens it, and calls made while it
 * runs are rejected like any other.
 */
export class CircuitBreaker {
  private current: CircuitState = 'closed';
  private consecutiveFailures = 0;
  private openedAtMs = 0;
  /** Bumped on every transition so a call admitted in an earlier phase cannot move the circuit. */
  private generation = 0;

  constructor(private readonly options: CircuitBreakerOptions) {}

  /** Current position; `open` is reported until a call actually starts the half-open trial. */
  get state(): CircuitState {
    return this.current;
  }

  /**
   * Runs `operation` unless the circuit rejects calls.
   *
   * @param operation - the guarded call to the dependency.
   * @returns whatever `operation` resolves to.
   * @throws CircuitOpenError while the circuit is open or a trial call is already running.
   * @throws the operation's own error, unchanged, after it has been counted.
   */
  async execute<T>(operation: () => Promise<T>): Promise<T> {
    const admittedIn = this.admit();
    try {
      const value = await operation();
      this.recordSuccess(admittedIn);
      return value;
    } catch (error) {
      this.recordError(error, admittedIn);
      throw error;
    }
  }

  private admit(): number {
    if (this.current === 'closed') {
      return this.generation;
    }
    const trialDue =
      this.current === 'open' && this.now() - this.openedAtMs >= this.options.resetTimeoutMs;
    if (!trialDue) {
      throw new CircuitOpenError();
    }
    this.transition('half-open');
    return this.generation;
  }

  private recordSuccess(admittedIn: number): void {
    if (admittedIn !== this.generation) {
      return;
    }
    this.consecutiveFailures = 0;
    this.transition('closed');
  }

  private recordError(error: unknown, admittedIn: number): void {
    if (admittedIn !== this.generation) {
      return;
    }
    const isFailure = this.options.isFailure ?? (() => true);
    if (!isFailure(error)) {
      // The dependency answered, so a half-open trial must not stay stuck waiting for a verdict.
      this.recordSuccess(admittedIn);
      return;
    }
    this.consecutiveFailures += 1;
    if (this.current === 'half-open' || this.consecutiveFailures >= this.options.failureThreshold) {
      this.openedAtMs = this.now();
      this.transition('open');
    }
  }

  private transition(next: CircuitState): void {
    if (next === this.current) {
      return;
    }
    const previous = this.current;
    this.current = next;
    this.generation += 1;
    this.options.onStateChange?.(previous, next);
  }

  private now(): number {
    return (this.options.now ?? Date.now)();
  }
}
