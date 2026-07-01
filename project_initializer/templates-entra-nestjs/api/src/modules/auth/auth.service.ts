import {
  ForbiddenException,
  Injectable,
  Logger,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as jwt from 'jsonwebtoken';
import * as jwksRsa from 'jwks-rsa';

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);
  private readonly jwksClient: jwksRsa.JwksClient;
  private readonly tenantId: string;
  private readonly audience: string[];
  private readonly requiredScope: string;

  constructor(private readonly configService: ConfigService) {
    this.tenantId = this.configService.getOrThrow<string>('ENTRA_TENANT_ID');
    const clientId = this.configService.getOrThrow<string>('ENTRA_API_CLIENT_ID');
    const audienceEnv = this.configService.getOrThrow<string>('ENTRA_API_AUDIENCE');
    // Accept both the GUID and the api:// URI form (comment: covers both Entra audience formats)
    this.audience = [clientId, audienceEnv].filter((v, i, a) => a.indexOf(v) === i);
    this.requiredScope = this.configService.getOrThrow<string>('ENTRA_API_SCOPE');

    this.jwksClient = jwksRsa({
      jwksUri: `https://login.microsoftonline.com/${this.tenantId}/discovery/v2.0/keys`,
      cache: true,
      rateLimit: true,
    });
    this.logger.log('Entra auth service initialized');
  }

  async getUser(token: string): Promise<{ id: string; email: string; role: string }> {
    const decoded = await this.verifyToken(token);
    this.assertTid(decoded);
    this.assertScope(decoded);
    return this.extractUser(decoded);
  }

  private verifyToken(token: string): Promise<jwt.JwtPayload> {
    return new Promise((resolve, reject) => {
      const getKey: jwt.GetPublicKeyOrSecret = (header, callback) => {
        this.jwksClient.getSigningKey(header.kid, (err, key) => {
          if (err) return callback(err);
          callback(null, key?.getPublicKey());
        });
      };

      jwt.verify(
        token,
        getKey,
        {
          algorithms: ['RS256'],
          audience: this.audience,
          issuer: `https://login.microsoftonline.com/${this.tenantId}/v2.0`,
        },
        (err, decoded) => {
          if (err) {
            this.logger.warn(`Token verification failed: ${err.message}`);
            return reject(new UnauthorizedException('Invalid or expired token'));
          }
          resolve(decoded as jwt.JwtPayload);
        },
      );
    });
  }

  private assertTid(payload: jwt.JwtPayload): void {
    if (payload['tid'] !== this.tenantId) {
      throw new UnauthorizedException('Token tenant mismatch');
    }
  }

  private assertScope(payload: jwt.JwtPayload): void {
    const scp: string = payload['scp'] ?? '';
    const scopes = scp.split(' ').filter(Boolean);
    if (!scopes.includes(this.requiredScope)) {
      throw new ForbiddenException('Insufficient scope');
    }
  }

  private extractUser(payload: jwt.JwtPayload): { id: string; email: string; role: string } {
    const roles: string[] = payload['roles'] ?? [];
    return {
      id: (payload['oid'] ?? payload['sub'] ?? '') as string,
      email: (payload['preferred_username'] ?? '') as string,
      role: roles[0] ?? 'authenticated',
    };
  }
}
