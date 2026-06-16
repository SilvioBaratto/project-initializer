import 'reflect-metadata';
import { ExecutionContext, UnauthorizedException } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { Reflector } from '@nestjs/core';
import { AuthGuard } from './auth.guard';
import { AuthService } from './auth.service';

const mockAuthService = { validateToken: jest.fn() };
const mockReflector = { getAllAndOverride: jest.fn() };

function buildContext(headers: Record<string, string> = {}): ExecutionContext {
  const request = { headers };
  return {
    getHandler: jest.fn(),
    getClass: jest.fn(),
    switchToHttp: () => ({ getRequest: () => request }),
  } as unknown as ExecutionContext;
}

describe('AuthGuard', () => {
  let guard: AuthGuard;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuthGuard,
        { provide: AuthService, useValue: mockAuthService },
        { provide: Reflector, useValue: mockReflector },
      ],
    }).compile();
    guard = module.get<AuthGuard>(AuthGuard);
  });

  it('when route is public, canActivate returns true and validateToken is not called', () => {
    mockReflector.getAllAndOverride.mockReturnValue(true);

    const result = guard.canActivate(buildContext());

    expect(result).toBe(true);
    expect(mockAuthService.validateToken).not.toHaveBeenCalled();
  });

  it('when authorization header is missing, canActivate throws UnauthorizedException', () => {
    mockReflector.getAllAndOverride.mockReturnValue(false);

    expect(() => guard.canActivate(buildContext())).toThrow(UnauthorizedException);
  });

  it('when authorization header is non-bearer, canActivate throws UnauthorizedException', () => {
    mockReflector.getAllAndOverride.mockReturnValue(false);

    expect(() =>
      guard.canActivate(buildContext({ authorization: 'Basic abc123' })),
    ).toThrow(UnauthorizedException);
  });

  it('when token is valid, canActivate returns true', () => {
    mockReflector.getAllAndOverride.mockReturnValue(false);
    mockAuthService.validateToken.mockReturnValue({ authenticated: true, message: 'ok' });

    const result = guard.canActivate(buildContext({ authorization: 'Bearer valid-token' }));

    expect(result).toBe(true);
  });

  it('when token is invalid, canActivate throws UnauthorizedException', () => {
    mockReflector.getAllAndOverride.mockReturnValue(false);
    mockAuthService.validateToken.mockReturnValue({ authenticated: false, message: 'Invalid token' });

    expect(() =>
      guard.canActivate(buildContext({ authorization: 'Bearer bad-token' })),
    ).toThrow(UnauthorizedException);
  });
});
