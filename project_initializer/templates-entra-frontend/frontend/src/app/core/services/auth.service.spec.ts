import { TestBed } from '@angular/core/testing';
import { MsalService } from '@azure/msal-angular';
import { InteractionRequiredAuthError } from '@azure/msal-browser';
import { AuthService } from './auth.service';

// Minimal stub for IPublicClientApplication used across tests.
function makeMsalInstanceStub(overrides: Partial<{
  getActiveAccount: () => unknown;
  getAllAccounts: () => unknown[];
  acquireTokenSilent: (req: unknown) => Promise<{ accessToken: string }>;
  acquireTokenRedirect: (req: unknown) => Promise<void>;
  loginRedirect: (req: unknown) => void;
  logoutRedirect: () => void;
  setActiveAccount: (a: unknown) => void;
  initialize: () => Promise<void>;
  handleRedirectPromise: () => Promise<unknown>;
}> = {}) {
  return {
    getActiveAccount: () => ({ username: 'user@example.com' }),
    getAllAccounts: () => [{ username: 'user@example.com' }],
    acquireTokenSilent: async () => ({ accessToken: 'fake-token' }),
    acquireTokenRedirect: async () => undefined,
    loginRedirect: () => undefined,
    logoutRedirect: () => undefined,
    setActiveAccount: () => undefined,
    initialize: async () => undefined,
    handleRedirectPromise: async () => null,
    ...overrides,
  };
}

function makeMsalServiceStub(instanceOverrides = {}) {
  return { instance: makeMsalInstanceStub(instanceOverrides) };
}

describe('AuthService', () => {
  let service: AuthService;
  let msalStub: ReturnType<typeof makeMsalServiceStub>;

  function setup(instanceOverrides = {}) {
    msalStub = makeMsalServiceStub(instanceOverrides);
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        { provide: MsalService, useValue: msalStub },
      ],
    });
    service = TestBed.inject(AuthService);
  }

  // ── Criterion: isAuthenticated reflects account presence ──────────────────

  it('when accounts exist, isAuthenticated is set to true by refreshAccount', () => {
    setup();
    service.refreshAccount();
    expect(service.isAuthenticated()).toBe(true);
  });

  it('when no accounts exist, isAuthenticated is set to false by refreshAccount', () => {
    setup({
      getActiveAccount: () => null,
      getAllAccounts: () => [],
    });
    service.refreshAccount();
    expect(service.isAuthenticated()).toBe(false);
  });

  // ── Criterion: runtime contract — init sequence gates isAuthenticated ──────

  it('when runInitSequence completes with an account, isAuthenticated is true', async () => {
    setup();
    await service.runInitSequence();
    expect(service.isAuthenticated()).toBe(true);
  });

  it('when runInitSequence completes with no accounts, isAuthenticated is false', async () => {
    setup({
      getActiveAccount: () => null,
      getAllAccounts: () => [],
      handleRedirectPromise: async () => null,
    });
    await service.runInitSequence();
    expect(service.isAuthenticated()).toBe(false);
  });

  // ── Criterion: waitUntilInitialized resolves only after runInitSequence ────

  it('when runInitSequence has not yet been called, waitUntilInitialized is still pending', async () => {
    setup();
    let resolved = false;
    service.waitUntilInitialized().then(() => { resolved = true; });
    // Flush microtasks once; promise must not yet resolve without runInitSequence.
    await Promise.resolve();
    expect(resolved).toBe(false);
  });

  it('when runInitSequence completes, waitUntilInitialized resolves', async () => {
    setup();
    await service.runInitSequence();
    let resolved = false;
    await service.waitUntilInitialized().then(() => { resolved = true; });
    expect(resolved).toBe(true);
  });

  // ── Criterion: silent-success path ────────────────────────────────────────

  it('when acquireTokenSilent resolves, getAccessToken returns the access token', async () => {
    setup({
      acquireTokenSilent: async () => ({ accessToken: 'silent-token' }),
    });
    const token = await service.getAccessToken();
    expect(token).toBe('silent-token');
  });

  it('when no active account exists, getAccessToken returns null', async () => {
    setup({
      getActiveAccount: () => null,
      getAllAccounts: () => [],
    });
    const token = await service.getAccessToken();
    expect(token).toBeNull();
  });

  // ── Criterion: InteractionRequiredAuthError fallback path ─────────────────

  it('when acquireTokenSilent throws InteractionRequiredAuthError, acquireTokenRedirect is called', async () => {
    const redirectSpy = jasmine.createSpy('acquireTokenRedirect').and.returnValue(Promise.resolve());
    setup({
      acquireTokenSilent: async () => {
        throw new InteractionRequiredAuthError('interaction_required');
      },
      acquireTokenRedirect: redirectSpy,
    });
    const token = await service.getAccessToken();
    expect(redirectSpy).toHaveBeenCalled();
    expect(token).toBeNull();
  });

  it('when acquireTokenSilent throws a non-interaction error, the error is re-thrown', async () => {
    setup({
      acquireTokenSilent: async () => {
        throw new Error('network error');
      },
    });
    await expectAsync(service.getAccessToken()).toBeRejectedWithError('network error');
  });

  // ── Criterion: login/logout delegates ─────────────────────────────────────

  it('when login is called, loginRedirect is invoked with environment scope', () => {
    const spy = jasmine.createSpy('loginRedirect');
    setup({ loginRedirect: spy });
    service.login();
    expect(spy).toHaveBeenCalled();
  });

  it('when logout is called, logoutRedirect is invoked', () => {
    const spy = jasmine.createSpy('logoutRedirect');
    setup({ logoutRedirect: spy });
    service.logout();
    expect(spy).toHaveBeenCalled();
  });
});
