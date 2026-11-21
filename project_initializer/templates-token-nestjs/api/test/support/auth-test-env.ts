/** Shared secret the token variant's e2e suite configures and presents; at least 32 characters. */
export const TEST_AUTH_TOKEN = 'e2e-shared-secret-0123456789abcdef-0123456789';

/**
 * Environment variables the token variant needs before `AppModule` is imported.
 *
 * Replaces the empty base file; `test-env.ts` writes it into `process.env` through jest
 * `setupFiles`, over any value already set there, so specs never depend on the real secret.
 */
export const AUTH_TEST_ENV: Readonly<Record<string, string>> = {
  AUTH_TOKEN: TEST_AUTH_TOKEN,
};
