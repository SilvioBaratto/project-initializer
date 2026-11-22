import { Body, Controller, HttpCode, HttpStatus, Post } from '@nestjs/common';
import {
  ApiBadRequestResponse,
  ApiOperation,
  ApiTags,
  ApiTooManyRequestsResponse,
} from '@nestjs/swagger';
import { Throttle } from '@nestjs/throttler';
import { Public } from '../../common/decorators/public.decorator';
import { ResponseSchema } from '../../common/serialization/response-schema.decorator';
import { AUTH_PROBE_RATE_LIMIT } from '../../config/rate-limit';
import { AuthService } from './auth.service';
import {
  AuthRequestSchema,
  AuthResponseSchema,
  type AuthRequestDto,
  type AuthResponseDto,
} from './dto/auth.dto';

/** Token-variant endpoints under `/auth`; `GET /auth/me` lives in the shared `CurrentUserController`. */
@ApiTags('Auth')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  /**
   * Public so a client can test a token before storing it. The tight rate limit is what stops this
   * endpoint from being used to guess the shared secret. Answers 200 rather than 201 because
   * nothing is created.
   *
   * @param authRequest - Body carrying the candidate secret.
   * @returns `authenticated: true` for the shared secret and `authenticated: false` for anything
   *   else; a wrong token is an answer, not an error.
   */
  @Post('validate')
  @Public()
  @Throttle(AUTH_PROBE_RATE_LIMIT)
  @HttpCode(HttpStatus.OK)
  @ResponseSchema(HttpStatus.OK, AuthResponseSchema)
  @ApiOperation({ summary: 'Validate an authentication token' })
  @ApiBadRequestResponse({ description: 'The body is not a token request' })
  @ApiTooManyRequestsResponse({ description: 'Too many validation attempts' })
  validate(@Body({ schema: AuthRequestSchema }) authRequest: AuthRequestDto): AuthResponseDto {
    return this.authService.validateToken(authRequest.token);
  }
}
