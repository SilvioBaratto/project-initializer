import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createHash, timingSafeEqual } from 'crypto';
import { AuthRequestDto, AuthResponseDto } from './dto/auth.dto';

@Injectable()
export class AuthService {
  private readonly authToken: string;

  constructor(private readonly configService: ConfigService) {
    this.authToken = this.configService.get<string>('AUTH_TOKEN', 'changeme');
  }

  validateToken(request: AuthRequestDto): AuthResponseDto {
    const isValid = this.constantTimeCompare(
      request.token,
      this.authToken,
    );

    if (isValid) {
      return {
        authenticated: true,
        message: 'Authentication successful',
      };
    }

    return {
      authenticated: false,
      message: 'Invalid token',
    };
  }

  /**
   * Performs constant-time string comparison to prevent timing attacks.
   * Uses SHA256 hashing to ensure equal-length buffers for timingSafeEqual.
   */
  private constantTimeCompare(a: string, b: string): boolean {
    const hashA = createHash('sha256').update(a).digest();
    const hashB = createHash('sha256').update(b).digest();
    return timingSafeEqual(hashA, hashB);
  }
}
