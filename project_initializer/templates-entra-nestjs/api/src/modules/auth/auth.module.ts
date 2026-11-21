import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ACCESS_TOKEN_VERIFIER } from '../../common/auth/access-token-verifier';
import { CurrentUserController } from '../../common/auth/current-user.controller';
import { Env } from '../../config/env.validation';
import { AuthService, createJwksSigningKeyResolver, SIGNING_KEY_RESOLVER } from './auth.service';

/**
 * Wires Microsoft Entra ID token verification into the application.
 *
 * Exports only the verifier port, which the global `AccessTokenGuard` resolves; the concrete
 * service and the JWKS-backed key resolver stay private to the module.
 */
@Module({
  controllers: [CurrentUserController],
  providers: [
    {
      provide: SIGNING_KEY_RESOLVER,
      inject: [ConfigService],
      useFactory: (config: ConfigService<Env, true>) =>
        createJwksSigningKeyResolver(config.get('ENTRA_TENANT_ID', { infer: true })),
    },
    AuthService,
    { provide: ACCESS_TOKEN_VERIFIER, useExisting: AuthService },
  ],
  exports: [ACCESS_TOKEN_VERIFIER],
})
export class AuthModule {}
