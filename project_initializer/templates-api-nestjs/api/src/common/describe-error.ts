/**
 * Renders anything that was thrown as text suitable for the second argument of a Nest logger call.
 *
 * @param error - the caught value; JavaScript allows throwing non-`Error` values.
 * @returns the stack for an `Error` (its message when the stack was stripped), otherwise
 *   `String(error)`.
 */
export function describeError(error: unknown): string {
  if (error instanceof Error) {
    return error.stack ?? error.message;
  }
  return String(error);
}
