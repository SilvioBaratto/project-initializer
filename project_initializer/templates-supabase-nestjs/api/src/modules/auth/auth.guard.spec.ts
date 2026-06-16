import 'reflect-metadata';
import { ExecutionContext, UnauthorizedException } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { Reflector } from '@nestjs/core';
import { SupabaseAuthGuard } from './auth.guard';
import { AuthService } from './auth.service';

const mockAuthService = { getUser: jest.fn() };
const mockReflector = { getAllAndOverride: jest.fn() };

function buildContext(headers: Record<string, string> = {}): {
  ctx: ExecutionContext;
  request: Record<string, unknown>;
} {
  const request: Record<string, unknown> = { headers };
  const ctx = {
    getHandler: jest.fn(),
    getClass: jest.fn(),
    switchToHttp: () => ({ getRequest: () => request }),
  } as unknown as ExecutionContext;
  return { ctx, request };
}

describe('SupabaseAuthGuard', () => {
  let guard: SupabaseAuthGuard;

  beforeEach(async () => {
    jest.clearAllMocks();
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        SupabaseAuthGuard,
        { provide: AuthService, useValue: mockAuthService },
        { provide: Reflector, useValue: mockReflector },
      ],
    }).compile();
    guard = module.get<SupabaseAuthGuard>(SupabaseAuthGuard);
  });

  it('when route is public, canActivate resolves true and getUser is not called', async () => {
    mockReflector.getAllAndOverride.mockReturnValue(true);
    const { ctx } = buildContext();

    const result = await guard.canActivate(ctx);

    expect(result).toBe(true);
    expect(mockAuthService.getUser).not.toHaveBeenCalled();
  });

  it('when authorization header is missing, canActivate throws UnauthorizedException', async () => {
    mockReflector.getAllAndOverride.mockReturnValue(false);
    const { ctx } = buildContext();

    await expect(guard.canActivate(ctx)).rejects.toThrow(UnauthorizedException);
  });

  it('when authorization header is non-bearer, canActivate throws UnauthorizedException', async () => {
    mockReflector.getAllAndOverride.mockReturnValue(false);
    const { ctx } = buildContext({ authorization: 'Basic abc123' });

    await expect(guard.canActivate(ctx)).rejects.toThrow(UnauthorizedException);
  });

  it('when token is valid, canActivate resolves true and sets request.user', async () => {
    const user = { id: 'user-1', email: 'user@example.com', role: 'authenticated' };
    mockReflector.getAllAndOverride.mockReturnValue(false);
    mockAuthService.getUser.mockResolvedValue(user);
    const { ctx, request } = buildContext({ authorization: 'Bearer valid-token' });

    const result = await guard.canActivate(ctx);

    expect(result).toBe(true);
    expect(request.user).toEqual(user);
  });

  it('when token is invalid, canActivate throws UnauthorizedException', async () => {
    mockReflector.getAllAndOverride.mockReturnValue(false);
    mockAuthService.getUser.mockRejectedValue(new UnauthorizedException('Invalid or expired token'));
    const { ctx } = buildContext({ authorization: 'Bearer bad-token' });

    await expect(guard.canActivate(ctx)).rejects.toThrow(UnauthorizedException);
  });
});
