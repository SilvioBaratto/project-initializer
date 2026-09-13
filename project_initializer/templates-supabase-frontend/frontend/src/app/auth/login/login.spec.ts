import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { TestBed } from '@angular/core/testing';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatCardHarness } from '@angular/material/card/testing';
import { MATERIAL_ANIMATIONS } from '@angular/material/core';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';
import { MatInputHarness } from '@angular/material/input/testing';
import { MatProgressSpinnerHarness } from '@angular/material/progress-spinner/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { vi, type Mock } from 'vitest';

import { ICON_PROVIDER } from '../../icons';
import { AuthService } from '../../services/auth';
import { LoginComponent } from './login';

interface AuthResult {
  success: boolean;
  message: string;
}

interface AuthServiceStub {
  login: Mock<(email: string, password: string) => Promise<AuthResult>>;
  signup: Mock<(email: string, password: string) => Promise<AuthResult>>;
  loginWithGoogle: Mock<() => Promise<void>>;
}

describe('LoginComponent', () => {
  let auth: AuthServiceStub;
  let routerHarness: RouterTestingHarness;
  let loader: HarnessLoader;
  let host: HTMLElement;

  async function setup(url = '/login'): Promise<void> {
    auth = {
      login: vi.fn(async () => ({ success: true, message: 'Authenticated' })),
      signup: vi.fn(async () => ({
        success: true,
        message: 'Check your email to confirm your account.',
      })),
      loginWithGoogle: vi.fn(async () => undefined),
    };

    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'login', component: LoginComponent }]),
        { provide: AuthService, useValue: auth },
        { provide: MATERIAL_ANIMATIONS, useValue: { animationsDisabled: true } },
        ICON_PROVIDER,
      ],
    });

    routerHarness = await RouterTestingHarness.create();
    await routerHarness.navigateByUrl(url, LoginComponent);
    host = routerHarness.routeNativeElement as HTMLElement;
    loader = TestbedHarnessEnvironment.loader(routerHarness.fixture);
  }

  /** Lets the awaited AuthService promise resolve, then renders. */
  async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve));
    await routerHarness.fixture.whenStable();
  }

  const input = (controlName: string) =>
    loader.getHarness(MatInputHarness.with({ selector: `[formControlName="${controlName}"]` }));
  const inputElement = (controlName: string) =>
    host.querySelector<HTMLInputElement>(`[formControlName="${controlName}"]`) as HTMLInputElement;
  const field = (label: string) =>
    loader.getHarness(MatFormFieldHarness.with({ floatingLabelText: label }));
  const submitButton = () =>
    loader.getHarness(MatButtonHarness.with({ selector: '[type="submit"]' }));
  const submitElement = () =>
    host.querySelector<HTMLButtonElement>('button[type="submit"]') as HTMLButtonElement;
  const googleElement = () =>
    Array.from(host.querySelectorAll<HTMLButtonElement>('button')).find((button) =>
      button.textContent?.includes('with Google'),
    ) as HTMLButtonElement;
  const switchButton = () => loader.getHarness(MatButtonHarness.with({ ancestor: '.switch' }));
  const alertRegion = () => host.querySelector<HTMLElement>('[role="alert"]') as HTMLElement;
  const statusRegion = () => host.querySelector<HTMLElement>('[role="status"]') as HTMLElement;
  const labels = async () =>
    Promise.all((await loader.getAllHarnesses(MatFormFieldHarness)).map((f) => f.getLabel()));
  const allFieldErrors = async () =>
    (
      await Promise.all(
        (await loader.getAllHarnesses(MatFormFieldHarness)).map((f) => f.getTextErrors()),
      )
    ).flat();

  async function fillCredentials(email: string, password: string): Promise<void> {
    await (await input('email')).setValue(email);
    await (await input('password')).setValue(password);
  }

  describe('structure', () => {
    it('renders one h1 as the card title inside a main landmark', async () => {
      await setup();

      const headings = host.querySelectorAll('h1');
      expect(headings).toHaveLength(1);
      expect(headings[0].textContent?.trim()).toBe('Sign in');
      expect(host.querySelector('main')?.contains(headings[0])).toBe(true);

      const card = await loader.getHarness(MatCardHarness);
      expect(await (await card.host()).hasClass('mat-mdc-card-outlined')).toBe(true);
      expect(headings[0].classList.contains('mat-mdc-card-title')).toBe(true);
      expect(headings[0].closest('mat-card-header')).not.toBeNull();
      expect(await card.getTitleText()).toBe('Sign in');
      expect(await card.getSubtitleText()).toBe('Enter your email and password to continue');
    });

    it('labels outlined email and password fields with sign-in autocomplete tokens', async () => {
      await setup();

      expect(await labels()).toEqual(['Email', 'Password']);
      const fields = await loader.getAllHarnesses(MatFormFieldHarness);
      expect(await Promise.all(fields.map((f) => f.getAppearance()))).toEqual(['outline', 'outline']);

      const email = await input('email');
      expect(await email.getType()).toBe('email');
      expect(await (await email.host()).getAttribute('autocomplete')).toBe('username');
      const password = await input('password');
      expect(await password.getType()).toBe('password');
      expect(await (await password.host()).getAttribute('autocomplete')).toBe('current-password');
    });

    it('uses one filled primary action and text buttons for the secondary links', async () => {
      await setup();

      expect(await (await submitButton()).getAppearance()).toBe('filled');
      const google = await loader.getHarness(MatButtonHarness.with({ text: 'Sign in with Google' }));
      expect(await google.getAppearance()).toBe('outlined');
      const reset = await loader.getHarness(MatButtonHarness.with({ text: 'Reset password' }));
      expect(await reset.getAppearance()).toBe('text');
      expect(await (await reset.host()).getAttribute('href')).toBe('/auth/forgot-password');
      expect(await (await switchButton()).getAppearance()).toBe('text');
      expect(await loader.getAllHarnesses(MatButtonHarness.with({ appearance: 'filled' }))).toHaveLength(1);
      // A standalone label, so it takes sentence case.
      expect(host.querySelector('.divider')?.textContent?.trim()).toBe('Or');
    });
  });

  describe('validation', () => {
    it('keeps the primary action enabled, so an empty submit reveals both errors, focuses the email field and skips the service', async () => {
      await setup();
      const submit = await submitButton();

      // A disabled default button would also block Enter (implicit submission) in the fields.
      expect(await submit.isDisabled()).toBe(false);
      expect(submitElement().hasAttribute('disabled')).toBe(false);

      await submit.click();
      await settle();

      expect(await allFieldErrors()).toEqual(['Enter your email', 'Enter your password']);
      expect(document.activeElement).toBe(inputElement('email'));
      expect(auth.login).not.toHaveBeenCalled();
    });

    it('focuses the password when only it is invalid and explains the length rule', async () => {
      await setup();

      await fillCredentials('ada@example.com', '12345');
      await (await submitButton()).click();
      await settle();

      expect(await (await field('Password')).getTextErrors()).toEqual(['Enter at least 6 characters']);
      expect(await (await field('Email')).getTextErrors()).toEqual([]);
      expect(document.activeElement).toBe(inputElement('password'));
      expect(auth.login).not.toHaveBeenCalled();
    });

    it('reveals what is missing when the form is submitted with Enter in a field', async () => {
      await setup();

      await (await input('email')).setValue('not-an-email');
      host.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
      await settle();

      expect(await (await field('Email')).getTextErrors()).toEqual([
        'Enter an email address like name@example.com',
      ]);
      expect(document.activeElement).toBe(inputElement('email'));
      expect(auth.login).not.toHaveBeenCalled();
    });

    it('shows a field error once the user leaves an invalid email', async () => {
      await setup();
      const email = await input('email');

      await email.setValue('not-an-email');
      await email.blur();

      expect(await (await field('Email')).getTextErrors()).toEqual([
        'Enter an email address like name@example.com',
      ]);
      expect(await (await email.host()).getAttribute('aria-invalid')).toBe('true');
    });

    it('asks for the password when the field is left empty', async () => {
      await setup();
      const password = await input('password');

      await password.focus();
      await password.blur();

      expect(await (await field('Password')).getTextErrors()).toEqual(['Enter your password']);
    });
  });

  describe('sign in', () => {
    it('signs in with the trimmed password and navigates to the return url', async () => {
      await setup('/login?returnUrl=%2Fdashboard');
      const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);

      await fillCredentials('ada@example.com', '  secret1  ');
      await (await submitButton()).click();
      await settle();

      expect(auth.login).toHaveBeenCalledWith('ada@example.com', 'secret1');
      expect(navigate).toHaveBeenCalledWith(['/dashboard'], { replaceUrl: true });
    });

    it('keeps focus on the busy primary action, then reports the failure in an alert', async () => {
      await setup();
      let resolveLogin: (result: AuthResult) => void = () => undefined;
      auth.login.mockImplementation(
        () => new Promise<AuthResult>((resolve) => (resolveLogin = resolve)),
      );

      await fillCredentials('ada@example.com', 'secret1');
      const submit = await submitButton();
      const button = submitElement();
      button.focus();
      await submit.click();
      await settle();

      // Busy state sits on the button, so neither live region is inside an aria-busy subtree.
      expect(button.getAttribute('aria-busy')).toBe('true');
      expect(host.querySelector('form')?.hasAttribute('aria-busy')).toBe(false);
      expect(alertRegion().closest('[aria-busy]')).toBeNull();
      expect(statusRegion().closest('[aria-busy]')).toBeNull();

      // Focusable disabled state: a native `disabled` attribute would drop keyboard focus to <body>.
      expect(await submit.isDisabled()).toBe(true);
      expect(button.hasAttribute('disabled')).toBe(false);
      expect(button.getAttribute('aria-disabled')).toBe('true');
      expect(document.activeElement).toBe(button);

      expect(await submit.getText()).toBe('Sign in');
      const spinner = await loader.getHarness(
        MatProgressSpinnerHarness.with({ ancestor: '[type="submit"]' }),
      );
      expect(await spinner.getMode()).toBe('indeterminate');
      expect(await (await spinner.host()).getAttribute('aria-hidden')).toBe('true');
      // A <button> may not contain a descendant with a tabindex attribute.
      expect(button.querySelectorAll('[tabindex]')).toHaveLength(0);
      expect(statusRegion().textContent?.trim()).toBe('Signing in…');

      // Only the activated action is busy: the Google action is disabled but keeps its brand mark.
      const google = googleElement();
      expect(google.getAttribute('aria-disabled')).toBe('true');
      expect(google.hasAttribute('aria-busy')).toBe(false);
      expect(google.querySelector('mat-progress-spinner')).toBeNull();
      expect(google.querySelector('svg.brand-mark')).not.toBeNull();

      await submit.click();
      await settle();
      expect(auth.login).toHaveBeenCalledTimes(1);

      resolveLogin({ success: false, message: 'Invalid login credentials' });
      await settle();

      expect(button.hasAttribute('aria-busy')).toBe(false);
      expect(button.hasAttribute('aria-disabled')).toBe(false);
      expect(document.activeElement).toBe(button);
      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(0);
      expect(statusRegion().textContent?.trim()).toBe('');
      expect(alertRegion().textContent?.trim()).toBe('Invalid login credentials');
      expect(await submit.isDisabled()).toBe(false);
    });

    it('shows a retry message when sign-in fails without a message', async () => {
      await setup();
      auth.login.mockResolvedValue({ success: false, message: '' });

      await fillCredentials('ada@example.com', 'secret1');
      await (await submitButton()).click();
      await settle();

      expect(alertRegion().textContent?.trim()).toBe("Couldn't sign you in. Try again.");
    });

    it('keeps focus on the busy Google action while it starts, and reports a failure to open it', async () => {
      await setup();
      let rejectGoogle: (error: Error) => void = () => undefined;
      auth.loginWithGoogle.mockImplementation(
        () => new Promise<void>((_, reject) => (rejectGoogle = reject)),
      );
      const google = await loader.getHarness(MatButtonHarness.with({ text: 'Sign in with Google' }));
      const button = googleElement();

      button.focus();
      await google.click();
      await settle();

      expect(auth.loginWithGoogle).toHaveBeenCalledTimes(1);
      expect(await google.isDisabled()).toBe(true);
      expect(button.hasAttribute('disabled')).toBe(false);
      expect(button.getAttribute('aria-disabled')).toBe('true');
      expect(button.getAttribute('aria-busy')).toBe('true');
      expect(document.activeElement).toBe(button);

      // The spinner takes the brand mark's leading icon slot in the button the user activated.
      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(1);
      const spinner = button.querySelector<HTMLElement>('mat-progress-spinner')!;
      expect(spinner).not.toBeNull();
      expect(spinner.getAttribute('aria-hidden')).toBe('true');
      expect(spinner.nextElementSibling?.classList.contains('mdc-button__label')).toBe(true);
      expect(button.querySelector('svg.brand-mark')).toBeNull();
      // A <button> may not contain a descendant with a tabindex attribute.
      expect(button.querySelectorAll('[tabindex]')).toHaveLength(0);

      // The email submit is disabled too, but it isn't the busy one.
      expect(submitElement().getAttribute('aria-disabled')).toBe('true');
      expect(submitElement().hasAttribute('aria-busy')).toBe(false);
      expect(statusRegion().textContent?.trim()).toBe('Opening Google sign-in…');
      expect(statusRegion().closest('[aria-busy]')).toBeNull();

      await google.click();
      await settle();
      expect(auth.loginWithGoogle).toHaveBeenCalledTimes(1);

      rejectGoogle(new Error('popup blocked'));
      await settle();

      expect(alertRegion().textContent?.trim()).toBe("Couldn't open Google sign-in. Try again.");
      expect(await google.isDisabled()).toBe(false);
      expect(button.hasAttribute('aria-busy')).toBe(false);
      expect(button.querySelector('svg.brand-mark')).not.toBeNull();
      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(0);
      expect(statusRegion().textContent?.trim()).toBe('');
      expect(document.activeElement).toBe(button);
    });
  });

  describe('create account', () => {
    it('switches mode in place, keeping focus on the switch button', async () => {
      await setup();
      const toggle = host.querySelector<HTMLButtonElement>('.switch button') as HTMLButtonElement;

      toggle.focus();
      toggle.click();
      await routerHarness.fixture.whenStable();

      expect(host.querySelector('h1')?.textContent?.trim()).toBe('Create account');
      expect(document.activeElement).toBe(toggle);
      expect(toggle.textContent?.trim()).toBe('Sign in');
      expect(await labels()).toEqual(['Email', 'Password', 'Confirm password']);
      expect(await (await field('Password')).getTextHints()).toEqual(['Use at least 6 characters']);
      expect(await (await (await input('password')).host()).getAttribute('autocomplete')).toBe('new-password');
      expect(await (await (await input('confirmPassword')).host()).getAttribute('autocomplete')).toBe('new-password');
      expect(await (await submitButton()).getText()).toBe('Create account');
      expect(await loader.getAllHarnesses(MatButtonHarness.with({ text: 'Reset password' }))).toHaveLength(0);
      // "Create account" stays the only verb for creating one; the Google action says "Continue".
      expect(await loader.getAllHarnesses(MatButtonHarness.with({ text: 'Continue with Google' }))).toHaveLength(1);
      expect(host.textContent).not.toContain('Sign up');
    });

    it('shows a mismatch on the confirmation field without calling sign-up, then clears it once the passwords match', async () => {
      await setup();
      await (await switchButton()).click();

      await fillCredentials('ada@example.com', 'secret1');
      const confirm = await input('confirmPassword');
      await confirm.setValue('secret2');
      submitElement().focus();
      await (await submitButton()).click();
      await settle();

      expect(auth.signup).not.toHaveBeenCalled();
      expect(await (await field('Confirm password')).getTextErrors()).toEqual(["Passwords don't match"]);
      expect(await (await confirm.host()).getAttribute('aria-invalid')).toBe('true');
      expect(document.activeElement).toBe(inputElement('confirmPassword'));
      expect(alertRegion().textContent?.trim()).toBe('');

      await confirm.setValue('secret1');
      expect(await (await field('Confirm password')).getTextErrors()).toEqual([]);
      expect(await (await confirm.host()).getAttribute('aria-invalid')).not.toBe('true');

      await (await submitButton()).click();
      await settle();
      expect(auth.signup).toHaveBeenCalledWith('ada@example.com', 'secret1');
    });

    it('asks for the confirmation when it is left empty on submit', async () => {
      await setup();
      await (await switchButton()).click();

      await fillCredentials('ada@example.com', 'secret1');
      submitElement().focus();
      await (await submitButton()).click();
      await settle();

      expect(auth.signup).not.toHaveBeenCalled();
      expect(await (await field('Confirm password')).getTextErrors()).toEqual(['Enter the password again']);
      expect(document.activeElement).toBe(inputElement('confirmPassword'));
    });

    it('starts the other mode with empty fields and no leftover errors after a submit', async () => {
      await setup();
      auth.login.mockResolvedValue({ success: false, message: 'Invalid login credentials' });

      await fillCredentials('ada@example.com', 'secret1');
      await (await submitButton()).click();
      await settle();
      expect(alertRegion().textContent?.trim()).toBe('Invalid login credentials');

      await (await switchButton()).click();
      expect(alertRegion().textContent?.trim()).toBe('');
      expect(await labels()).toEqual(['Email', 'Password', 'Confirm password']);
      expect(await (await input('email')).getValue()).toBe('');
      expect(await allFieldErrors()).toEqual([]);

      await fillCredentials('ada@example.com', 'secret1');
      await (await input('confirmPassword')).setValue('secret2');
      await (await submitButton()).click();
      await settle();
      expect(await allFieldErrors()).toEqual(["Passwords don't match"]);

      await (await switchButton()).click();
      expect(await labels()).toEqual(['Email', 'Password']);
      expect(await allFieldErrors()).toEqual([]);
    });

    it('announces its own confirmation copy in a status region and clears both password fields without errors', async () => {
      await setup();
      await (await switchButton()).click();

      await fillCredentials('ada@example.com', 'secret1');
      await (await input('confirmPassword')).setValue('secret1');
      await (await submitButton()).click();
      await settle();

      expect(auth.signup).toHaveBeenCalledWith('ada@example.com', 'secret1');
      // A single sentence takes no period; the service's own message isn't shown.
      expect(statusRegion().textContent?.trim()).toBe('Check your email to confirm your account');
      expect(await (await input('email')).getValue()).toBe('ada@example.com');
      expect(await (await input('password')).getValue()).toBe('');
      expect(await (await input('confirmPassword')).getValue()).toBe('');
      expect(await allFieldErrors()).toEqual([]);
    });

    it('shows a retry message when account creation fails without a message', async () => {
      await setup();
      auth.signup.mockResolvedValue({ success: false, message: '' });
      await (await switchButton()).click();

      await fillCredentials('ada@example.com', 'secret1');
      await (await input('confirmPassword')).setValue('secret1');
      await (await submitButton()).click();
      await settle();

      expect(alertRegion().textContent?.trim()).toBe("Couldn't create your account. Try again.");
    });
  });
});
