import type { Provider, Type } from '@nestjs/common';
import { APP_GUARD } from '@nestjs/core';
import { AccessTokenGuard } from './common/auth/access-token.guard';
import { AuthModule } from './modules/auth/auth.module';

/** Feature modules this auth variant adds to `AppModule`. */
export const AUTH_MODULES: ReadonlyArray<Type<unknown>> = [AuthModule];

/**
 * Global guards this auth variant adds after the rate limiter, so a request that fails
 * authentication still counts against the limit.
 */
export const AUTH_GUARDS: ReadonlyArray<Provider> = [
  { provide: APP_GUARD, useClass: AccessTokenGuard },
];
