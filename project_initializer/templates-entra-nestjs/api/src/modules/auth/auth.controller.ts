import { Controller, Get } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { ZodSerializerDto } from 'nestjs-zod';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { UserInfoDto } from './dto/auth.dto';

@ApiTags('auth')
@Controller('auth')
export class AuthController {
  @Get('me')
  @ZodSerializerDto(UserInfoDto)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Get current authenticated user info' })
  getMe(@CurrentUser() user: UserInfoDto): UserInfoDto {
    return user;
  }
}
