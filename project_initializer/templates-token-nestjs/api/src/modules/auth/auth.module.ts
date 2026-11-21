import { Module } from '@nestjs/common';
import { ACCESS_TOKEN_VERIFIER } from '../../common/auth/access-token-verifier';
import { CurrentUserController } from '../../common/auth/current-user.controller';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';

/** Wires the shared-secret verifier behind `ACCESS_TOKEN_VERIFIER` for the global guard. */
@Module({
  controllers: [AuthController, CurrentUserController],
  providers: [AuthService, { provide: ACCESS_TOKEN_VERIFIER, useExisting: AuthService }],
  exports: [ACCESS_TOKEN_VERIFIER],
})
export class AuthModule {}
