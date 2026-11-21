const BYTES_PER_KILOBYTE = 1_024;
const MAX_REQUEST_BODY_KILOBYTES = 512;

/**
 * Largest JSON request body the API reads, in bytes.
 *
 * Express stops at 100 kB by default. This limit sits above it for routes that take larger
 * documents, yet stays small enough that a client cannot make the process buffer megabytes per
 * request. Raise it together with the bounds the routes validate, never alone.
 */
export const MAX_REQUEST_BODY_BYTES = MAX_REQUEST_BODY_KILOBYTES * BYTES_PER_KILOBYTE;
