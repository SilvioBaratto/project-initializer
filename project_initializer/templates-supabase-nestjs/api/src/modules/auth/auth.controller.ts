import { Controller, Get, SerializeOptions } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { UserInfoSchema, UserInfoDto } from './dto/auth.dto';

/** Returns the current Supabase-authenticated user's profile. */
@ApiTags('auth')
@Controller('auth')
export class AuthController {
  @Get('me')
  @SerializeOptions({ schema: UserInfoSchema })
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Get current authenticated user info' })
  getMe(@CurrentUser() user: UserInfoDto): UserInfoDto {
    return user;
  }
}
