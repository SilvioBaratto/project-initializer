import { z } from 'zod';
import { MAX_BEARER_TOKEN_LENGTH } from '../../../common/auth/bearer-token';

/**
 * Request body of `POST /auth/validate`. The token is trimmed and capped exactly like a bearer
 * credential, so a token is valid here if and only if the guard would accept it.
 */
export const AuthRequestSchema = z.object({
  token: z.string().trim().min(1, 'Token is required').max(MAX_BEARER_TOKEN_LENGTH),
});

/** Result of `POST /auth/validate`; a wrong token is a normal answer, not an HTTP error. */
export const AuthResponseSchema = z.object({
  authenticated: z.boolean(),
  message: z.string(),
});

/** Validated body of `POST /auth/validate`. */
export type AuthRequestDto = z.infer<typeof AuthRequestSchema>;
/** Response body of `POST /auth/validate`. */
export type AuthResponseDto = z.infer<typeof AuthResponseSchema>;
