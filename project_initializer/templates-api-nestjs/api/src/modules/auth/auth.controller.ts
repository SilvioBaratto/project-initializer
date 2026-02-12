import { Controller, Post, Body } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { AuthService } from './auth.service';
import { AuthRequestDto, AuthResponseDto } from './dto/auth.dto';

@ApiTags('auth')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('validate')
  @ApiOperation({ summary: 'Validate authentication token' })
  validateToken(@Body() request: AuthRequestDto): AuthResponseDto {
    return this.authService.validateToken(request);
  }
}
