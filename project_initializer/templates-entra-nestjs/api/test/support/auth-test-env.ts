/** Tenant that the specs treat as the configured Entra directory. */
export const TEST_ENTRA_TENANT_ID = '11111111-1111-4111-8111-111111111111';

/** Application (client) id of the API registration in the specs. */
export const TEST_ENTRA_API_CLIENT_ID = '22222222-2222-4222-8222-222222222222';

/** Audience in its `api://` URI form, the second value an Entra access token may carry in `aud`. */
export const TEST_ENTRA_API_AUDIENCE = `api://${TEST_ENTRA_API_CLIENT_ID}`;

/** Scope name as it appears in the `scp` claim of a token. */
export const TEST_ENTRA_API_SCOPE = 'access_as_user';

/**
 * Environment variables the Entra env schema needs before `AppModule` is imported.
 *
 * Replaces the empty base file. `test/support/test-env.ts` writes it into `process.env` through
 * jest `setupFiles`, over any value already set there, so specs never reach a real tenant. The ids
 * are syntactically valid GUIDs that belong to no real tenant.
 */
export const AUTH_TEST_ENV: Readonly<Record<string, string>> = {
  ENTRA_TENANT_ID: TEST_ENTRA_TENANT_ID,
  ENTRA_API_CLIENT_ID: TEST_ENTRA_API_CLIENT_ID,
  ENTRA_API_AUDIENCE: TEST_ENTRA_API_AUDIENCE,
  ENTRA_API_SCOPE: TEST_ENTRA_API_SCOPE,
};
