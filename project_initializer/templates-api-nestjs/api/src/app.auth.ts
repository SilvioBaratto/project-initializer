import type { Provider, Type } from '@nestjs/common';

/**
 * Feature modules the active auth variant adds to `AppModule`.
 *
 * Empty in the base template: no authentication is wired, so every route is public. An auth
 * overlay replaces this whole file, which keeps `app.module.ts` identical in all variants.
 */
export const AUTH_MODULES: ReadonlyArray<Type<unknown>> = [];

/**
 * Global guards the active auth variant adds after the rate limiter.
 *
 * Empty in the base template. An overlay lists `{ provide: APP_GUARD, useClass: AccessTokenGuard }`.
 */
export const AUTH_GUARDS: ReadonlyArray<Provider> = [];
