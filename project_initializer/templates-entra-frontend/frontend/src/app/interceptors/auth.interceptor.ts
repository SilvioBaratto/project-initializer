import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, switchMap, catchError, throwError } from 'rxjs';
import { AuthService } from '../core/services/auth.service';
import { environment } from '../../environments/environment';

// Token is audience-bound to the API; attach only to API requests to avoid
// leaking the scoped token to login.microsoftonline.com or static assets.
function isApiRequest(url: string): boolean {
  return url.startsWith(environment.apiUrl);
}

function cloneWithBearer(req: Parameters<HttpInterceptorFn>[0], token: string) {
  return req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);

  if (!isApiRequest(req.url)) {
    return next(req);
  }

  // getAccessToken() is async (MSAL acquireTokenSilent returns a Promise).
  return from(authService.getAccessToken()).pipe(
    switchMap((token) => {
      const authedReq = token ? cloneWithBearer(req, token) : req;
      return next(authedReq).pipe(
        catchError((error) => handle401(error, req, next, authService)),
      );
    }),
  );
};

// On 401: attempt one silent-token refresh and retry the request.
// If MSAL requires interaction (InteractionRequiredAuthError), trigger loginRedirect
// and let the in-flight request fail — the browser navigates away so no retry is possible.
function handle401(
  error: { status?: number },
  req: Parameters<HttpInterceptorFn>[0],
  next: Parameters<HttpInterceptorFn>[1],
  authService: AuthService,
) {
  if (error.status !== 401) {
    return throwError(() => error);
  }

  return from(authService.getAccessToken()).pipe(
    switchMap((token) => {
      if (!token) {
        authService.login();
        return throwError(() => error);
      }
      return next(cloneWithBearer(req, token));
    }),
    catchError(() => {
      // InteractionRequiredAuthError or other failure: login() already triggers redirect.
      authService.login();
      return throwError(() => error);
    }),
  );
}
