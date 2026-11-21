/**
 * Upper bound for an accepted bearer token. Real tokens (JWTs with several claims) stay well below
 * it; the cap keeps a crafted header from reaching signature checks or key lookups at full size.
 */
export const MAX_BEARER_TOKEN_LENGTH = 8_192;

// The credential is one run of non-space characters (RFC 6750 token68), so `Bearer a b` is not a
// token. Both runs of blanks are matched by classes disjoint from `\S`, which keeps matching linear.
const BEARER_HEADER_PATTERN = /^bearer[ \t]+(\S+)[ \t]*$/i;

/**
 * Extracts the credential from an `Authorization` header value.
 *
 * @param header - Raw header value. An array (repeated header) is never accepted, because picking
 *   one of several credentials would be ambiguous.
 * @returns The token without scheme and surrounding blanks, or `null` when the header is missing,
 *   uses another scheme, carries an empty token, or exceeds {@link MAX_BEARER_TOKEN_LENGTH}.
 *   The scheme name is matched case-insensitively.
 */
export function extractBearerToken(header: string | string[] | undefined): string | null {
  if (typeof header !== 'string') {
    return null;
  }
  const token = BEARER_HEADER_PATTERN.exec(header)?.[1];
  if (token === undefined || token.length > MAX_BEARER_TOKEN_LENGTH) {
    return null;
  }
  return token;
}
