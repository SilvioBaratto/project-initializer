/** Project URL the specs treat as the configured Supabase project; no request ever reaches it. */
export const TEST_SUPABASE_URL = 'https://test-project.supabase.co';

/** Publishable key placeholder; the client is stubbed in specs, so the value is never sent. */
export const TEST_SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_test_key';

/**
 * Environment variables the Supabase env schema needs before `AppModule` is imported.
 *
 * Replaces the empty base file. `test/support/test-env.ts` writes it into `process.env` through
 * jest `setupFiles`, over any value already set there, so specs never reach a real project.
 */
export const AUTH_TEST_ENV: Readonly<Record<string, string>> = {
  SUPABASE_URL: TEST_SUPABASE_URL,
  SUPABASE_PUBLISHABLE_KEY: TEST_SUPABASE_PUBLISHABLE_KEY,
};
