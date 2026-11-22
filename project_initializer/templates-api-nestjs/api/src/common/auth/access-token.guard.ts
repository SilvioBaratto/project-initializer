import {
  CanActivate,
  ExecutionContext,
  HttpException,
  Inject,
  Injectable,
  Logger,
  UnauthorizedException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { IS_PUBLIC_KEY } from '../decorators/public.decorator';
import { describeError } from '../describe-error';
import { requestPathOf } from '../filters/error-body';
import { ACCESS_TOKEN_VERIFIER, AccessTokenVerifier } from './access-token-verifier';
import { AUTHENTICATION_REQUIRED_MESSAGE, INVALID_CREDENTIALS_MESSAGE } from './auth-messages';
import { AuthenticatedRequest, AuthenticatedUser } from './authenticated-user';
import { extractBearerToken } from './bearer-token';

/** `nestjs-pino` stores the request correlation id on the request as `id`. */
type LoggedRequest = AuthenticatedRequest & { id?: unknown };

function requestIdOf(request: LoggedRequest): string | undefined {
  const { id } = request;
  return typeof id === 'string' || typeof id === 'number' ? String(id) : undefined;
}

/**
 * Global guard that requires a verified bearer token on every route not marked `@Public()`.
 *
 * The credential check itself lives behind {@link ACCESS_TOKEN_VERIFIER}, so one guard serves
 * every auth variant. On success the resolved identity is attached as `request.user`.
 *
 * Failure mapping: no usable token gives 401; an `HttpException` from the verifier (401, 403, 503)
 * passes through unchanged; any other error becomes a generic 401 and is logged with its stack.
 * Each rejection writes exactly one warn audit line carrying status, method, path and request id.
 * The token and the caller's email are never logged.
 */
@Injectable()
export class AccessTokenGuard implements CanActivate {
  private readonly logger = new Logger(AccessTokenGuard.name);

  constructor(
    private readonly reflector: Reflector,
    @Inject(ACCESS_TOKEN_VERIFIER) private readonly verifier: AccessTokenVerifier,
  ) {}

  /**
   * @returns `true` when the route is public or the token verified.
   * @throws HttpException 401 without a usable token, otherwise whatever the verifier threw.
   */
  async canActivate(context: ExecutionContext): Promise<boolean> {
    if (this.isPublic(context)) {
      return true;
    }
    const request = context.switchToHttp().getRequest<LoggedRequest>();
    const token = extractBearerToken(request.headers.authorization);
    if (token === null) {
      throw this.reject(request, new UnauthorizedException(AUTHENTICATION_REQUIRED_MESSAGE));
    }
    request.user = await this.verify(token, request);
    return true;
  }

  private isPublic(context: ExecutionContext): boolean {
    return (
      this.reflector.getAllAndOverride<boolean | undefined>(IS_PUBLIC_KEY, [
        context.getHandler(),
        context.getClass(),
      ]) === true
    );
  }

  private async verify(token: string, request: LoggedRequest): Promise<AuthenticatedUser> {
    try {
      return await this.verifier.verify(token);
    } catch (error) {
      throw this.reject(request, this.toHttpException(error));
    }
  }

  private toHttpException(error: unknown): HttpException {
    if (error instanceof HttpException) {
      return error;
    }
    this.logger.error('Access token verifier failed unexpectedly', describeError(error));
    return new UnauthorizedException(INVALID_CREDENTIALS_MESSAGE);
  }

  private reject(request: LoggedRequest, exception: HttpException): HttpException {
    this.logger.warn({
      msg: 'Request rejected by access token guard',
      status: exception.getStatus(),
      method: request.method,
      path: requestPathOf(request),
      requestId: requestIdOf(request),
    });
    return exception;
  }
}
