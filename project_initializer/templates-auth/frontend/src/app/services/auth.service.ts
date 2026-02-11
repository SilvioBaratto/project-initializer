import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';
import { environment } from '../../environments/environment';

export interface AuthRequest {
  token: string;
}

export interface AuthResponse {
  authenticated: boolean;
  message: string;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly AUTH_ENDPOINT = `${environment.apiUrl}auth/validate`;
  private readonly TOKEN_KEY = 'app_auth_token';

  isAuthenticated = signal(this.hasToken());

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
      catchError((error) => {
        this.isAuthenticated.set(false);
        this.clearStorage();
        return of({
          authenticated: false,
          message: error?.error?.message || error?.message || 'Authentication failed',
        });
      }),
    );
  }

  logout(): void {
    this.isAuthenticated.set(false);
    this.clearStorage();
  }

  getToken(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(this.TOKEN_KEY);
    }
    return null;
  }

  private hasToken(): boolean {
    return this.getToken() !== null;
  }

  private storeToken(token: string): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem(this.TOKEN_KEY, token);
    }
  }

  private clearStorage(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(this.TOKEN_KEY);
    }
  }
}
