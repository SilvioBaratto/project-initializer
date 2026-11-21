import { Controller, Get, UnauthorizedException } from '@nestjs/common';
import {
  ApiBearerAuth,
  ApiForbiddenResponse,
  ApiOperation,
  ApiServiceUnavailableResponse,
  ApiTags,
  ApiTooManyRequestsResponse,
  ApiUnauthorizedResponse,
} from '@nestjs/swagger';
import { ZodResponse } from 'nestjs-zod';
import { CurrentUser } from '../decorators/current-user.decorator';
import {
  AUTH_PROVIDER_UNAVAILABLE_MESSAGE,
  AUTHENTICATION_REQUIRED_MESSAGE,
  INSUFFICIENT_SCOPE_MESSAGE,
} from './auth-messages';
import { AuthenticatedUser } from './authenticated-user';
import { toUserInfo, UserInfoDto } from './user-info.dto';

/** Exposes the identity behind the presented token to authenticated callers. */
@ApiTags('Auth')
@ApiBearerAuth()
@Controller('auth')
export class CurrentUserController {
  /**
   * @param user - Identity the global guard attached to the request.
   * @returns The caller's id, email (`null` when the provider released none) and roles.
   * @throws UnauthorizedException when no identity is attached, which only happens if the global
   *   guard is not registered; failing closed beats returning an empty identity.
   * @remarks The guard, not this handler, answers 401 for a bad token, 403 for a token without the
   *   required scope (Entra), 503 when the identity provider is unreachable (Supabase, Entra) and
   *   429 once the rate limit is exhausted. They are declared here because this controller is shared
   *   by every auth variant.
   */
  @Get('me')
  @ZodResponse({ status: 200, type: UserInfoDto })
  @ApiOperation({ summary: 'Return the authenticated caller' })
  @ApiUnauthorizedResponse({ description: AUTHENTICATION_REQUIRED_MESSAGE })
  @ApiForbiddenResponse({ description: INSUFFICIENT_SCOPE_MESSAGE })
  @ApiServiceUnavailableResponse({ description: AUTH_PROVIDER_UNAVAILABLE_MESSAGE })
  @ApiTooManyRequestsResponse({ description: 'Too many requests' })
  currentUser(@CurrentUser() user: AuthenticatedUser | undefined): UserInfoDto {
    if (user === undefined) {
      throw new UnauthorizedException(AUTHENTICATION_REQUIRED_MESSAGE);
    }
    return toUserInfo(user);
  }
}
