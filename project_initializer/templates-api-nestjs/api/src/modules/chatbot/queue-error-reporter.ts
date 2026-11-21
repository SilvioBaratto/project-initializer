import { Injectable, Logger } from '@nestjs/common';
import { QUEUE_ERROR_LOG_INTERVAL_MS } from './chat.constants';

/** Which side of the chat queue raised a connection error. */
export type QueueErrorOrigin = 'producer' | 'worker';

/**
 * Reduces an error to one short label. Redis connection failures arrive as multi-line
 * `AggregateError`s whose message is empty, so the code (`ECONNREFUSED`) is the useful part.
 */
function labelOf(error: unknown): string {
  if (!(error instanceof Error)) {
    return typeof error;
  }
  if ('code' in error && typeof error.code === 'string') {
    return error.code;
  }
  return error.name;
}

/**
 * Logs errors the BullMQ queue and worker emit on their own, such as a lost Redis connection.
 *
 * BullMQ prints an `error` event nobody listens to as a raw stack with `console.error`, once per
 * reconnect attempt, which floods the log and bypasses its format. Listening and reporting a
 * single line per distinct error, at most once per {@link QUEUE_ERROR_LOG_INTERVAL_MS}, keeps an
 * outage visible without drowning everything else.
 */
@Injectable()
export class QueueErrorReporter {
  private readonly logger = new Logger(QueueErrorReporter.name);
  private readonly lastLoggedAtByKey = new Map<string, number>();

  /**
   * Logs a queue error as a warning, unless the same one was logged recently.
   *
   * @param origin - Which side of the queue raised it.
   * @param error - The emitted value; only its code or class name is logged, never its message or
   *   stack, so a connection string inside either cannot leak.
   */
  report(origin: QueueErrorOrigin, error: unknown): void {
    const label = labelOf(error);
    const key = `${origin}:${label}`;
    const now = Date.now();
    const lastLoggedAt = this.lastLoggedAtByKey.get(key);
    if (lastLoggedAt !== undefined && now - lastLoggedAt < QUEUE_ERROR_LOG_INTERVAL_MS) {
      return;
    }
    this.lastLoggedAtByKey.set(key, now);
    this.logger.warn(`Chat queue ${origin} error: ${label}`);
  }
}
