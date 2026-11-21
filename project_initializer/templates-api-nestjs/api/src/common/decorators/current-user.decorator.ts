import { createParamDecorator, ExecutionContext } from '@nestjs/common';
import type { AuthenticatedRequest, AuthenticatedUser } from '../auth/authenticated-user';

/**
 * Injects the identity that `AccessTokenGuard` attached to the request.
 *
 * Resolves to `undefined` on public routes and in the base template, where no guard is wired, so
 * handlers must accept an absent user.
 */
export const CurrentUser = createParamDecorator(
  (_data: unknown, context: ExecutionContext): AuthenticatedUser | undefined =>
    context.switchToHttp().getRequest<AuthenticatedRequest>().user,
);
