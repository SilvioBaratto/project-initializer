import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createHmac, timingSafeEqual } from 'crypto';
import { AuthResponseDto } from './dto/auth.dto';

@Injectable()
export class AuthService {
  private readonly authToken: string;

  constructor(private readonly configService: ConfigService) {
    this.authToken = this.configService.get<string>('AUTH_TOKEN', 'changeme');
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
