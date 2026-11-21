/** Client-facing text for a request without a usable bearer token. */
export const AUTHENTICATION_REQUIRED_MESSAGE = 'Authentication required';

/**
 * Deliberately identical for every credential failure (unknown, expired, malformed), so a
 * response never tells an attacker which part of the credential was wrong.
 */
export const INVALID_CREDENTIALS_MESSAGE = 'Invalid or expired credentials';

/** Client-facing text for a valid identity that lacks the scope or the role the API requires. */
export const INSUFFICIENT_SCOPE_MESSAGE = 'Insufficient permissions';

/** Client-facing text when the identity provider could not be reached to check a token. */
export const AUTH_PROVIDER_UNAVAILABLE_MESSAGE = 'Authentication service temporarily unavailable';
