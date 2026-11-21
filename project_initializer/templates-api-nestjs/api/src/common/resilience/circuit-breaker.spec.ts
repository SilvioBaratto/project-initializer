import { CircuitBreaker, CircuitOpenError, type CircuitState } from './circuit-breaker';

/** Validates src/common/resilience/circuit-breaker.ts. */
const FAILURE_THRESHOLD = 3;
const RESET_TIMEOUT_MS = 1_000;

class FakeClock {
  private nowMs = 0;

  now = (): number => this.nowMs;

  advance(ms: number): void {
    this.nowMs += ms;
  }
}

const dependencyDown = new Error('dependency down');
const failingCall = (): Promise<string> => Promise.reject(dependencyDown);
const succeedingCall = (): Promise<string> => Promise.resolve('ok');

describe('CircuitBreaker', () => {
  let clock: FakeClock;
  let transitions: Array<[CircuitState, CircuitState]>;
  let breaker: CircuitBreaker;

  const createBreaker = (isFailure?: (error: unknown) => boolean): CircuitBreaker =>
    new CircuitBreaker({
      failureThreshold: FAILURE_THRESHOLD,
      resetTimeoutMs: RESET_TIMEOUT_MS,
      now: clock.now,
      isFailure,
      onStateChange: (from, to) => transitions.push([from, to]),
    });

  const failTimes = async (times: number): Promise<void> => {
    for (let attempt = 0; attempt < times; attempt += 1) {
      await expect(breaker.execute(failingCall)).rejects.toBe(dependencyDown);
    }
  };

  beforeEach(() => {
    clock = new FakeClock();
    transitions = [];
    breaker = createBreaker();
  });

  describe('when the circuit is closed', () => {
    it('when the operation succeeds, then its value is returned and the circuit stays closed', async () => {
      await expect(breaker.execute(succeedingCall)).resolves.toBe('ok');

      expect(breaker.state).toBe('closed');
    });

    it('when failures stay below the threshold, then the circuit stays closed', async () => {
      await failTimes(FAILURE_THRESHOLD - 1);

      expect(breaker.state).toBe('closed');
    });

    it('when failures reach the threshold, then the circuit opens', async () => {
      await failTimes(FAILURE_THRESHOLD);

      expect(breaker.state).toBe('open');
      expect(transitions).toEqual([['closed', 'open']]);
    });

    it('when a success interrupts the failures, then the streak starts again from zero', async () => {
      await failTimes(FAILURE_THRESHOLD - 1);
      await breaker.execute(succeedingCall);
      await failTimes(FAILURE_THRESHOLD - 1);

      expect(breaker.state).toBe('closed');
    });
  });

  describe('when the circuit is open', () => {
    beforeEach(async () => {
      await failTimes(FAILURE_THRESHOLD);
    });

    it('when a call arrives before the reset timeout, then it is rejected without running', async () => {
      const operation = jest.fn(succeedingCall);
      clock.advance(RESET_TIMEOUT_MS - 1);

      await expect(breaker.execute(operation)).rejects.toBeInstanceOf(CircuitOpenError);

      expect(operation).not.toHaveBeenCalled();
      expect(breaker.state).toBe('open');
    });

    it('when the reset timeout has elapsed and the trial succeeds, then the circuit closes', async () => {
      clock.advance(RESET_TIMEOUT_MS);

      await expect(breaker.execute(succeedingCall)).resolves.toBe('ok');

      expect(breaker.state).toBe('closed');
      expect(transitions).toEqual([
        ['closed', 'open'],
        ['open', 'half-open'],
        ['half-open', 'closed'],
      ]);
    });

    it('when the trial fails, then the circuit reopens and the timeout restarts', async () => {
      clock.advance(RESET_TIMEOUT_MS);
      await expect(breaker.execute(failingCall)).rejects.toBe(dependencyDown);
      clock.advance(RESET_TIMEOUT_MS - 1);

      expect(breaker.state).toBe('open');
      await expect(breaker.execute(succeedingCall)).rejects.toBeInstanceOf(CircuitOpenError);
    });

    it('when a trial is running, then concurrent calls are rejected and only one runs', async () => {
      clock.advance(RESET_TIMEOUT_MS);
      let finishTrial: (value: string) => void = () => undefined;
      const trial = breaker.execute(
        () => new Promise<string>((resolve) => (finishTrial = resolve)),
      );
      const concurrentOperation = jest.fn(succeedingCall);

      await expect(breaker.execute(concurrentOperation)).rejects.toBeInstanceOf(CircuitOpenError);
      finishTrial('trial done');

      await expect(trial).resolves.toBe('trial done');
      expect(concurrentOperation).not.toHaveBeenCalled();
      expect(breaker.state).toBe('closed');
    });
  });

  describe('when an error is not a failure', () => {
    beforeEach(() => {
      breaker = createBreaker((error) => !(error instanceof RangeError));
    });

    it('when it is thrown while closed, then it is rethrown and does not count towards the threshold', async () => {
      const notAFailure = new RangeError('bad input');

      for (let attempt = 0; attempt < FAILURE_THRESHOLD * 2; attempt += 1) {
        await expect(breaker.execute(() => Promise.reject(notAFailure))).rejects.toBe(notAFailure);
      }

      expect(breaker.state).toBe('closed');
    });

    it('when it is thrown by the half-open trial, then the circuit closes because the dependency answered', async () => {
      await failTimes(FAILURE_THRESHOLD);
      clock.advance(RESET_TIMEOUT_MS);

      await expect(
        breaker.execute(() => Promise.reject(new RangeError('bad input'))),
      ).rejects.toThrow(RangeError);

      expect(breaker.state).toBe('closed');
    });
  });

  describe('when a call outlives the phase it was admitted in', () => {
    it('when a call admitted while closed succeeds after the circuit opened, then the circuit stays open', async () => {
      let finishSlowCall: (value: string) => void = () => undefined;
      const slowCall = breaker.execute(
        () => new Promise<string>((resolve) => (finishSlowCall = resolve)),
      );
      await failTimes(FAILURE_THRESHOLD);

      finishSlowCall('late success');
      await slowCall;

      expect(breaker.state).toBe('open');
    });
  });

  it('when no clock is injected, then the real clock is used', async () => {
    const realClockBreaker = new CircuitBreaker({ failureThreshold: 1, resetTimeoutMs: 60_000 });

    await expect(realClockBreaker.execute(failingCall)).rejects.toBe(dependencyDown);

    await expect(realClockBreaker.execute(succeedingCall)).rejects.toBeInstanceOf(CircuitOpenError);
  });
});
