import { Controller, Post, Body, SerializeOptions } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { AuthService } from './auth.service';
import {
  AuthRequestSchema,
  AuthResponseSchema,
  AuthRequestDto,
  AuthResponseDto,
} from './dto/auth.dto';
import { Public } from '../../common/decorators/public.decorator';

/** Token-auth endpoint that validates a bearer token and reports authentication status. */
@ApiTags('Auth')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('validate')
  @Public()
  @SerializeOptions({ schema: AuthResponseSchema })
  @ApiOperation({ summary: 'Validate an authentication token' })
  validate(
    @Body({ schema: AuthRequestSchema }) authRequest: AuthRequestDto,
  ): AuthResponseDto {
    return this.authService.validateToken(authRequest.token);
  }
}
