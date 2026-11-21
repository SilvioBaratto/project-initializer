/**
 * Validates src/modules/chatbot/queue-error-reporter.ts.
 */
import { Logger } from '@nestjs/common';
import { QUEUE_ERROR_LOG_INTERVAL_MS } from './chat.constants';
import { QueueErrorReporter } from './queue-error-reporter';

const START_MS = 1_000_000;

function connectionRefused(): Error {
  return Object.assign(new AggregateError([new Error('inner')], ''), { code: 'ECONNREFUSED' });
}

describe('QueueErrorReporter', () => {
  let reporter: QueueErrorReporter;
  let warnLog: jest.SpyInstance;
  let clock: jest.SpyInstance;

  beforeEach(() => {
    warnLog = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
    clock = jest.spyOn(Date, 'now').mockReturnValue(START_MS);
    reporter = new QueueErrorReporter();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('when a connection error is reported, then one warning names the origin and the code only', () => {
    reporter.report('producer', connectionRefused());

    expect(warnLog).toHaveBeenCalledTimes(1);
    expect(warnLog).toHaveBeenCalledWith('Chat queue producer error: ECONNREFUSED');
  });

  it('when the error carries a message and a stack, then neither is logged', () => {
    const error = new Error('redis://user:secret@host:6379 refused');

    reporter.report('worker', error);

    expect(warnLog).toHaveBeenCalledWith('Chat queue worker error: Error');
    expect(JSON.stringify(warnLog.mock.calls)).not.toContain('secret');
  });

  it('when a value that is not an Error is reported, then its type is logged', () => {
    reporter.report('worker', 'plain text');

    expect(warnLog).toHaveBeenCalledWith('Chat queue worker error: string');
  });

  it('when the same error repeats within the interval, then it is logged once', () => {
    reporter.report('producer', connectionRefused());
    clock.mockReturnValue(START_MS + QUEUE_ERROR_LOG_INTERVAL_MS - 1);
    reporter.report('producer', connectionRefused());

    expect(warnLog).toHaveBeenCalledTimes(1);
  });

  it('when the interval has passed, then the same error is logged again', () => {
    reporter.report('producer', connectionRefused());
    clock.mockReturnValue(START_MS + QUEUE_ERROR_LOG_INTERVAL_MS);
    reporter.report('producer', connectionRefused());

    expect(warnLog).toHaveBeenCalledTimes(2);
  });

  it('when the producer and the worker report the same code, then both are logged', () => {
    reporter.report('producer', connectionRefused());
    reporter.report('worker', connectionRefused());

    expect(warnLog).toHaveBeenCalledTimes(2);
  });

  it('when a different code arrives within the interval, then it is logged', () => {
    reporter.report('producer', connectionRefused());
    reporter.report('producer', Object.assign(new Error('x'), { code: 'ETIMEDOUT' }));

    expect(warnLog).toHaveBeenCalledWith('Chat queue producer error: ETIMEDOUT');
  });
});
