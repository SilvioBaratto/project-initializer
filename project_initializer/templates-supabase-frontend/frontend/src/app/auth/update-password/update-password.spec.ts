/**
 * Tests for UpdatePasswordComponent (supabase password update view on Angular Material).
 * Criteria: one h1 inside a single main landmark; two outlined, labelled password fields with
 * new-password autocomplete plus a hidden username field for password managers; one filled
 * submit and a text link back to sign in; invalid submits show specific field errors, focus the
 * field to fix and skip the service; a valid submit updates the password, confirms it under an
 * h2 that takes focus, never navigates on its own and offers one filled link that opens the app
 * replacing history; API failures show an alert and never mark a field invalid (aria-invalid follows the
 * fields' own validity); while updating the focused submit stays focusable as an aria-disabled,
 * aria-busy button with a spinner, the status is announced outside any busy subtree, repeat
 * submits are ignored and focus stays on the button after a failure; without a recovery session
 * or a signed-in user the view offers a new reset link instead.
 * Icons come from the app's registry (icons.ts), and one test renders the confirmation with only
 * the providers in app.config.ts, so an overlay config without ICON_PROVIDER fails here.
 */
import { EnvironmentProviders, Provider, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatCardHarness } from '@angular/material/card/testing';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';
import { MatInputHarness } from '@angular/material/input/testing';
import { MatProgressSpinnerHarness } from '@angular/material/progress-spinner/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { type Mock, type MockInstance, vi } from 'vitest';
import { appConfig } from '../../app.config';
import { ICON_PROVIDER } from '../../icons';
import { AuthService } from '../../services/auth';
import { UpdatePasswordComponent } from './update-password';

interface UpdateResult {
  success: boolean;
  message: string;
}

interface SetupOptions {
  recovery?: boolean;
  authenticated?: boolean;
  email?: string | null;
  /** App-level providers; AuthService is always faked on top of them. */
  providers?: (Provider | EnvironmentProviders)[];
}

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe('UpdatePasswordComponent', () => {
  let fixture: ComponentFixture<UpdatePasswordComponent>;
  let loader: HarnessLoader;
  let updatePassword: Mock<(password: string) => Promise<UpdateResult>>;
  let navigate: MockInstance<Router['navigate']>;

  async function setup({
    recovery = true,
    authenticated = false,
    email = 'ada@example.com',
    providers = [provideRouter([]), ICON_PROVIDER],
  }: SetupOptions = {}): Promise<void> {
    updatePassword = vi.fn<(password: string) => Promise<UpdateResult>>();

    await TestBed.configureTestingModule({
      imports: [UpdatePasswordComponent],
      providers: [
        ...providers,
        {
          provide: AuthService,
          useValue: {
            waitUntilInitialized: () => Promise.resolve(),
            isPasswordRecovery: signal(recovery),
            isAuthenticated: signal(authenticated),
            currentUser: signal(email ? { email } : null),
            updatePassword,
          },
        },
      ],
    }).compileComponents();

    navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    fixture = TestBed.createComponent(UpdatePasswordComponent);
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
    await fixture.whenStable();
  }

  afterEach(() => {
    vi.useRealTimers();
  });

  const host = (): HTMLElement => fixture.nativeElement;
  const passwordNative = (): HTMLInputElement => host().querySelector('input#password')!;
  const confirmNative = (): HTMLInputElement => host().querySelector('input#confirmPassword')!;
  const alertText = (): string | undefined =>
    host().querySelector('[role="alert"]')?.textContent?.trim();
  const submitButton = () => loader.getHarness(MatButtonHarness.with({ text: 'Update password' }));
  const submitNative = (): HTMLButtonElement => host().querySelector('button[type="submit"]')!;
  const passwordField = () =>
    loader.getHarness(MatFormFieldHarness.with({ floatingLabelText: 'New password' }));
  const confirmField = () =>
    loader.getHarness(MatFormFieldHarness.with({ floatingLabelText: 'Confirm new password' }));
  const passwordInput = () => loader.getHarness(MatInputHarness.with({ selector: '#password' }));
  const confirmInput = () =>
    loader.getHarness(MatInputHarness.with({ selector: '#confirmPassword' }));

  async function fill(password: string, confirmPassword: string): Promise<void> {
    await (await passwordInput()).setValue(password);
    await (await confirmInput()).setValue(confirmPassword);
  }

  describe('structure', () => {
    beforeEach(() => setup());

    it('renders one h1 naming the view inside a single main landmark', async () => {
      const headings = host().querySelectorAll('h1');
      expect(headings.length).toBe(1);
      expect(headings[0].textContent?.trim()).toBe('Update password');
      expect(host().querySelectorAll('main').length).toBe(1);
      expect(host().querySelector('main h1')).toBe(headings[0]);

      const card = await loader.getHarness(MatCardHarness);
      expect(await card.getTitleText()).toBe('Update password');
      expect(await card.getSubtitleText()).toBe('Choose a new password for your account');
    });

    it('renders two outlined, labelled password fields with new-password autocomplete', async () => {
      const fields = await loader.getAllHarnesses(MatFormFieldHarness);
      expect(fields.length).toBe(2);
      for (const field of fields) {
        expect(await field.getAppearance()).toBe('outline');
      }
      expect(await fields[0].getLabel()).toBe('New password');
      expect(await fields[1].getLabel()).toBe('Confirm new password');

      expect(await (await passwordInput()).getType()).toBe('password');
      expect(await (await confirmInput()).getType()).toBe('password');
      expect(passwordNative().getAttribute('autocomplete')).toBe('new-password');
      expect(confirmNative().getAttribute('autocomplete')).toBe('new-password');
    });

    it('states the length requirement up front', async () => {
      expect(await (await passwordField()).getTextHints()).toEqual(['Use at least 6 characters']);
    });

    it('gives password managers the account in a hidden username field', () => {
      const username = host().querySelector<HTMLInputElement>('input[autocomplete="username"]')!;
      expect(username.value).toBe('ada@example.com');
      expect(username.hidden).toBe(true);
    });

    it('uses one filled submit button and a text link back to sign in', async () => {
      const submit = await submitButton();
      expect(await submit.getAppearance()).toBe('filled');
      expect(await submit.getType()).toBe('submit');
      expect(await submit.isDisabled()).toBe(false);

      const back = await loader.getHarness(MatButtonHarness.with({ text: 'Back to sign in' }));
      expect(await back.getAppearance()).toBe('text');
      expect(await (await back.host()).getAttribute('href')).toBe('/login');

      const filled = [];
      for (const button of await loader.getAllHarnesses(MatButtonHarness)) {
        if ((await button.getAppearance()) === 'filled') filled.push(button);
      }
      expect(filled.length).toBe(1);
    });

    it('shows no alert before a submit', () => {
      expect(host().querySelector('[role="alert"]')).toBeNull();
    });
  });

  describe('without a username', () => {
    it('omits the hidden username field when the account has no email', async () => {
      await setup({ email: null });
      expect(host().querySelector('input[autocomplete="username"]')).toBeNull();
    });
  });

  describe('validation', () => {
    beforeEach(() => setup());

    it('asks for a new password, focuses it and skips the service on an empty submit', async () => {
      await (await submitButton()).click();

      expect(await (await passwordField()).getTextErrors()).toEqual(['Enter a new password']);
      // Material leaves aria-invalid off an empty required field and links the error instead.
      const error = host().querySelector('mat-error')!;
      expect(passwordNative().getAttribute('aria-describedby')).toContain(error.id);
      expect(document.activeElement).toBe(passwordNative());
      expect(updatePassword).not.toHaveBeenCalled();
    });

    it('explains the length requirement when the password is too short', async () => {
      await fill('abc', 'abc');
      await (await submitButton()).click();

      expect(await (await passwordField()).getTextErrors()).toEqual(['Enter at least 6 characters']);
      expect(document.activeElement).toBe(passwordNative());
      expect(updatePassword).not.toHaveBeenCalled();
    });

    it('asks for the confirmation and focuses it when only the password is filled', async () => {
      await (await passwordInput()).setValue('correct-horse');
      await (await submitButton()).click();

      expect(await (await confirmField()).getTextErrors()).toEqual(['Enter the password again']);
      expect(document.activeElement).toBe(confirmNative());
      expect(updatePassword).not.toHaveBeenCalled();
    });

    it('flags a mismatched confirmation, focuses it and skips the service', async () => {
      await fill('correct-horse', 'battery-staple');
      await (await submitButton()).click();

      expect(await (await confirmField()).getTextErrors()).toEqual(["Passwords don't match"]);
      expect(confirmNative().getAttribute('aria-invalid')).toBe('true');
      expect(await (await passwordField()).getTextErrors()).toEqual([]);
      expect(document.activeElement).toBe(confirmNative());
      expect(updatePassword).not.toHaveBeenCalled();
    });

    it('clears the mismatch error once the passwords match', async () => {
      await fill('correct-horse', 'battery-staple');
      await (await submitButton()).click();
      await (await confirmInput()).setValue('correct-horse');

      expect(await (await confirmField()).getTextErrors()).toEqual([]);
      expect(confirmNative().getAttribute('aria-invalid')).toBe('false');
    });
  });

  describe('updating', () => {
    beforeEach(() => setup());

    it('sends the new password, confirms the update and moves focus to the confirmation heading', async () => {
      updatePassword.mockResolvedValue({ success: true, message: 'Password updated successfully.' });

      await fill('correct-horse', 'correct-horse');
      await (await submitButton()).click();
      await fixture.whenStable();

      expect(updatePassword).toHaveBeenCalledExactlyOnceWith('correct-horse');
      expect(host().querySelector('form')).toBeNull();
      expect(host().querySelector('[role="alert"]')).toBeNull();

      // A heading under the card's h1, so heading navigation reaches it, and the focus target.
      expect(host().querySelectorAll('h1').length).toBe(1);
      const headings = host().querySelectorAll<HTMLElement>('h2');
      expect(headings.length).toBe(1);
      expect(headings[0].textContent?.trim()).toBe('Password updated');
      expect(headings[0].getAttribute('tabindex')).toBe('-1');
      expect(document.activeElement).toBe(headings[0]);
      expect(host().textContent).not.toContain('Taking you to the app');
      expect(await (await loader.getHarness(MatCardHarness)).getSubtitleText()).toBe('');
    });

    it('offers one filled link that opens the app, replacing the history entry', async () => {
      const router = TestBed.inject(Router);
      const navigateByUrl = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
      updatePassword.mockResolvedValue({ success: true, message: '' });
      await fill('correct-horse', 'correct-horse');
      await (await submitButton()).click();
      await fixture.whenStable();

      const open = await loader.getHarness(MatButtonHarness.with({ text: 'Open the app' }));
      expect(await open.getAppearance()).toBe('filled');
      expect(await (await open.host()).getAttribute('href')).toBe('/');
      // The user is signed in now, so the link back to sign in is gone and this is the only way on.
      expect(await loader.getAllHarnesses(MatButtonHarness)).toHaveLength(1);

      await open.click();

      expect(navigateByUrl).toHaveBeenCalledTimes(1);
      const [url, extras] = navigateByUrl.mock.calls[0];
      expect(router.serializeUrl(url as UrlTree)).toBe('/');
      expect(extras).toMatchObject({ replaceUrl: true });
    });

    it('never navigates on its own after the update', async () => {
      const navigateByUrl = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
      updatePassword.mockResolvedValue({ success: true, message: '' });
      await fill('correct-horse', 'correct-horse');

      vi.useFakeTimers();
      await fixture.componentInstance.onSubmit();
      vi.advanceTimersByTime(60_000);

      expect(fixture.componentInstance.updated()).toBe(true);
      expect(navigate).not.toHaveBeenCalled();
      expect(navigateByUrl).not.toHaveBeenCalled();
    });

    it('submits when the form itself is submitted (Enter in a field)', async () => {
      updatePassword.mockResolvedValue({ success: true, message: '' });

      await fill('correct-horse', 'correct-horse');
      host().querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
      await fixture.whenStable();

      expect(updatePassword).toHaveBeenCalledExactlyOnceWith('correct-horse');
    });
  });

  describe('with the app config', () => {
    it('renders the confirmation icon using only the providers from app.config.ts', async () => {
      // lucide-angular throws for an icon no LUCIDE_ICONS provider registers, so this fails when
      // the overlay's app config leaves out ICON_PROVIDER.
      await setup({ providers: appConfig.providers });
      updatePassword.mockResolvedValue({ success: true, message: '' });

      await fill('correct-horse', 'correct-horse');
      await (await submitButton()).click();
      await fixture.whenStable();

      const icon = host().querySelector('.update-password-success-icon lucide-icon');
      expect(icon).not.toBeNull();
      expect(icon!.querySelector('svg')).not.toBeNull();
      expect(icon!.getAttribute('aria-hidden')).toBe('true');
    });
  });

  describe('errors', () => {
    beforeEach(() => setup());

    async function submitValid(): Promise<void> {
      await fill('correct-horse', 'correct-horse');
      await (await submitButton()).click();
      await fixture.whenStable();
    }

    it('shows the API message in an alert without marking the valid fields invalid', async () => {
      updatePassword.mockResolvedValue({
        success: false,
        message: 'New password should be different from the old password.',
      });

      await submitValid();

      expect(alertText()).toBe('New password should be different from the old password.');
      // No field message explains a failed request, so neither field reports itself invalid.
      expect(passwordNative().getAttribute('aria-invalid')).toBe('false');
      expect(confirmNative().getAttribute('aria-invalid')).toBe('false');
      expect(host().querySelectorAll('mat-form-field.mat-form-field-invalid')).toHaveLength(0);
      expect(await (await passwordField()).getTextErrors()).toEqual([]);
      expect(await (await confirmField()).getTextErrors()).toEqual([]);
      expect(host().querySelector('form')).not.toBeNull();
      expect(host().querySelector('h2')).toBeNull();
      expect(navigate).not.toHaveBeenCalled();
    });

    it('keeps untouched fields valid when a request fails', async () => {
      updatePassword.mockResolvedValue({ success: false, message: 'Email rate limit exceeded' });
      fixture.componentInstance.form.setValue({
        password: 'correct-horse',
        confirmPassword: 'correct-horse',
      });

      await fixture.componentInstance.onSubmit();
      await fixture.whenStable();

      expect(fixture.componentInstance.form.touched).toBe(false);
      expect(alertText()).toBe('Email rate limit exceeded');
      expect(passwordNative().getAttribute('aria-invalid')).toBe('false');
      expect(confirmNative().getAttribute('aria-invalid')).toBe('false');
    });

    it('falls back to a retry message when the failure has no message', async () => {
      updatePassword.mockResolvedValue({ success: false, message: '' });

      await submitValid();

      expect(alertText()).toBe("Couldn't update your password. Try again.");
    });

    it('clears the previous alert when a new attempt starts', async () => {
      updatePassword.mockResolvedValueOnce({ success: false, message: 'Weak password' });
      await submitValid();
      expect(alertText()).toBe('Weak password');

      updatePassword.mockReturnValueOnce(deferred<UpdateResult>().promise);
      await (await submitButton()).click();
      await fixture.whenStable();

      expect(host().querySelector('[role="alert"]')).toBeNull();
      expect(passwordNative().getAttribute('aria-invalid')).toBe('false');
    });
  });

  describe('while updating', () => {
    let pending: ReturnType<typeof deferred<UpdateResult>>;

    beforeEach(async () => {
      await setup();
      pending = deferred<UpdateResult>();
      updatePassword.mockReturnValue(pending.promise);
      await fill('correct-horse', 'correct-horse');
      submitNative().focus();
      await (await submitButton()).click();
      await fixture.whenStable();
    });

    it('keeps focus on the submit button, disabled but focusable and busy, with a spinner', async () => {
      // Focusable disabled state: a native `disabled` attribute would drop keyboard focus to <body>.
      expect(await (await submitButton()).isDisabled()).toBe(true);
      expect(submitNative().hasAttribute('disabled')).toBe(false);
      expect(submitNative().getAttribute('aria-disabled')).toBe('true');
      expect(submitNative().getAttribute('aria-busy')).toBe('true');
      expect(document.activeElement).toBe(submitNative());
      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(1);
      // A <button> may not contain a descendant with a tabindex attribute.
      expect(submitNative().querySelectorAll('[tabindex]')).toHaveLength(0);
    });

    it('announces the status outside any busy subtree', () => {
      // Busy state sits on the button, so the live regions are never inside an aria-busy subtree.
      expect(host().querySelector('form')!.hasAttribute('aria-busy')).toBe(false);

      const status = host().querySelector('[role="status"]')!;
      expect(status.textContent?.trim()).toBe('Updating password…');
      expect(status.closest('[aria-busy]')).toBeNull();
    });

    it('ignores a click, an implicit submit or a direct call until the request settles', async () => {
      // The busy button has no native `disabled`, so a click and Enter in a field still submit.
      await (await submitButton()).click();
      host().querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
      await fixture.componentInstance.onSubmit();
      await fixture.whenStable();

      expect(updatePassword).toHaveBeenCalledTimes(1);
    });

    it('restores the idle state after the request settles', async () => {
      pending.resolve({ success: false, message: 'Weak password' });
      await fixture.whenStable();

      expect(await (await submitButton()).isDisabled()).toBe(false);
      expect(submitNative().hasAttribute('aria-disabled')).toBe(false);
      expect(submitNative().hasAttribute('aria-busy')).toBe(false);
      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(0);
      expect(host().querySelector('[role="status"]')!.textContent?.trim()).toBe('');
    });

    it('leaves focus on the submit button when the update fails', async () => {
      pending.resolve({ success: false, message: 'Weak password' });
      // Let onSubmit resume past its await (its continuation was queued first) before settling.
      await pending.promise;
      await fixture.whenStable();

      expect(alertText()).toBe('Weak password');
      expect(document.activeElement).toBe(submitNative());
    });
  });

  describe('without a recovery session', () => {
    it('offers a new reset link instead of the form', async () => {
      await setup({ recovery: false, authenticated: false });

      expect(host().querySelector('form')).toBeNull();
      expect(host().querySelectorAll('h1').length).toBe(1);
      // A heading under the card's h1, so heading navigation reaches the explanation.
      const headings = host().querySelectorAll('h2');
      expect(headings.length).toBe(1);
      expect(headings[0].textContent?.trim()).toBe('No valid reset link found');

      const request = await loader.getHarness(
        MatButtonHarness.with({ text: 'Request reset link' }),
      );
      expect(await request.getAppearance()).toBe('filled');
      expect(await (await request.host()).getAttribute('href')).toBe('/auth/forgot-password');
      expect(await (await loader.getHarness(MatCardHarness)).getSubtitleText()).toBe('');
    });

    it('keeps the form for a signed-in user outside the recovery flow', async () => {
      await setup({ recovery: false, authenticated: true });

      expect(host().querySelector('form')).not.toBeNull();
      expect(host().textContent).not.toContain('No valid reset link found');
    });
  });
});
