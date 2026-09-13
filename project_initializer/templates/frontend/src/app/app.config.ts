import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withViewTransitions } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { LucideIconConfig } from 'lucide-angular';

import { routes } from './app.routes';
import { ICON_PROVIDER } from './icons';
import { errorInterceptor } from './interceptors/error.interceptor';
import { ThemeService } from './services/theme';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding(), withViewTransitions()),
    provideHttpClient(withFetch(), withInterceptors([errorInterceptor])),
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
    // Apply the stored light/dark choice before the first view renders, so every
    // routed view honours it, not only those inside the shell.
    provideAppInitializer(() => {
      inject(ThemeService);
    }),
  ],
};
