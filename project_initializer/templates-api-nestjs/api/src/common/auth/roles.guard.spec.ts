import { ExecutionContext, ForbiddenException, Logger } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ExecutionContextHost } from '@nestjs/core/helpers/execution-context-host';
import { INSUFFICIENT_SCOPE_MESSAGE } from './auth-messages';
import type { AuthenticatedRequest, AuthenticatedUser } from './authenticated-user';
import { Roles } from './roles.decorator';
import { RolesGuard } from './roles.guard';

class OpenController {
  handle(): void {}
}

class AdminHandlerController {
  @Roles('admin')
  handle(): void {}
}

class AnyOfHandlerController {
  @Roles('editor', 'admin')
  handle(): void {}
}

class SealedHandlerController {
  @Roles()
  handle(): void {}
}

@Roles('admin')
class AdminClassController {
  handle(): void {}

  @Roles('reader')
  readerHandle(): void {}
}

type Controller =
  | typeof OpenController
  | typeof AdminHandlerController
  | typeof AnyOfHandlerController
  | typeof SealedHandlerController
  | typeof AdminClassController;

const ADMIN: AuthenticatedUser = { id: 'admin-1', email: 'boss@example.com', roles: ['admin'] };
const READER: AuthenticatedUser = { id: 'reader-1', roles: ['reader'] };
const NO_ROLES: AuthenticatedUser = { id: 'nobody-1', roles: [] };

function contextFor(
  user: AuthenticatedUser | undefined,
  controller: Controller,
  handler: () => void = controller.prototype.handle,
): ExecutionContext {
  const request = { user } as AuthenticatedRequest;
  return new ExecutionContextHost([request], controller, handler);
}

/** Validates src/common/auth/roles.guard.ts RolesGuard. */
describe('RolesGuard', () => {
  const guard = new RolesGuard(new Reflector());
  let warn: jest.SpyInstance;

  beforeEach(() => {
    warn = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('when the route has no @Roles, then an authenticated caller passes', () => {
    expect(guard.canActivate(contextFor(READER, OpenController))).toBe(true);
  });

  it('when the route has no @Roles, then a caller without identity passes too', () => {
    expect(guard.canActivate(contextFor(undefined, OpenController))).toBe(true);
  });

  it('when the caller holds the required role, then the request passes', () => {
    expect(guard.canActivate(contextFor(ADMIN, AdminHandlerController))).toBe(true);
  });

  it('when the caller holds one of several accepted roles, then the request passes', () => {
    expect(guard.canActivate(contextFor(ADMIN, AnyOfHandlerController))).toBe(true);
  });

  it('when the caller holds none of the required roles, then it answers 403 with the generic message', () => {
    expect(() => guard.canActivate(contextFor(READER, AdminHandlerController))).toThrow(
      new ForbiddenException(INSUFFICIENT_SCOPE_MESSAGE),
    );
  });

  it('when the caller has no roles at all, then it answers 403', () => {
    expect(() => guard.canActivate(contextFor(NO_ROLES, AdminHandlerController))).toThrow(
      ForbiddenException,
    );
  });

  it('when a role differs only in case, then it does not match', () => {
    const upperCaseAdmin: AuthenticatedUser = { id: 'admin-2', roles: ['Admin'] };

    expect(() => guard.canActivate(contextFor(upperCaseAdmin, AdminHandlerController))).toThrow(
      ForbiddenException,
    );
  });

  it('when no identity is attached, then a @Roles route is denied with 403 (fail closed)', () => {
    expect(() => guard.canActivate(contextFor(undefined, AdminHandlerController))).toThrow(
      ForbiddenException,
    );
  });

  it('when @Roles lists no role, then every caller is denied', () => {
    expect(() => guard.canActivate(contextFor(ADMIN, SealedHandlerController))).toThrow(
      ForbiddenException,
    );
  });

  it('when only the class carries @Roles, then the handler inherits it', () => {
    expect(guard.canActivate(contextFor(ADMIN, AdminClassController))).toBe(true);
    expect(() => guard.canActivate(contextFor(READER, AdminClassController))).toThrow(
      ForbiddenException,
    );
  });

  it('when the handler and the class both carry @Roles, then the handler wins', () => {
    expect(
      guard.canActivate(
        contextFor(READER, AdminClassController, AdminClassController.prototype.readerHandle),
      ),
    ).toBe(true);
    expect(() =>
      guard.canActivate(
        contextFor(ADMIN, AdminClassController, AdminClassController.prototype.readerHandle),
      ),
    ).toThrow(ForbiddenException);
  });

  it('when a caller is denied, then the response never names the required roles', () => {
    let message = '';
    try {
      guard.canActivate(contextFor(READER, AdminHandlerController));
    } catch (error) {
      message = error instanceof Error ? error.message : '';
    }

    expect(message).toBe(INSUFFICIENT_SCOPE_MESSAGE);
    expect(message).not.toContain('admin');
  });

  it('when a caller is denied, then one warn line carries the opaque id and no email or role', () => {
    expect(() => guard.canActivate(contextFor(ADMIN, SealedHandlerController))).toThrow();

    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledWith({
      msg: 'Request rejected by roles guard',
      status: 403,
      actorId: 'admin-1',
    });
  });

  it('when a caller passes, then nothing is logged', () => {
    guard.canActivate(contextFor(ADMIN, AdminHandlerController));

    expect(warn).not.toHaveBeenCalled();
  });
});
