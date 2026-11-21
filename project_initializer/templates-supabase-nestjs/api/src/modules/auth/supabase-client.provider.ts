import type { FactoryProvider } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { Env } from '../../config/env.validation';

/** Injection token for the server-side Supabase client used to verify access tokens. */
export const SUPABASE_CLIENT = Symbol('SUPABASE_CLIENT');

/**
 * The part of the Supabase client that token verification uses.
 *
 * Narrowing the dependency keeps the verifier from reaching anything else on the client and lets
 * a spec hand it a one-method double without a cast.
 */
export interface SupabaseTokenClient {
  readonly auth: Pick<SupabaseClient['auth'], 'getUser'>;
}

/**
 * Longest wait for Supabase Auth to answer one token check. Every protected request waits on it,
 * so without a bound a stalled Supabase would hold each of them open until the platform's own
 * timeout. An expired wait counts as an outage (503), not as a rejected token.
 */
export const SUPABASE_AUTH_TIMEOUT_MS = 5_000;

/**
 * Auth options for a client that serves many callers from one process.
 *
 * It only checks tokens that callers present, so it must not keep a session, schedule a refresh
 * timer (which would hold the event loop open) or read a session from a URL.
 */
export const SUPABASE_SERVER_AUTH_OPTIONS = {
  persistSession: false,
  autoRefreshToken: false,
  detectSessionInUrl: false,
} as const;

/**
 * Wraps `fetch` so that every request is aborted after a deadline.
 *
 * @param timeoutMs - Milliseconds after which a request that has not completed is aborted.
 * @returns A `fetch` replacement. An aborted request rejects, which the Supabase auth client
 *   reports as a retryable network error; a signal the caller supplies still aborts it as well.
 */
export function createTimeoutFetch(timeoutMs: number): typeof fetch {
  return (input, init) => {
    const deadline = AbortSignal.timeout(timeoutMs);
    const signal = init?.signal ? AbortSignal.any([init.signal, deadline]) : deadline;
    return fetch(input, { ...init, signal });
  };
}

/**
 * Builds the Supabase client once from validated configuration.
 *
 * Provided through a token rather than constructed inside the service, so specs and e2e suites
 * can replace it without touching the network.
 */
export const supabaseClientProvider: FactoryProvider<SupabaseClient> = {
  provide: SUPABASE_CLIENT,
  inject: [ConfigService],
  useFactory: (config: ConfigService<Env, true>) =>
    createClient(
      config.get('SUPABASE_URL', { infer: true }),
      config.get('SUPABASE_PUBLISHABLE_KEY', { infer: true }),
      {
        auth: SUPABASE_SERVER_AUTH_OPTIONS,
        global: { fetch: createTimeoutFetch(SUPABASE_AUTH_TIMEOUT_MS) },
      },
    ),
};
