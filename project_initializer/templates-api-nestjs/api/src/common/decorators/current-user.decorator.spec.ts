import { ExecutionContext } from '@nestjs/common';
import { ROUTE_ARGS_METADATA } from '@nestjs/common/constants';
import { ExecutionContextHost } from '@nestjs/core/helpers/execution-context-host';
import { AuthenticatedRequest, AuthenticatedUser } from '../auth/authenticated-user';
import { CurrentUser } from './current-user.decorator';

type ParamFactory = (data: unknown, context: ExecutionContext) => unknown;

class ProbeController {
  handle(@CurrentUser() user: AuthenticatedUser | undefined): AuthenticatedUser | undefined {
    return user;
  }
}

function resolveParam(request: Partial<AuthenticatedRequest>): unknown {
  const metadata = Reflect.getMetadata(ROUTE_ARGS_METADATA, ProbeController, 'handle') as Record<
    string,
    { factory: ParamFactory }
  >;
  const [{ factory }] = Object.values(metadata);
  return factory(undefined, new ExecutionContextHost([request]));
}

/** Validates src/common/decorators/current-user.decorator.ts CurrentUser. */
describe('CurrentUser', () => {
  it('when the guard attached an identity, then the parameter resolves to it', () => {
    const user: AuthenticatedUser = { id: 'user-1', roles: [] };

    expect(resolveParam({ user })).toBe(user);
  });

  it('when no identity is attached, then the parameter resolves to undefined', () => {
    expect(resolveParam({})).toBeUndefined();
  });
});
