import type { ThrottlerModuleOptions, ThrottlerOptions } from '@nestjs/throttler';

const RATE_LIMIT_WINDOW_MS = 60_000;

/** Requests per client and window that every route accepts before answering 429. */
export const GLOBAL_REQUESTS_PER_WINDOW = 100;
const AUTH_PROBE_REQUESTS_PER_WINDOW = 5;

/** Message of the 429 answer; the throttler's own default reads "ThrottlerException: ...". */
export const RATE_LIMIT_EXCEEDED_MESSAGE = 'Too many requests';

/** Ceiling for every route, applied per client by the app-wide `ThrottlerGuard`. */
export const GLOBAL_RATE_LIMIT: ThrottlerOptions = {
  ttl: RATE_LIMIT_WINDOW_MS,
  limit: GLOBAL_REQUESTS_PER_WINDOW,
};

/**
 * Options of `ThrottlerModule`. Counters live in process memory, so with several replicas each
 * one counts on its own and the effective ceiling is the limit times the replica count; share the
 * counters through a storage backed by an external shared store if that matters.
 */
export const THROTTLER_MODULE_OPTIONS: ThrottlerModuleOptions = {
  throttlers: [GLOBAL_RATE_LIMIT],
  errorMessage: RATE_LIMIT_EXCEEDED_MESSAGE,
};

/**
 * Stricter ceiling than the global one, for routes that let a caller test whether a credential is
 * valid, so that guessing one is slow. Pass it to `@Throttle()`.
 */
export const AUTH_PROBE_RATE_LIMIT = {
  default: { ttl: RATE_LIMIT_WINDOW_MS, limit: AUTH_PROBE_REQUESTS_PER_WINDOW },
};
