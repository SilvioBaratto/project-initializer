import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { EntraAuthGuard } from './auth.guard';

@Module({
  imports: [ConfigModule],
  controllers: [AuthController],
  providers: [AuthService, EntraAuthGuard],
  exports: [AuthService, EntraAuthGuard],
})
export class AuthModule {}
