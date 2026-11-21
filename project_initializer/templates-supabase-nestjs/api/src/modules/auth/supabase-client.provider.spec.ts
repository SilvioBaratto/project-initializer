import { ConfigService } from '@nestjs/config';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import {
  TEST_SUPABASE_PUBLISHABLE_KEY,
  TEST_SUPABASE_URL,
} from '../../../test/support/auth-test-env';
import type { Env } from '../../config/env.validation';
import {
  SUPABASE_CLIENT,
  SUPABASE_SERVER_AUTH_OPTIONS,
  supabaseClientProvider,
} from './supabase-client.provider';

jest.mock('@supabase/supabase-js', () => ({ createClient: jest.fn() }));

// A stub keeps these values out of process.env, which `ConfigService` reads first.
const configService = {
  get: (key: string) =>
    ({
      SUPABASE_URL: TEST_SUPABASE_URL,
      SUPABASE_PUBLISHABLE_KEY: TEST_SUPABASE_PUBLISHABLE_KEY,
    })[key],
} as unknown as ConfigService<Env, true>;

/** Validates src/modules/auth/supabase-client.provider.ts supabaseClientProvider. */
describe('supabaseClientProvider', () => {
  it('when the provider is declared, then it registers SUPABASE_CLIENT and injects the config', () => {
    expect(supabaseClientProvider.provide).toBe(SUPABASE_CLIENT);
    expect(supabaseClientProvider.inject).toEqual([ConfigService]);
  });

  it('when the factory runs, then the client is created from the configured URL and key', async () => {
    const client = { auth: {} } as unknown as SupabaseClient;
    (createClient as unknown as jest.Mock).mockReturnValue(client);

    const created = await supabaseClientProvider.useFactory(configService);

    expect(created).toBe(client);
    expect(createClient).toHaveBeenCalledWith(TEST_SUPABASE_URL, TEST_SUPABASE_PUBLISHABLE_KEY, {
      auth: SUPABASE_SERVER_AUTH_OPTIONS,
      global: { fetch: expect.any(Function) as unknown },
    });
  });
});
