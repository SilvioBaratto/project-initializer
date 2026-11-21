import { describeError } from '../../common/describe-error';

/**
 * Renders a chat failure for the log, looking through the generic 503 that hides its cause.
 *
 * @param error - What the chat pipeline threw. `ChatbotService` wraps every provider failure in a
 *   `ServiceUnavailableException` that carries the original as `cause`.
 * @returns The stack of the cause when there is one, otherwise of the error itself.
 */
export function describeChatFailure(error: unknown): string {
  const cause = error instanceof Error ? error.cause : undefined;
  return describeError(cause ?? error);
}
