import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpHeaders, HttpStatusCode } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap, map, catchError } from 'rxjs/operators';
import { environment } from '../../environments/environment';

export interface AuthRequest {
  token: string;
}

/** Why a sign-in attempt failed, as far as the person signing in needs to know. */
export type SignInFailure = 'invalid-token' | 'unreachable' | 'too-many-attempts' | 'unexpected';

/**
 * The copy shown for each sign-in failure. It says what went wrong and how to fix it, with no
 * apology and no transport detail ("Failed to fetch", status codes, API messages). Each message has
 * two sentences, so each ends with a period. Keep failure copy here and nowhere else.
 */
export const SIGN_IN_FAILURE_MESSAGES: Readonly<Record<SignInFailure, string>> = {
  'invalid-token': "That token isn't valid. Check it and try again.",
  unreachable: "Can't reach the server. Check your connection and try again.",
  // Both API templates throttle at 100 requests per 60 seconds per client.
  'too-many-attempts': 'Too many attempts. Wait a minute and try again.',
  unexpected: "Couldn't sign you in. Try again.",
};

export interface AuthResponse {
  authenticated: boolean;
  /**
   * On failure, the user-facing copy from SIGN_IN_FAILURE_MESSAGES. On success, the API's own
   * confirmation, which isn't meant for display.
   */
  message: string;
  /** Set by AuthService.login() when authenticated is false. */
  failure?: SignInFailure;
}

/** Classifies a failed sign-in request. Anything that isn't an HTTP error counts as unexpected. */
export function signInFailureFromError(error: unknown): SignInFailure {
  if (!(error instanceof HttpErrorResponse)) {
    return 'unexpected';
  }
  switch (error.status) {
    // No HTTP response at all: offline, DNS or CORS failure, or the API isn't running.
    case 0:
      return 'unreachable';
    case HttpStatusCode.Unauthorized:
    case HttpStatusCode.Forbidden:
      return 'invalid-token';
    case HttpStatusCode.TooManyRequests:
      return 'too-many-attempts';
    default:
      return 'unexpected';
  }
}

function failedSignIn(failure: SignInFailure): AuthResponse {
  return { authenticated: false, message: SIGN_IN_FAILURE_MESSAGES[failure], failure };
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly AUTH_ENDPOINT = `${environment.apiUrl}auth/validate`;
  private readonly TOKEN_KEY = 'app_auth_token';

  isAuthenticated = signal(this.hasToken());

  /**
   * Validates the token with the API and stores it when accepted. Never errors: every failure
   * emits `authenticated: false` with a failure kind and its user-facing message.
   */
  login(token: string): Observable<AuthResponse> {
    const authRequest: AuthRequest = { token };
    const headers = new HttpHeaders({ 'Content-Type': 'application/json' });

    return this.http.post<AuthResponse>(this.AUTH_ENDPOINT, authRequest, { headers }).pipe(
      tap((response) => {
        if (response.authenticated) {
          this.storeToken(token);
          this.isAuthenticated.set(true);
        }
      }),
      // The validate endpoint answers a wrong token with 200 and its own message. That message
      // isn't user-facing copy, so a rejection reads the same whichever way the API reports it.
      map((response) => (response.authenticated ? response : failedSignIn('invalid-token'))),
      catchError((error: unknown) => {
        this.isAuthenticated.set(false);
        this.clearStorage();
        return of(failedSignIn(signInFailureFromError(error)));
      }),
    );
  }

  logout(): void {
    this.isAuthenticated.set(false);
    this.clearStorage();
  }

  /**
   * The stored token, or null. The localStorage getter throws a SecurityError when the browser
   * blocks site data, so every storage access is guarded: a blocked store reads as signed out.
   */
  getToken(): string | null {
    if (typeof window === 'undefined') {
      return null;
    }
    try {
      return localStorage.getItem(this.TOKEN_KEY);
    } catch {
      return null;
    }
  }

  private hasToken(): boolean {
    return this.getToken() !== null;
  }

  private storeToken(token: string): void {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      localStorage.setItem(this.TOKEN_KEY, token);
    } catch {
      // Storage is blocked or full: the sign-in lasts until the page reloads.
    }
  }

  private clearStorage(): void {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      localStorage.removeItem(this.TOKEN_KEY);
    } catch {
      // Storage is blocked, so there is no stored token to remove.
    }
  }
}
