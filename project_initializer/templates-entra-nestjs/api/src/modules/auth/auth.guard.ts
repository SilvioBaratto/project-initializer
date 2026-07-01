import {
  CanActivate,
  ExecutionContext,
  HttpException,
  Injectable,
  Logger,
  UnauthorizedException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { IS_PUBLIC_KEY } from '../../common/decorators/public.decorator';
import { AuthService } from './auth.service';

@Injectable()
export class EntraAuthGuard implements CanActivate {
  private readonly logger = new Logger(EntraAuthGuard.name);

  constructor(
    private readonly authService: AuthService,
    private readonly reflector: Reflector,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) {
      return true;
    }

    const request = context.switchToHttp().getRequest();
    const authHeader = request.headers['authorization'] as string | undefined;

    if (!authHeader || !authHeader.toLowerCase().startsWith('bearer ')) {
      throw new UnauthorizedException('Missing or invalid authorization header');
    }

    const token = authHeader.slice(7).trim();
    if (!token) {
      throw new UnauthorizedException('Missing or invalid authorization header');
    }

    try {
      const user = await this.authService.getUser(token);
      request.user = user;
      return true;
    } catch (error) {
      this.logger.warn(`Auth failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      // Re-throw any HttpException (including ForbiddenException for 403) unchanged.
      if (error instanceof HttpException) throw error;
      throw new UnauthorizedException('Authentication failed');
    }
  }
}
