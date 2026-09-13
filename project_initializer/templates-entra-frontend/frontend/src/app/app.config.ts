import {
  ApplicationConfig,
  provideBrowserGlobalErrorListeners,
  provideAppInitializer,
  inject,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withViewTransitions } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import {
  IPublicClientApplication,
  PublicClientApplication,
  BrowserCacheLocation,
  InteractionType,
  RedirectRequest,
} from '@azure/msal-browser';
import {
  MSAL_INSTANCE,
  MSAL_GUARD_CONFIG,
  MsalGuardConfiguration,
  MsalService,
} from '@azure/msal-angular';
import { LucideIconConfig } from 'lucide-angular';

import { routes } from './app.routes';
import { ICON_PROVIDER } from './icons';
import { errorInterceptor } from './interceptors/error.interceptor';
import { authInterceptor } from './interceptors/auth.interceptor';
import { environment } from '../environments/environment';
import { AuthService } from './core/services/auth.service';
import { ThemeService } from './services/theme';

function MSALInstanceFactory(): IPublicClientApplication {
  return new PublicClientApplication({
    auth: {
      clientId: environment.entraSpaClientId,
      authority: environment.authority,
      redirectUri: '/',
    },
    cache: {
      cacheLocation: BrowserCacheLocation.LocalStorage,
    },
  });
}

function MSALGuardConfigFactory(): MsalGuardConfiguration {
  return {
    interactionType: InteractionType.Redirect,
    authRequest: {
      scopes: [environment.scope],
    } as RedirectRequest,
  };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding(), withViewTransitions()),
    provideHttpClient(withFetch(), withInterceptors([errorInterceptor, authInterceptor])),
    ICON_PROVIDER,
    {
      // M3 icons are 24px. Material icon buttons already size inner svgs to 24px;
      // text/filled buttons take [size]="18" on the icon (see icons.ts).
      provide: LucideIconConfig,
      useFactory: () => {
        const cfg = new LucideIconConfig();
        cfg.size = 24;
        cfg.strokeWidth = 2;
        return cfg;
      },
    },
    // Apply the stored light/dark choice before the first view renders, so views
    // outside the shell (sign-in) honour it too.
    provideAppInitializer(() => {
      inject(ThemeService);
    }),
    { provide: MSAL_INSTANCE, useFactory: MSALInstanceFactory },
    { provide: MSAL_GUARD_CONFIG, useFactory: MSALGuardConfigFactory },
    MsalService,
    // Runs initialize() → handleRedirectPromise() → refreshAccount() before any
    // route guard resolves, so isAuthenticated() is accurate at guard time.
    provideAppInitializer(() => inject(AuthService).runInitSequence()),
  ],
};
