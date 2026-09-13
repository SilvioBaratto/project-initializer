import { provideZonelessChangeDetection } from '@angular/core';
import {
  MSAL_GUARD_CONFIG,
  MSAL_INSTANCE,
  MsalGuardConfiguration,
  MsalService,
} from '@azure/msal-angular';
import {
  IPublicClientApplication,
  InteractionType,
  stubbedPublicClientApplication,
} from '@azure/msal-browser';

/**
 * Test environment providers for the Entra variant, applied to every spec through
 * `providersFile` in angular.json. This overlay file replaces the base one and keeps
 * zoneless change detection.
 *
 * The Entra app-sidebar injects AuthService, and AuthService injects MsalService, so a
 * spec that renders the real shell without caring about auth (layout, responsive shell)
 * would fail with NG0201. These providers mirror the MSAL providers in app.config.ts over
 * an inert client: signed out, no network and no redirects. No app initializer is
 * registered, so the MSAL init sequence never starts on its own.
 *
 * A spec that exercises auth declares its own providers (an AuthService or MsalService
 * stub, or its own MSAL_INSTANCE). TestBed providers override these environment providers.
 */
function createInertMsalInstance(): IPublicClientApplication {
  return {
    // msal-browser's own stub: no accounts, and token, popup and cache calls reject.
    ...stubbedPublicClientApplication,
    // The init sequence and the redirect entry points resolve without navigating, so
    // runInitSequence() ends signed out and Sign in or Sign out in a shell spec leaves
    // no unhandled rejection behind.
    initialize: () => Promise.resolve(),
    handleRedirectPromise: () => Promise.resolve(null),
    loginRedirect: () => Promise.resolve(),
    logoutRedirect: () => Promise.resolve(),
  };
}

const inertGuardConfig: MsalGuardConfiguration = {
  interactionType: InteractionType.Redirect,
  authRequest: { scopes: [] },
};

export default [
  provideZonelessChangeDetection(),
  { provide: MSAL_INSTANCE, useFactory: createInertMsalInstance },
  { provide: MSAL_GUARD_CONFIG, useValue: inertGuardConfig },
  MsalService,
];
