import { Module } from '@nestjs/common';
import { ACCESS_TOKEN_VERIFIER } from '../../common/auth/access-token-verifier';
import { CurrentUserController } from '../../common/auth/current-user.controller';
import { AuthService } from './auth.service';
import { supabaseClientProvider } from './supabase-client.provider';

/**
 * Wires Supabase token verification into the application.
 *
 * Exports only the verifier port, which the global `AccessTokenGuard` resolves; the concrete
 * service and the Supabase client stay private to the module.
 */
@Module({
  controllers: [CurrentUserController],
  providers: [
    supabaseClientProvider,
    AuthService,
    { provide: ACCESS_TOKEN_VERIFIER, useExisting: AuthService },
  ],
  exports: [ACCESS_TOKEN_VERIFIER],
})
export class AuthModule {}
