/**
 * Tests for LoginComponent (token auth sign-in view on Angular Material).
 * Criteria: one h1 inside a single main landmark; an outlined, labelled password field with
 * current-password autocomplete; an empty submit shows a specific error without calling the
 * service; a valid submit sends the trimmed token and navigates to returnUrl replacing history;
 * failures show an alert with copy that says what went wrong and how to fix it, never a raw
 * transport or API message; only a rejected token flags the field and describes it with the
 * alert, and editing the token clears both; while signing in the submit button is disabled but
 * keeps keyboard focus (aria-disabled, never the native attribute), is busy with a spinner, the
 * status is announced outside any busy subtree, duplicate submits are ignored and focus stays on
 * the button after a failure.
 * Through the real AuthService over HTTP: no response maps to the unreachable copy, 401/403 and
 * a 200 rejection to the invalid-token copy, 429 to the too-many-attempts copy, anything else to
 * the generic retry copy.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatCardHarness } from '@angular/material/card/testing';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';
import { MatInputHarness } from '@angular/material/input/testing';
import { MatProgressSpinnerHarness } from '@angular/material/progress-spinner/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { environment } from '../../../environments/environment';
import { AuthResponse, AuthService, SIGN_IN_FAILURE_MESSAGES } from '../../services/auth';
import { LoginComponent } from './login';

const REJECTED: AuthResponse = {
  authenticated: false,
  message: SIGN_IN_FAILURE_MESSAGES['invalid-token'],
  failure: 'invalid-token',
};

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let loader: HarnessLoader;
  let login: ReturnType<typeof vi.fn<(token: string) => Observable<AuthResponse>>>;
  let navigate: ReturnType<typeof vi.fn>;

  async function setup(queryParams: Record<string, string> = {}): Promise<void> {
    login = vi.fn<(token: string) => Observable<AuthResponse>>();
    navigate = vi.fn().mockResolvedValue(true);

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: { login } },
        { provide: Router, useValue: { navigate } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParams } } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  }

  const host = (): HTMLElement => fixture.nativeElement;
  const nativeInput = (): HTMLInputElement => host().querySelector('input#token')!;
  const alertText = (): string | undefined =>
    host().querySelector('[role="alert"]')?.textContent?.trim();
  const describedBy = (): string[] =>
    nativeInput().getAttribute('aria-describedby')?.split(' ') ?? [];
  const submitButton = () => loader.getHarness(MatButtonHarness.with({ text: 'Sign in' }));
  const tokenField = () => loader.getHarness(MatFormFieldHarness);
  const tokenInput = () => loader.getHarness(MatInputHarness.with({ selector: '#token' }));

  describe('structure', () => {
    beforeEach(() => setup());

    it('renders one h1 naming the view inside a single main landmark', async () => {
      const headings = host().querySelectorAll('h1');
      expect(headings.length).toBe(1);
      expect(headings[0].textContent?.trim()).toBe('Sign in');
      expect(host().querySelectorAll('main').length).toBe(1);
      expect(host().querySelector('main h1')).toBe(headings[0]);

      const card = await loader.getHarness(MatCardHarness);
      expect(await card.getTitleText()).toBe('Sign in');
      expect(await card.getSubtitleText()).toBe('Enter your token to continue');
    });

    it('renders the token as an outlined, labelled password field', async () => {
      const field = await tokenField();
      expect(await field.getAppearance()).toBe('outline');
      expect(await field.getLabel()).toBe('Token');

      const input = await tokenInput();
      expect(await input.getType()).toBe('password');
      expect(nativeInput().getAttribute('autocomplete')).toBe('current-password');
    });

    it('uses one filled submit button as the primary action', async () => {
      const buttons = await loader.getAllHarnesses(MatButtonHarness);
      expect(buttons.length).toBe(1);
      expect(await buttons[0].getAppearance()).toBe('filled');
      expect(await buttons[0].getType()).toBe('submit');
      expect(await buttons[0].isDisabled()).toBe(false);
    });

    it('shows no alert before a submit', () => {
      expect(host().querySelector('[role="alert"]')).toBeNull();
    });
  });

  describe('validation', () => {
    beforeEach(() => setup());

    it('shows a specific error, focuses the field and skips the service on an empty submit', async () => {
      await (await submitButton()).click();

      const field = await tokenField();
      expect(await field.getTextErrors()).toEqual(['Enter your token']);
      // Material reports an empty required field through aria-required, not aria-invalid,
      // and links the visible error through aria-describedby.
      expect(nativeInput().getAttribute('aria-required')).toBe('true');
      const errorId = host().querySelector('mat-error')!.id;
      expect(describedBy()).toContain(errorId);
      expect(document.activeElement).toBe(nativeInput());
      expect(login).not.toHaveBeenCalled();
    });

    it('clears the required error once a token is entered', async () => {
      await (await submitButton()).click();
      await (await tokenInput()).setValue('abc');

      expect(await (await tokenField()).getTextErrors()).toEqual([]);
    });
  });

  describe('submitting', () => {
    it('sends the trimmed token and navigates to returnUrl replacing history', async () => {
      await setup({ returnUrl: '/reports' });
      login.mockReturnValue(of({ authenticated: true, message: '' }));

      await (await tokenInput()).setValue('  secret-token  ');
      await (await submitButton()).click();

      expect(login).toHaveBeenCalledExactlyOnceWith('secret-token');
      expect(navigate).toHaveBeenCalledWith(['/reports'], { replaceUrl: true });
      expect(host().querySelector('[role="alert"]')).toBeNull();
    });

    it('navigates to the root when there is no returnUrl', async () => {
      await setup();
      login.mockReturnValue(of({ authenticated: true, message: '' }));

      await (await tokenInput()).setValue('secret-token');
      await (await submitButton()).click();

      expect(navigate).toHaveBeenCalledWith(['/'], { replaceUrl: true });
    });

    it('submits when the form itself is submitted (Enter in the field)', async () => {
      await setup();
      login.mockReturnValue(of({ authenticated: true, message: '' }));

      await (await tokenInput()).setValue('secret-token');
      host().querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
      await fixture.whenStable();

      expect(login).toHaveBeenCalledExactlyOnceWith('secret-token');
    });
  });

  describe('errors', () => {
    beforeEach(() => setup());

    async function submitToken(): Promise<void> {
      await (await tokenInput()).setValue('secret-token');
      await (await submitButton()).click();
      await fixture.whenStable();
    }

    it('says how to fix a rejected token in an alert and flags the field', async () => {
      login.mockReturnValue(of(REJECTED));

      await submitToken();

      expect(alertText()).toBe("That token isn't valid. Check it and try again.");
      expect(nativeInput().getAttribute('aria-invalid')).toBe('true');
      expect(navigate).not.toHaveBeenCalled();
    });

    it('describes the flagged field with the rejection so the reason is read on focus', async () => {
      login.mockReturnValue(of(REJECTED));

      await submitToken();

      const alert = host().querySelector('[role="alert"]')!;
      expect(alert.id).toBeTruthy();
      expect(describedBy()).toContain(alert.id);
    });

    it('clears the rejection once the token is edited', async () => {
      login.mockReturnValue(of(REJECTED));
      await submitToken();
      const alertId = host().querySelector('[role="alert"]')!.id;

      await (await tokenInput()).setValue('another-token');
      await fixture.whenStable();

      expect(host().querySelector('[role="alert"]')).toBeNull();
      expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
      expect(describedBy()).not.toContain(alertId);
      expect(await (await tokenField()).getTextErrors()).toEqual([]);
      expect(login).toHaveBeenCalledTimes(1);
    });

    it('shows the required error when the rejected token is cleared', async () => {
      login.mockReturnValue(of(REJECTED));
      await submitToken();

      await (await tokenInput()).setValue('');
      await fixture.whenStable();

      expect(host().querySelector('[role="alert"]')).toBeNull();
      expect(await (await tokenField()).getTextErrors()).toEqual(['Enter your token']);
    });

    it('treats a rejection without a failure kind as a rejected token, not its raw message', async () => {
      login.mockReturnValue(of({ authenticated: false, message: 'Invalid token' }));

      await submitToken();

      expect(alertText()).toBe(SIGN_IN_FAILURE_MESSAGES['invalid-token']);
      expect(nativeInput().getAttribute('aria-invalid')).toBe('true');
    });

    it('says to check the connection when the server is unreachable, without flagging the field', async () => {
      login.mockReturnValue(
        of({ authenticated: false, message: 'Failed to fetch', failure: 'unreachable' }),
      );

      await submitToken();

      expect(alertText()).toBe("Can't reach the server. Check your connection and try again.");
      expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
      expect(describedBy()).not.toContain('login-error');
    });

    it('says to wait when there were too many attempts, without flagging the field', async () => {
      login.mockReturnValue(
        of({ authenticated: false, message: '', failure: 'too-many-attempts' }),
      );

      await submitToken();

      expect(alertText()).toBe('Too many attempts. Wait a minute and try again.');
      expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
    });

    it('maps an HTTP failure that reaches the component instead of showing its message', async () => {
      login.mockReturnValue(
        throwError(
          () =>
            new HttpErrorResponse({ status: 0, statusText: 'Unknown Error', error: new TypeError('Failed to fetch') }),
        ),
      );

      await submitToken();

      expect(alertText()).toBe(SIGN_IN_FAILURE_MESSAGES.unreachable);
      expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
    });

    it('shows the generic retry copy for an error that is not an HTTP failure', async () => {
      login.mockReturnValue(throwError(() => new Error('Network unavailable')));

      await submitToken();

      expect(alertText()).toBe("Couldn't sign you in. Try again.");
      expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
    });

    it('shows the generic retry copy when the failure has no details', async () => {
      login.mockReturnValue(throwError(() => ({})));

      await submitToken();

      expect(alertText()).toBe(SIGN_IN_FAILURE_MESSAGES.unexpected);
    });

    it('clears the previous alert when a new attempt starts', async () => {
      login.mockReturnValueOnce(of(REJECTED));
      await submitToken();
      expect(host().querySelector('[role="alert"]')).not.toBeNull();

      const pending = new Subject<AuthResponse>();
      login.mockReturnValueOnce(pending);
      await (await submitButton()).click();
      await fixture.whenStable();

      expect(host().querySelector('[role="alert"]')).toBeNull();
      expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
    });
  });

  describe('while signing in', () => {
    let pending: Subject<AuthResponse>;
    const submitNative = (): HTMLButtonElement => host().querySelector('button[type="submit"]')!;

    beforeEach(async () => {
      await setup();
      pending = new Subject<AuthResponse>();
      login.mockReturnValue(pending);
      await (await tokenInput()).setValue('secret-token');
      submitNative().focus();
      await (await submitButton()).click();
      await fixture.whenStable();
    });

    it('marks the focused submit button disabled and busy without dropping focus, shows a spinner and announces the status', async () => {
      // Focusable disabled state: a native `disabled` attribute would drop keyboard focus to <body>.
      expect(await (await submitButton()).isDisabled()).toBe(true);
      expect(submitNative().hasAttribute('disabled')).toBe(false);
      expect(submitNative().getAttribute('aria-disabled')).toBe('true');
      expect(submitNative().getAttribute('aria-busy')).toBe('true');
      expect(document.activeElement).toBe(submitNative());

      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(1);
      // A <button> may not contain a descendant with a tabindex attribute.
      expect(submitNative().querySelectorAll('[tabindex]')).toHaveLength(0);

      // Busy state sits on the button, so the live regions are never inside an aria-busy subtree.
      expect(host().querySelector('form')!.hasAttribute('aria-busy')).toBe(false);
      const status = host().querySelector('[role="status"]')!;
      expect(status.textContent?.trim()).toBe('Signing in…');
      expect(status.closest('[aria-busy]')).toBeNull();
    });

    it('ignores a click on the busy button, Enter in the field or a direct call until the request settles', async () => {
      // The busy button has no native `disabled`, so a click and Enter in the field still submit.
      await (await submitButton()).click();
      host().querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
      fixture.componentInstance.onSubmit();
      await fixture.whenStable();

      expect(login).toHaveBeenCalledTimes(1);
    });

    it('restores the idle state after the request settles', async () => {
      pending.next(REJECTED);
      pending.complete();
      await fixture.whenStable();

      expect(await (await submitButton()).isDisabled()).toBe(false);
      expect(submitNative().hasAttribute('aria-disabled')).toBe(false);
      expect(submitNative().hasAttribute('aria-busy')).toBe(false);
      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(0);
      expect(host().querySelector('[role="status"]')!.textContent?.trim()).toBe('');
    });

    it('leaves focus on the submit button when the attempt fails', async () => {
      pending.next(REJECTED);
      await fixture.whenStable();

      expect(alertText()).toBe(SIGN_IN_FAILURE_MESSAGES['invalid-token']);
      expect(document.activeElement).toBe(submitNative());
    });

    it('returns focus to the field if focus was lost while signing in', async () => {
      (document.activeElement as HTMLElement | null)?.blur();
      expect(document.activeElement).toBe(document.body);

      pending.next(REJECTED);
      await fixture.whenStable();

      expect(document.activeElement).toBe(nativeInput());
    });
  });

  describe('failure copy from the real AuthService over HTTP', () => {
    const TOKEN_KEY = 'app_auth_token';
    const VALIDATE_URL = `${environment.apiUrl}auth/validate`;
    let httpTesting: HttpTestingController;

    beforeEach(async () => {
      localStorage.clear();
      navigate = vi.fn().mockResolvedValue(true);

      await TestBed.configureTestingModule({
        imports: [LoginComponent],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          { provide: Router, useValue: { navigate } },
          { provide: ActivatedRoute, useValue: { snapshot: { queryParams: {} } } },
        ],
      }).compileComponents();

      httpTesting = TestBed.inject(HttpTestingController);
      fixture = TestBed.createComponent(LoginComponent);
      loader = TestbedHarnessEnvironment.loader(fixture);
      await fixture.whenStable();
    });

    afterEach(() => {
      httpTesting.verify();
      localStorage.clear();
    });

    /** Submits a token and answers the validate request with `respond`. */
    async function attempt(respond: (request: ReturnType<HttpTestingController['expectOne']>) => void) {
      await (await tokenInput()).setValue('secret-token');
      await (await submitButton()).click();
      const request = httpTesting.expectOne({ method: 'POST', url: VALIDATE_URL });
      expect(request.request.body).toEqual({ token: 'secret-token' });
      respond(request);
      await fixture.whenStable();
    }

    it('says the server is unreachable when the request gets no response, not "Failed to fetch"', async () => {
      await attempt((request) => request.error(new ProgressEvent('error')));

      expect(alertText()).toBe("Can't reach the server. Check your connection and try again.");
      expect(alertText()).not.toMatch(/fetch|http|unknown error/i);
      expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
    });

    for (const status of [401, 403]) {
      it(`says the token isn't valid on ${status} and flags the field`, async () => {
        await attempt((request) =>
          request.flush({ message: 'Unauthorized', statusCode: status }, { status, statusText: 'Denied' }),
        );

        expect(alertText()).toBe("That token isn't valid. Check it and try again.");
        expect(nativeInput().getAttribute('aria-invalid')).toBe('true');
        expect(describedBy()).toContain('login-error');
      });
    }

    it("says the token isn't valid when the API answers 200 with authenticated false, not its own message", async () => {
      await attempt((request) => request.flush({ authenticated: false, message: 'Invalid token' }));

      expect(alertText()).toBe(SIGN_IN_FAILURE_MESSAGES['invalid-token']);
      expect(nativeInput().getAttribute('aria-invalid')).toBe('true');
      expect(navigate).not.toHaveBeenCalled();
    });

    it('says to wait when the API throttles the attempt (429)', async () => {
      await attempt((request) =>
        request.flush(
          { error: { code: 'RATE_LIMIT_EXCEEDED', message: 'Rate limit exceeded.' } },
          { status: 429, statusText: 'Too Many Requests' },
        ),
      );

      expect(alertText()).toBe('Too many attempts. Wait a minute and try again.');
      expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
    });

    for (const status of [500, 502]) {
      it(`shows the generic retry copy on ${status}, not the server's message`, async () => {
        await attempt((request) =>
          request.flush({ message: 'Internal server error' }, { status, statusText: 'Server Error' }),
        );

        expect(alertText()).toBe("Couldn't sign you in. Try again.");
        expect(nativeInput().getAttribute('aria-invalid')).toBe('false');
      });
    }

    it('clears a stored token after a failed attempt', async () => {
      localStorage.setItem(TOKEN_KEY, 'stale-token');

      await attempt((request) => request.error(new ProgressEvent('error')));

      expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
      expect(TestBed.inject(AuthService).isAuthenticated()).toBe(false);
    });

    it('stores the token and navigates when the API accepts it', async () => {
      await attempt((request) =>
        request.flush({ authenticated: true, message: 'Authentication successful' }),
      );

      expect(localStorage.getItem(TOKEN_KEY)).toBe('secret-token');
      expect(TestBed.inject(AuthService).isAuthenticated()).toBe(true);
      expect(navigate).toHaveBeenCalledWith(['/'], { replaceUrl: true });
      expect(host().querySelector('[role="alert"]')).toBeNull();
    });
  });
});
