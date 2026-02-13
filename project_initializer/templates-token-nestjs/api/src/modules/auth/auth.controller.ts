import { Controller, Post, Body } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { AuthService } from './auth.service';
import { AuthRequestDto, AuthResponseDto } from './dto/auth.dto';
import { Public } from '../../common/decorators/public.decorator';

@ApiTags('Auth')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('validate')
  @Public()
  @ApiOperation({ summary: 'Validate an authentication token' })
  validate(@Body() authRequest: AuthRequestDto): AuthResponseDto {
    return this.authService.validateToken(authRequest.token);
  }
}
