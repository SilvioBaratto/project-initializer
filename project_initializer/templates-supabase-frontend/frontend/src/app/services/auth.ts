import { Injectable, signal } from '@angular/core';
import {
  createClient,
  isAuthError,
  isAuthRetryableFetchError,
  isAuthWeakPasswordError,
  SupabaseClient,
  User,
} from '@supabase/supabase-js';
import { environment } from '../../environments/environment';

/** The auth request a failure came from; it picks the fallback copy for unclassified errors. */
export type AuthAction = 'sign-in' | 'sign-up' | 'reset-request' | 'password-update';

/** Why an auth request failed, as far as the person using the form needs to know. */
export type AuthFailure =
  | 'invalid-credentials'
  | 'email-not-confirmed'
  | 'account-exists'
  | 'weak-password'
  | 'same-password'
  | 'too-many-attempts'
  | 'unreachable'
  | 'unexpected';

/**
 * The copy shown for each classified failure. It says what went wrong and how to fix it, with no
 * apology and no transport or API detail (Supabase's own `error.message` never reaches the UI).
 * Two-sentence messages end with a period; a single sentence doesn't. Keep failure copy here.
 */
export const AUTH_FAILURE_MESSAGES: Readonly<Record<Exclude<AuthFailure, 'unexpected'>, string>> = {
  'invalid-credentials': "That email or password isn't right. Check them and try again.",
  'email-not-confirmed': 'Confirm your email to sign in. Open the link in your confirmation email.',
  'account-exists': 'An account with that email already exists. Sign in instead.',
  'weak-password': 'That password is too easy to guess. Choose a longer one with more kinds of characters.',
  'same-password': "Choose a password that's different from your current one",
  'too-many-attempts': 'Too many attempts. Wait a few minutes and try again.',
  unreachable: "Can't reach the server. Check your connection and try again.",
};

/** The copy for a failure that isn't classified, per request. */
export const UNEXPECTED_FAILURE_MESSAGES: Readonly<Record<AuthAction, string>> = {
  'sign-in': "Couldn't sign you in. Try again.",
  'sign-up': "Couldn't create your account. Try again.",
  'reset-request': "Couldn't send the reset link. Try again.",
  'password-update': "Couldn't update your password. Try again.",
};

/** The confirmation copy shown after a successful request. */
export const AUTH_SUCCESS_MESSAGES = {
  signUp: 'Check your email to confirm your account',
  resetRequest: 'Check your email for a password reset link',
  passwordUpdate: 'Password updated',
} as const;

/** Classifies a Supabase auth error by its error code, class or HTTP status. */
export function authFailureFromError(error: unknown): AuthFailure {
  // No response, or a gateway/5xx error Supabase marks as retryable.
  if (isAuthRetryableFetchError(error)) {
    return 'unreachable';
  }
  if (isAuthWeakPasswordError(error)) {
    return 'weak-password';
  }
  if (!isAuthError(error)) {
    return 'unexpected';
  }
  switch (error.code) {
    case 'invalid_credentials':
      return 'invalid-credentials';
    case 'email_not_confirmed':
      return 'email-not-confirmed';
    case 'user_already_exists':
    case 'email_exists':
      return 'account-exists';
    case 'weak_password':
      return 'weak-password';
    case 'same_password':
      return 'same-password';
    case 'over_request_rate_limit':
    case 'over_email_send_rate_limit':
      return 'too-many-attempts';
    default:
      return error.status === 429 ? 'too-many-attempts' : 'unexpected';
  }
}

/** The user-facing copy for a failed auth request. */
export function authFailureMessage(error: unknown, action: AuthAction): string {
  const failure = authFailureFromError(error);
  return failure === 'unexpected' ? UNEXPECTED_FAILURE_MESSAGES[action] : AUTH_FAILURE_MESSAGES[failure];
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly supabase: SupabaseClient;
  private initPromise: Promise<void>;
  private cachedAccessToken: string | null = null;

  isAuthenticated = signal(false);
  isInitialized = signal(false);
  currentUser = signal<User | null>(null);
  isPasswordRecovery = signal(false);

  constructor() {
    this.supabase = createClient(environment.supabaseUrl, environment.supabasePublishableKey);

    this.initPromise = this.supabase.auth.getSession()
      .then(({ data: { session } }) => {
        this.isAuthenticated.set(!!session);
        this.currentUser.set(session?.user ?? null);
        this.cachedAccessToken = session?.access_token ?? null;
      })
      .catch(() => {
        this.isAuthenticated.set(false);
        this.currentUser.set(null);
        this.cachedAccessToken = null;
      })
      .finally(() => {
        this.isInitialized.set(true);
      });

    this.supabase.auth.onAuthStateChange((event, session) => {
      this.isAuthenticated.set(!!session);
      this.currentUser.set(session?.user ?? null);
      this.cachedAccessToken = session?.access_token ?? null;

      if (event === 'PASSWORD_RECOVERY') {
        this.isPasswordRecovery.set(true);
      }
    });
  }

  waitUntilInitialized(): Promise<void> {
    return this.initPromise;
  }

  async login(email: string, password: string): Promise<{ success: boolean; message: string }> {
    const { error } = await this.supabase.auth.signInWithPassword({ email, password });

    if (error) {
      return { success: false, message: authFailureMessage(error, 'sign-in') };
    }

    return { success: true, message: 'Authenticated' };
  }

  async signup(email: string, password: string): Promise<{ success: boolean; message: string }> {
    const { error } = await this.supabase.auth.signUp({ email, password });

    if (error) {
      return { success: false, message: authFailureMessage(error, 'sign-up') };
    }

    return { success: true, message: AUTH_SUCCESS_MESSAGES.signUp };
  }

  async forgotPassword(email: string): Promise<{ success: boolean; message: string }> {
    const { error } = await this.supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin + '/auth/update-password',
    });

    if (error) {
      return { success: false, message: authFailureMessage(error, 'reset-request') };
    }

    return { success: true, message: AUTH_SUCCESS_MESSAGES.resetRequest };
  }

  async updatePassword(newPassword: string): Promise<{ success: boolean; message: string }> {
    const { error } = await this.supabase.auth.updateUser({ password: newPassword });

    if (error) {
      return { success: false, message: authFailureMessage(error, 'password-update') };
    }

    this.isPasswordRecovery.set(false);
    return { success: true, message: AUTH_SUCCESS_MESSAGES.passwordUpdate };
  }

  async loginWithGoogle(): Promise<void> {
    await this.supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin,
      },
    });
  }

  getAccessToken(): string | null {
    return this.cachedAccessToken;
  }

  async refreshSession(): Promise<boolean> {
    const { data: { session }, error } = await this.supabase.auth.refreshSession();
    if (error || !session) {
      return false;
    }
    return true;
  }

  async logout(): Promise<void> {
    try {
      await this.supabase.auth.signOut();
    } finally {
      this.isAuthenticated.set(false);
      this.currentUser.set(null);
      this.isPasswordRecovery.set(false);
      this.cachedAccessToken = null;
    }
  }
}
