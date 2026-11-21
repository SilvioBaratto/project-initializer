import { AUTH_TEST_ENV } from './auth-test-env';

/**
 * Environment for unit and e2e runs, with no database behind it: every suite stubs it.
 *
 * `ConfigModule.forRoot` validates `process.env` while `AppModule` is still being imported, so a
 * spec cannot set these in its own body: by then the import has already thrown. Register this file
 * under jest `setupFiles` so it runs before any module loads.
 *
 * The connection settings are only defaults (`??=`), because a stubbed run never connects to what
 * they point at. Values the assertions depend on are forced, so a `.env` loaded into the process,
 * a compose container or a CI job cannot change what a test sees.
 */
const CONNECTION_DEFAULTS: Readonly<Record<string, string>> = {
  NODE_ENV: 'test',
  DATABASE_URL: 'postgresql://postgres:postgres@localhost:5432/test',
  DIRECT_URL: 'postgresql://postgres:postgres@localhost:5432/test',
  LOG_LEVEL: 'silent',
};

// A fresh jest worker already holds ~315 MB of heap, which trips the production health limits and
// makes the health endpoints answer 503 intermittently.
const FORCED_ENV: Readonly<Record<string, string>> = {
  HEALTH_HEAP_READINESS_MB: '4096',
  HEALTH_HEAP_LIVENESS_MB: '4096',
};

for (const [name, value] of Object.entries(CONNECTION_DEFAULTS)) {
  process.env[name] ??= value;
}
Object.assign(process.env, FORCED_ENV, AUTH_TEST_ENV);
