import {
  ForbiddenException,
  Inject,
  Injectable,
  Logger,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as jwt from 'jsonwebtoken';
import { JwksClient, SigningKeyNotFoundError } from 'jwks-rsa';
import { z } from 'zod';
import { AccessTokenVerifier } from '../../common/auth/access-token-verifier';
import {
  AUTH_PROVIDER_UNAVAILABLE_MESSAGE,
  INSUFFICIENT_SCOPE_MESSAGE,
  INVALID_CREDENTIALS_MESSAGE,
} from '../../common/auth/auth-messages';
import { AuthenticatedUser } from '../../common/auth/authenticated-user';
import { toOptionalEmail } from '../../common/auth/optional-email';
import { Env } from '../../config/env.validation';

/** Sign-in authority of the Microsoft identity platform; issuer and key set hang off it. */
export const ENTRA_AUTHORITY_HOST = 'https://login.microsoftonline.com';

const ENTRA_SIGNING_ALGORITHM: jwt.Algorithm = 'RS256';
const SCOPE_CLAIM_SEPARATOR = ' ';

// Entra and this server do not share a clock; without tolerance a token issued a moment ago can
// be refused as "not yet valid", or one that just expired still be served.
const CLOCK_TOLERANCE_SECONDS = 30;

const MILLISECONDS_PER_HOUR = 3_600_000;

// Keys rotate over weeks and the old one stays published during the overlap, so a long cache
// keeps almost every request off the network. A kid that is not cached costs one fetch, and
// unknown kids are rate-limited by the client.
const JWKS_CACHE_MAX_AGE_MS = 24 * MILLISECONDS_PER_HOUR;

// Every uncached token check waits for this fetch; the library default of 30 s would hold each of
// them open for that long when Microsoft is slow.
const JWKS_REQUEST_TIMEOUT_MS = 5_000;

function entraAuthority(tenantId: string): string {
  return `${ENTRA_AUTHORITY_HOST}/${tenantId}`;
}

/**
 * Issuer (`iss`) that v2.0 access tokens of a tenant carry.
 *
 * @param tenantId - Directory (tenant) id of the Entra tenant.
 */
export function entraIssuer(tenantId: string): string {
  return `${entraAuthority(tenantId)}/v2.0`;
}

/**
 * Location of the public keys that sign a tenant's v2.0 tokens.
 *
 * @param tenantId - Directory (tenant) id of the Entra tenant.
 */
export function entraJwksUri(tenantId: string): string {
  return `${entraAuthority(tenantId)}/discovery/v2.0/keys`;
}

/**
 * Claims of a v2.0 access token that this API reads; every other claim is dropped.
 *
 * `oid` is required because it is the stable per-tenant user id. `exp` and `iat` are required
 * because the signature check alone accepts a token that has none, which would then never expire.
 * `preferred_username` is optional and not guaranteed to be an email address (guest and service
 * accounts differ).
 */
export const EntraClaimsSchema = z.object({
  tid: z.string(),
  oid: z.guid(),
  exp: z.number(),
  iat: z.number(),
  scp: z.string().optional(),
  roles: z.array(z.string()).optional(),
  preferred_username: z.string().optional(),
});

/** Parsed claims of a verified Entra access token. */
export type EntraClaims = z.output<typeof EntraClaimsSchema>;

/** Injection token for the {@link SigningKeyResolver} that {@link AuthService} verifies with. */
export const SIGNING_KEY_RESOLVER = Symbol('SIGNING_KEY_RESOLVER');

/**
 * Looks up the PEM public key that matches a token's `kid` header.
 *
 * Injected so specs can supply keys they generated instead of fetching Microsoft's.
 * Implementations throw `SigningKeyNotFoundError` for an unknown key id and any other error when
 * the key set cannot be retrieved. The key id is always present: a token without one is refused
 * before the lookup.
 */
export type SigningKeyResolver = (kid: string) => Promise<string>;

/**
 * Creates the production resolver, backed by the tenant's JWKS endpoint.
 *
 * The client caches keys for a day, bounds each fetch to a few seconds and rate-limits refetches,
 * so key rotation is picked up on demand and a flood of unknown key ids cannot turn into a flood
 * of requests to Microsoft. Once that limit is hit the client throws `JwksRateLimitError`, which
 * the verifier reports as 503.
 *
 * @param tenantId - Directory (tenant) id whose key set is used.
 */
export function createJwksSigningKeyResolver(tenantId: string): SigningKeyResolver {
  const jwksClient = new JwksClient({
    jwksUri: entraJwksUri(tenantId),
    cache: true,
    cacheMaxAge: JWKS_CACHE_MAX_AGE_MS,
    rateLimit: true,
    timeout: JWKS_REQUEST_TIMEOUT_MS,
  });
  return async (kid) => (await jwksClient.getSigningKey(kid)).getPublicKey();
}

function toAuthenticatedUser(claims: EntraClaims): AuthenticatedUser {
  return {
    id: claims.oid,
    // Display-only: `preferred_username` is mutable and need not be an address, so it never
    // identifies the caller; `id` does.
    email: toOptionalEmail(claims.preferred_username),
    roles: claims.roles ?? [],
  };
}

/**
 * Verifies Microsoft Entra ID v2.0 access tokens for this API.
 *
 * A token is accepted only when it is RS256 signed by a key of the configured tenant, was issued
 * by that tenant, is addressed to this API (client id or configured audience), carries `exp` and
 * `iat` and has not expired (within a 30 second clock tolerance), and carries the required
 * delegated scope in `scp`. No client secret is involved.
 *
 * Failure mapping: an invalid token is a 401 whose text never says which check failed, a missing
 * scope is a 403, and an unreachable or rate-limited key set is a 503 that carries the cause, so
 * clients retry instead of re-authenticating. The verifier does not log a 503; the exception
 * filter does.
 */
@Injectable()
export class AuthService implements AccessTokenVerifier {
  private readonly logger = new Logger(AuthService.name);
  private readonly tenantId: string;
  private readonly issuer: string;
  private readonly audiences: [string, ...string[]];
  private readonly requiredScope: string;

  constructor(
    config: ConfigService<Env, true>,
    @Inject(SIGNING_KEY_RESOLVER) private readonly signingKeyResolver: SigningKeyResolver,
  ) {
    this.tenantId = config.get('ENTRA_TENANT_ID', { infer: true });
    this.issuer = entraIssuer(this.tenantId);
    // A v2.0 access token names the API's client id in `aud`. The configured audience (normally
    // the `api://` URI of the registration) is accepted as well, so a registration that reports
    // its application ID URI still verifies.
    const clientId = config.get('ENTRA_API_CLIENT_ID', { infer: true });
    const audience = config.get('ENTRA_API_AUDIENCE', { infer: true });
    this.audiences = audience === clientId ? [clientId] : [clientId, audience];
    this.requiredScope = config.get('ENTRA_API_SCOPE', { infer: true });
  }

  /**
   * @param token - Raw bearer token.
   * @returns The caller's identity; `email` is set only when `preferred_username` is an address.
   * @throws UnauthorizedException when the token is malformed, mis-signed, expired, addressed to
   *   another API, issued by another tenant, or lacks the `oid`, `exp` or `iat` claim.
   * @throws ForbiddenException when the token is valid but its `scp` lacks the required scope.
   * @throws ServiceUnavailableException when the signing keys cannot be retrieved, or the fetch
   *   was refused by the rate limit; the failure is attached as `cause`.
   */
  async verify(token: string): Promise<AuthenticatedUser> {
    const keyId = this.readKeyId(token);
    const publicKey = await this.resolvePublicKey(keyId);
    const claims = this.parseClaims(this.verifySignature(token, publicKey));
    this.assertTenant(claims);
    this.assertScope(claims);
    return toAuthenticatedUser(claims);
  }

  // Rejecting before the key lookup keeps forged tokens (HS256, `alg: none`, no `kid`) from
  // costing a JWKS fetch.
  private readKeyId(token: string): string {
    const header = jwt.decode(token, { complete: true })?.header;
    if (header === undefined) {
      throw this.invalidCredentials('Token is not a decodable JWT');
    }
    if (header.alg !== ENTRA_SIGNING_ALGORITHM) {
      throw this.invalidCredentials(`Token algorithm ${header.alg} is not accepted`);
    }
    if (!header.kid) {
      throw this.invalidCredentials('Token header has no key id');
    }
    return header.kid;
  }

  private async resolvePublicKey(keyId: string): Promise<string> {
    try {
      return await this.signingKeyResolver(keyId);
    } catch (error) {
      if (error instanceof SigningKeyNotFoundError) {
        throw this.invalidCredentials('No signing key matches the token key id');
      }
      throw new ServiceUnavailableException(AUTH_PROVIDER_UNAVAILABLE_MESSAGE, { cause: error });
    }
  }

  private verifySignature(token: string, publicKey: string): string | jwt.JwtPayload {
    try {
      return jwt.verify(token, publicKey, {
        algorithms: [ENTRA_SIGNING_ALGORITHM],
        audience: this.audiences,
        issuer: this.issuer,
        clockTolerance: CLOCK_TOLERANCE_SECONDS,
      });
    } catch (error) {
      throw this.invalidCredentials(
        error instanceof Error ? error.message : 'Token verification failed',
      );
    }
  }

  private parseClaims(payload: string | jwt.JwtPayload): EntraClaims {
    const parsed = EntraClaimsSchema.safeParse(payload);
    if (!parsed.success) {
      const claimNames = parsed.error.issues.map((issue) => issue.path.join('.'));
      throw this.invalidCredentials(`Token claims invalid: ${claimNames.join(', ')}`);
    }
    return parsed.data;
  }

  // The issuer already pins the tenant; this guards against a mis-issued token and keeps the
  // client-facing message generic so a response never confirms which tenant is configured.
  private assertTenant(claims: EntraClaims): void {
    if (claims.tid !== this.tenantId) {
      throw this.invalidCredentials('Token tid does not match the configured tenant');
    }
  }

  // Scopes are compared whole, so a granted `access_as_user_admin` does not satisfy `access_as_user`.
  private assertScope(claims: EntraClaims): void {
    const grantedScopes = (claims.scp ?? '').split(SCOPE_CLAIM_SEPARATOR);
    if (!grantedScopes.includes(this.requiredScope)) {
      throw new ForbiddenException(INSUFFICIENT_SCOPE_MESSAGE);
    }
  }

  // The reason is logged at debug level only: the guard already writes the one audit line per
  // rejection, and the reason must not reach the client.
  private invalidCredentials(reason: string): UnauthorizedException {
    this.logger.debug(reason);
    return new UnauthorizedException(INVALID_CREDENTIALS_MESSAGE);
  }
}
