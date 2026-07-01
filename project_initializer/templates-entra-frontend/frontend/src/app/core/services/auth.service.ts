import { Injectable, signal, inject } from '@angular/core';
import { MsalService } from '@azure/msal-angular';
import {
  AccountInfo,
  InteractionRequiredAuthError,
  AuthenticationResult,
} from '@azure/msal-browser';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly msalService = inject(MsalService);
  // Init promise is owned here; provideAppInitializer calls runInitSequence() to resolve it.
  private resolveInit!: () => void;
  private readonly initPromise = new Promise<void>(r => { this.resolveInit = r; });

  readonly isAuthenticated = signal(false);
  readonly isInitialized = signal(false);

  waitUntilInitialized(): Promise<void> {
    return this.initPromise;
  }

  async runInitSequence(): Promise<void> {
    await this.msalService.instance.initialize();
    await this.msalService.instance.handleRedirectPromise();
    this.refreshAccount();
    this.resolveInit();
  }

  async getAccessToken(): Promise<string | null> {
    const account = this.resolveActiveAccount();
    if (!account) return null;
    return this.acquireSilentOrInteractive(account);
  }

  login(): void {
    this.msalService.instance.loginRedirect({ scopes: [environment.scope] });
  }

  logout(): void {
    this.msalService.instance.logoutRedirect();
  }

  refreshAccount(): void {
    const accounts = this.msalService.instance.getAllAccounts();
    const account = accounts[0] ?? null;
    if (account) {
      this.msalService.instance.setActiveAccount(account);
    }
    this.isAuthenticated.set(!!account);
    this.isInitialized.set(true);
  }

  private resolveActiveAccount(): AccountInfo | null {
    const active = this.msalService.instance.getActiveAccount();
    if (active) return active;
    const all = this.msalService.instance.getAllAccounts();
    return all[0] ?? null;
  }

  private async acquireSilentOrInteractive(account: AccountInfo): Promise<string | null> {
    try {
      const result: AuthenticationResult = await this.msalService.instance.acquireTokenSilent({
        account,
        scopes: [environment.scope],
      });
      return result.accessToken;
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        await this.msalService.instance.acquireTokenRedirect({
          account,
          scopes: [environment.scope],
        });
        return null;
      }
      throw err;
    }
  }
}
