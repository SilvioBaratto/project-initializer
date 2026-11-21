const BYTES_PER_KILOBYTE = 1_024;
const MAX_REQUEST_BODY_KILOBYTES = 512;

/**
 * Largest JSON request body the API reads, in bytes.
 *
 * Express stops at 100 kB by default, which is below what the chat route accepts by its own
 * bounds (a 4,000-character question plus 50 history entries of 8,000 characters is about 404,000
 * characters). The limit has to cover that with room for non-ASCII text, yet stay small enough
 * that a client cannot make the process buffer megabytes per request. Raise it together with the
 * chat bounds in `chat.constants.ts`, never alone.
 */
export const MAX_REQUEST_BODY_BYTES = MAX_REQUEST_BODY_KILOBYTES * BYTES_PER_KILOBYTE;
