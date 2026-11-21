import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  HttpStatus,
  Injectable,
  Logger,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { INSUFFICIENT_SCOPE_MESSAGE } from './auth-messages';
import type { AuthenticatedRequest } from './authenticated-user';
import { ROLES_KEY } from './roles.decorator';

/**
 * Global guard that enforces `@Roles(...)` (role-based access control).
 *
 * It is registered after the rate limiter and the authentication guards, so by the time it runs
 * `request.user` holds the verified identity. A route without `@Roles` passes. With `@Roles` the
 * caller must hold at least one listed role, otherwise the answer is 403 with the same generic
 * text for every cause: the required roles are never listed, so a response does not map the
 * permission model. A request with no identity, and a `@Roles()` with no role, are denied.
 *
 * Each denial writes one warn line with the status and the caller's opaque id when there is one,
 * never the roles or an email, so repeated attempts can be traced.
 */
@Injectable()
export class RolesGuard implements CanActivate {
  private readonly logger = new Logger(RolesGuard.name);

  constructor(private readonly reflector: Reflector) {}

  /**
   * @returns `true` when the route needs no role or the caller holds one of them.
   * @throws ForbiddenException (403) when the caller lacks every required role or has no identity.
   */
  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<readonly string[] | undefined>(
      ROLES_KEY,
      [context.getHandler(), context.getClass()],
    );
    if (requiredRoles === undefined) {
      return true;
    }
    const { user } = context.switchToHttp().getRequest<AuthenticatedRequest>();
    if (user?.roles.some((role) => requiredRoles.includes(role))) {
      return true;
    }
    this.logger.warn({
      msg: 'Request rejected by roles guard',
      status: HttpStatus.FORBIDDEN,
      actorId: user?.id,
    });
    throw new ForbiddenException(INSUFFICIENT_SCOPE_MESSAGE);
  }
}
