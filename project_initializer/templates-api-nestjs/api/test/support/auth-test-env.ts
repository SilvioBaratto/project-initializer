/**
 * Environment variables the active auth overlay needs before `AppModule` is imported.
 *
 * Empty in the base template, which has no auth. An auth overlay replaces this file with the
 * minimum valid values for its own env schema (for example a Supabase URL or a tenant id).
 */
export const AUTH_TEST_ENV: Readonly<Record<string, string>> = {};
