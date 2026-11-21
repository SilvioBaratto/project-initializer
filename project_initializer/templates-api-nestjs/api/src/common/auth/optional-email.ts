import { z } from 'zod';

/**
 * The single definition of an address that may leave the API as the caller's email.
 *
 * It uses the browser (HTML5) address grammar rather than Zod's stricter default, so addresses
 * that identity providers accept (`first!last@example.com`, `dev@localhost`) are kept. Both the
 * verifiers (through {@link toOptionalEmail}) and the `GET /auth/me` response schema use it, so an
 * identity can never carry an email that the response then refuses to serialise.
 */
export const emailAddressSchema = z.email({ pattern: z.regexes.html5Email });

/**
 * Reduces an email-like claim to a usable address or nothing.
 *
 * @param raw - Email or username claim as the identity provider reported it; providers may send
 *   `undefined`, an empty string, a phone number or a display name instead of an address.
 * @returns The address when it is valid, otherwise `undefined`. A missing email is never an error:
 *   the identity stays valid without one.
 */
export function toOptionalEmail(raw?: string): string | undefined {
  const parsed = emailAddressSchema.safeParse(raw);
  return parsed.success ? parsed.data : undefined;
}
