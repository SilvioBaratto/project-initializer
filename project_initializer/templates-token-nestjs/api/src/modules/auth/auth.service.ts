import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { timingSafeEqual } from 'crypto';
import { AuthResponseDto } from './dto/auth.dto';

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);
  private readonly authToken: string;

  constructor(private readonly configService: ConfigService) {
    this.authToken = this.configService.getOrThrow<string>('AUTH_TOKEN');

    if (this.authToken === 'changeme' || this.authToken.length < 16) {
      this.logger.warn(
        'AUTH_TOKEN is weak (default or shorter than 16 chars). Use a strong token in production.',
      );
    }
  }

  validateToken(token: string): AuthResponseDto {
    if (this.timingSafeCompare(token, this.authToken)) {
      return { authenticated: true, message: 'Authentication successful' };
    }
    return { authenticated: false, message: 'Invalid token' };
  }

  private timingSafeCompare(a: string, b: string): boolean {
    try {
      const bufA = Buffer.from(a, 'utf-8');
      const bufB = Buffer.from(b, 'utf-8');
      if (bufA.length !== bufB.length) {
        // Compare against self to maintain constant time
        timingSafeEqual(bufA, bufA);
        return false;
      }
      return timingSafeEqual(bufA, bufB);
    } catch {
      return false;
    }
  }
}
