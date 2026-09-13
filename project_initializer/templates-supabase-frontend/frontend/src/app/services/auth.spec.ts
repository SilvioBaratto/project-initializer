/**
 * Tests for the Supabase AuthService's user-facing copy. Supabase's own `error.message` (API and
 * transport strings such as "Invalid login credentials" or "Failed to fetch") must never reach the
 * UI: every failure maps to fixed copy that says what went wrong and how to fix it, and success
 * copy follows the same punctuation rule (no period on a single sentence).
 */
import {
  AuthApiError,
  AuthRetryableFetchError,
  AuthSessionMissingError,
  AuthWeakPasswordError,
} from '@supabase/supabase-js';
import {
  AUTH_FAILURE_MESSAGES,
  AUTH_SUCCESS_MESSAGES,
  AuthAction,
  UNEXPECTED_FAILURE_MESSAGES,
  authFailureFromError,
  authFailureMessage,
} from './auth';

const ACTIONS: AuthAction[] = ['sign-in', 'sign-up', 'reset-request', 'password-update'];

/** Counts sentences by their terminal punctuation, ignoring a missing final period. */
function sentenceCount(copy: string): number {
  return copy.split(/[.!?](?:\s|$)/).filter((part) => part.trim().length > 0).length;
}

describe('authFailureFromError', () => {
  it.each([
    ['invalid_credentials', 400, 'invalid-credentials'],
    ['email_not_confirmed', 400, 'email-not-confirmed'],
    ['user_already_exists', 422, 'account-exists'],
    ['email_exists', 422, 'account-exists'],
    ['weak_password', 422, 'weak-password'],
    ['same_password', 422, 'same-password'],
    ['over_request_rate_limit', 429, 'too-many-attempts'],
    ['over_email_send_rate_limit', 429, 'too-many-attempts'],
  ] as const)('when the API answers %s with status %s, the failure is %s', (code, status, failure) => {
    expect(authFailureFromError(new AuthApiError('raw API text', status, code))).toBe(failure);
  });

  it('when the API answers 429 without a code, the failure is too-many-attempts', () => {
    expect(authFailureFromError(new AuthApiError('raw API text', 429, undefined))).toBe('too-many-attempts');
  });

  it('when the request gets no response, the failure is unreachable', () => {
    expect(authFailureFromError(new AuthRetryableFetchError('Failed to fetch', 0))).toBe('unreachable');
  });

  it('when a gateway error is marked retryable, the failure is unreachable', () => {
    expect(authFailureFromError(new AuthRetryableFetchError('HTTP 503', 503))).toBe('unreachable');
  });

  it('when the password is rejected as weak, the failure is weak-password', () => {
    expect(authFailureFromError(new AuthWeakPasswordError('Password is weak', 422, ['length']))).toBe(
      'weak-password',
    );
  });

  it('when the error is unclassified, the failure is unexpected', () => {
    expect(authFailureFromError(new AuthApiError('raw API text', 500, 'unexpected_failure'))).toBe('unexpected');
    expect(authFailureFromError(new AuthSessionMissingError())).toBe('unexpected');
    expect(authFailureFromError(new Error('boom'))).toBe('unexpected');
    expect(authFailureFromError('not an error')).toBe('unexpected');
  });
});

describe('authFailureMessage', () => {
  it.each(ACTIONS)('when %s fails with raw API text, that text is never shown', (action) => {
    const raw = 'Invalid login credentials';
    const errors = [
      new AuthApiError(raw, 400, 'invalid_credentials'),
      new AuthApiError(raw, 500, undefined),
      new AuthRetryableFetchError(raw, 0),
    ];
    for (const error of errors) {
      expect(authFailureMessage(error, action)).not.toContain(raw);
    }
  });

  it('when a classified failure occurs, its fixed copy is returned for any request', () => {
    const error = new AuthApiError('raw API text', 400, 'invalid_credentials');
    for (const action of ACTIONS) {
      expect(authFailureMessage(error, action)).toBe(AUTH_FAILURE_MESSAGES['invalid-credentials']);
    }
  });

  it.each(ACTIONS)('when %s fails unexpectedly, the fallback copy names that request', (action) => {
    expect(authFailureMessage(new Error('boom'), action)).toBe(UNEXPECTED_FAILURE_MESSAGES[action]);
  });

  it('when the unexpected copy is read, it matches the pages that fall back to their own copy', () => {
    // forgot-password.ts and update-password.ts show these when a result carries no message.
    expect(UNEXPECTED_FAILURE_MESSAGES['reset-request']).toBe("Couldn't send the reset link. Try again.");
    expect(UNEXPECTED_FAILURE_MESSAGES['password-update']).toBe("Couldn't update your password. Try again.");
  });
});

describe('auth copy punctuation', () => {
  const allCopy = [
    ...Object.values(AUTH_FAILURE_MESSAGES),
    ...Object.values(UNEXPECTED_FAILURE_MESSAGES),
    ...Object.values(AUTH_SUCCESS_MESSAGES),
  ];

  it.each(allCopy)('%s ends with a period only when it has several sentences', (copy) => {
    if (sentenceCount(copy) > 1) {
      expect(copy.endsWith('.')).toBe(true);
    } else {
      expect(copy.endsWith('.')).toBe(false);
    }
  });

  it.each(allCopy)('%s has no apology or "please"', (copy) => {
    expect(copy.toLowerCase()).not.toMatch(/\b(sorry|please|oops)\b/);
  });
});
