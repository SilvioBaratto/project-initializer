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

/** Public token-validation endpoint for the no-auth base template. */
@ApiTags('auth')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('validate')
  @Public()
  @SerializeOptions({ schema: AuthResponseSchema })
  @ApiOperation({ summary: 'Validate authentication token' })
  validateToken(
    @Body({ schema: AuthRequestSchema }) request: AuthRequestDto,
  ): AuthResponseDto {
    return this.authService.validateToken(request);
  }
}
