const SCOPE_URI_SEPARATOR = '/';

/**
 * Reduces a configured scope to the bare name that the `scp` claim carries.
 *
 * The portal displays a scope as `api://<client-id>/access_as_user`, but a token lists only
 * `access_as_user`; accepting both spellings in configuration avoids an API that rejects every
 * token because of how the operator copied the value.
 *
 * @param configured - Scope as set in `ENTRA_API_SCOPE`, either a bare name or a full URI.
 * @returns The segment after the last `/`, or the trimmed input when it has none. A value that
 *   ends in `/` yields an empty string, which the environment schema refuses.
 */
export function requiredScopeName(configured: string): string {
  const trimmed = configured.trim();
  return trimmed.slice(trimmed.lastIndexOf(SCOPE_URI_SEPARATOR) + 1);
}
