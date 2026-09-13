import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatFormFieldHarness } from '@angular/material/form-field/testing';
import { MatInputHarness } from '@angular/material/input/testing';
import { MatProgressSpinnerHarness } from '@angular/material/progress-spinner/testing';
import { provideRouter } from '@angular/router';
import { type Mock, vi } from 'vitest';
import { appConfig } from '../../app.config';
import { ICON_PROVIDER } from '../../icons';
import { AuthService } from '../../services/auth';
import { ForgotPasswordComponent } from './forgot-password';

type ResetResult = { success: boolean; message: string };

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => (resolve = res));
  return { promise, resolve };
}

describe('ForgotPasswordComponent', () => {
  let fixture: ComponentFixture<ForgotPasswordComponent>;
  let host: HTMLElement;
  let loader: HarnessLoader;
  let forgotPassword: Mock<(email: string) => Promise<ResetResult>>;

  const submitButton = () => loader.getHarness(MatButtonHarness.with({ text: 'Send reset link' }));
  const submitElement = () => host.querySelector<HTMLButtonElement>('button[type="submit"]')!;

  async function submitWith(email: string): Promise<void> {
    const input = await loader.getHarness(MatInputHarness);
    await input.setValue(email);
    await (await submitButton()).click();
    await fixture.whenStable();
  }

  beforeEach(async () => {
    forgotPassword = vi.fn<(email: string) => Promise<ResetResult>>();

    // Icons are registered names from the app's registry (icons.ts), which app.config.ts provides.
    await TestBed.configureTestingModule({
      imports: [ForgotPasswordComponent],
      providers: [
        provideRouter([]),
        ICON_PROVIDER,
        { provide: AuthService, useValue: { forgotPassword } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ForgotPasswordComponent);
    host = fixture.nativeElement;
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  it('when rendered, the view has one h1 inside the main landmark and an outlined card', () => {
    const main = host.querySelector('main');
    const headings = host.querySelectorAll('h1');

    expect(main).not.toBeNull();
    expect(headings.length).toBe(1);
    expect(headings[0].textContent?.trim()).toBe('Reset your password');
    expect(main!.contains(headings[0])).toBe(true);
    expect(host.querySelector('mat-card')?.classList).toContain('mat-mdc-card-outlined');
  });

  it('when rendered, the email field is an outlined form field whose autofill matches the sign-in screen', async () => {
    const field = await loader.getHarness(MatFormFieldHarness);
    const input = host.querySelector('input')!;

    expect(await field.getAppearance()).toBe('outline');
    expect(await field.getLabel()).toBe('Email');
    expect(input.type).toBe('email');
    expect(input.getAttribute('autocomplete')).toBe('username');
    expect(input.getAttribute('autocapitalize')).toBe('none');
    expect(input.getAttribute('spellcheck')).toBe('false');
  });

  it('when rendered, the single primary action is a filled button and sign in is a text link', async () => {
    const submit = await submitButton();
    const back = await loader.getHarness(MatButtonHarness.with({ text: 'Back to sign in' }));

    expect(await submit.getAppearance()).toBe('filled');
    expect(await submit.isDisabled()).toBe(false);
    expect(await back.getAppearance()).toBe('text');
    expect(await (await back.host()).getAttribute('href')).toBe('/login');
  });

  it('when submitted empty, the required error shows, focus moves to the field and nothing is sent', async () => {
    await (await submitButton()).click();
    await fixture.whenStable();

    const field = await loader.getHarness(MatFormFieldHarness);
    expect(await field.getTextErrors()).toEqual(['Enter your email']);
    expect(document.activeElement).toBe(host.querySelector('input'));
    expect(forgotPassword).not.toHaveBeenCalled();
  });

  it('when the email is malformed, the field is invalid and explains the expected format', async () => {
    const input = await loader.getHarness(MatInputHarness);
    await input.setValue('not-an-email');
    await input.blur();

    const field = await loader.getHarness(MatFormFieldHarness);
    expect(await field.getTextErrors()).toEqual(['Enter an email address like name@example.com']);
    expect(await field.isControlValid()).toBe(false);
    expect(host.querySelector('input')?.getAttribute('aria-invalid')).toBe('true');
  });

  it('while the request is pending, the focused submit stays focusable as a busy disabled button with a spinner and the status is announced', async () => {
    const pending = deferred<ResetResult>();
    forgotPassword.mockReturnValue(pending.promise);

    await (await loader.getHarness(MatInputHarness)).setValue('user@example.com');
    const button = submitElement();
    button.focus();
    const submit = await submitButton();
    await submit.click();
    await fixture.whenStable();

    // Focusable disabled state: a native `disabled` attribute would drop keyboard focus to <body>.
    expect(await submit.isDisabled()).toBe(true);
    expect(button.hasAttribute('disabled')).toBe(false);
    expect(button.getAttribute('aria-disabled')).toBe('true');
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(document.activeElement).toBe(button);

    // Busy state sits on the button, so the live regions are never inside an aria-busy subtree.
    expect(host.querySelector('form')?.hasAttribute('aria-busy')).toBe(false);
    const status = host.querySelector('[role="status"]');
    expect(status?.closest('[aria-busy]')).toBeNull();
    expect(status?.textContent?.trim()).toBe('Sending reset link…');
    expect(await loader.getHarnessOrNull(MatProgressSpinnerHarness)).not.toBeNull();
    // A <button> may not contain a descendant with a tabindex attribute.
    expect(button.querySelectorAll('[tabindex]')).toHaveLength(0);

    pending.resolve({ success: false, message: 'Try again later' });
    // Let onSubmit resume past its await (its continuation was queued first) before settling.
    await pending.promise;
    await fixture.whenStable();

    expect(button.hasAttribute('aria-busy')).toBe(false);
    expect(button.hasAttribute('aria-disabled')).toBe(false);
    expect(await submit.isDisabled()).toBe(false);
    expect(await loader.getHarnessOrNull(MatProgressSpinnerHarness)).toBeNull();
    expect(host.querySelector('[role="status"]')?.textContent?.trim()).toBe('');
  });

  it('while the request is pending, a click or an implicit submit on the busy button is ignored', async () => {
    const pending = deferred<ResetResult>();
    forgotPassword.mockReturnValue(pending.promise);

    await submitWith('user@example.com');
    // The busy button has no native `disabled`, so both of these still reach onSubmit.
    await (await submitButton()).click();
    host.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    await fixture.whenStable();

    expect(forgotPassword).toHaveBeenCalledTimes(1);

    pending.resolve({ success: true, message: '' });
    await pending.promise;
    await fixture.whenStable();
  });

  it('when the service returns an error, focus stays on the submit button for another attempt', async () => {
    forgotPassword.mockResolvedValue({ success: false, message: 'Email rate limit exceeded' });

    await (await loader.getHarness(MatInputHarness)).setValue('user@example.com');
    const button = submitElement();
    button.focus();
    await (await submitButton()).click();
    await fixture.whenStable();

    expect(host.querySelector('[role="alert"]')?.textContent?.trim()).toBe('Email rate limit exceeded');
    expect(document.activeElement).toBe(button);
  });

  it('when the reset link is sent, the email goes to the service and focus lands on the confirmation', async () => {
    forgotPassword.mockResolvedValue({ success: true, message: 'Check your email for a password reset link.' });

    await submitWith('user@example.com');
    await fixture.whenStable();

    expect(forgotPassword).toHaveBeenCalledTimes(1);
    expect(forgotPassword).toHaveBeenCalledWith('user@example.com');
    expect(host.querySelector('form')).toBeNull();
    expect(host.querySelector('[matCardSubtitle]')).toBeNull();

    const heading = host.querySelector('h2');
    expect(heading?.textContent?.trim()).toBe('Check your email');
    expect(document.activeElement).toBe(heading);
    expect(host.querySelector('.forgot-password-sent')?.textContent).toContain('user@example.com');

    const mailIcon = host.querySelector('.forgot-password-sent-icon lucide-icon');
    expect(mailIcon?.getAttribute('aria-hidden')).toBe('true');
    expect(mailIcon?.querySelector('svg')).not.toBeNull();
  });

  it('when the service returns an error, it shows in an alert, the valid field is not marked invalid and the form stays usable', async () => {
    forgotPassword.mockResolvedValue({ success: false, message: 'Email rate limit exceeded' });

    await submitWith('user@example.com');

    expect(host.querySelector('[role="alert"]')?.textContent?.trim()).toBe('Email rate limit exceeded');
    expect(host.querySelector('mat-form-field')?.classList).not.toContain('mat-form-field-invalid');
    expect(host.querySelector('input')?.getAttribute('aria-invalid')).toBe('false');
    expect(host.querySelector('form')).not.toBeNull();
    expect(await (await submitButton()).isDisabled()).toBe(false);
  });

  it('when the request throws, a generic error shows and loading ends', async () => {
    forgotPassword.mockRejectedValue(new Error('network down'));

    await submitWith('user@example.com');

    expect(host.querySelector('[role="alert"]')?.textContent?.trim()).toBe(
      "Couldn't send the reset link. Try again.",
    );
    expect(fixture.componentInstance.isLoading()).toBe(false);
    expect(await (await submitButton()).isDisabled()).toBe(false);
  });

  it('when a new request starts, the previous error is cleared', async () => {
    forgotPassword.mockResolvedValueOnce({ success: false, message: 'Email rate limit exceeded' });
    await submitWith('user@example.com');
    expect(host.querySelector('[role="alert"]')).not.toBeNull();

    const pending = deferred<ResetResult>();
    forgotPassword.mockReturnValueOnce(pending.promise);
    await (await submitButton()).click();
    await fixture.whenStable();

    expect(host.querySelector('[role="alert"]')).toBeNull();
    pending.resolve({ success: true, message: '' });
    await fixture.whenStable();
  });

  it('when rendered, the back icon is the registered ArrowLeft, decorative and sized for a text button', () => {
    const icon = host.querySelector('.forgot-password-back-icon');
    expect(icon?.getAttribute('aria-hidden')).toBe('true');
    expect(icon?.hasAttribute('matButtonIcon')).toBe(true);
    expect(icon?.querySelector('svg')?.getAttribute('width')).toBe('18');
    // lucide-angular adds `lucide-<name>` only for an icon bound by registered name, not through [img].
    expect(icon?.querySelector('svg')?.classList).toContain('lucide-ArrowLeft');
  });
});

describe('ForgotPasswordComponent with the app config', () => {
  it('renders both icons using only the providers from app.config.ts', async () => {
    // lucide-angular throws for an icon name no LUCIDE_ICONS provider registers, so this fails
    // when the overlay's app config leaves out ICON_PROVIDER or the registry drops Mail/ArrowLeft.
    const forgotPassword = vi.fn(async () => ({ success: true, message: '' }));
    await TestBed.configureTestingModule({
      imports: [ForgotPasswordComponent],
      providers: [...appConfig.providers, { provide: AuthService, useValue: { forgotPassword } }],
    }).compileComponents();

    const fixture = TestBed.createComponent(ForgotPasswordComponent);
    const loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
    const host: HTMLElement = fixture.nativeElement;

    expect(host.querySelector('.forgot-password-back-icon svg')).not.toBeNull();

    await (await loader.getHarness(MatInputHarness)).setValue('user@example.com');
    await (await loader.getHarness(MatButtonHarness.with({ text: 'Send reset link' }))).click();
    await fixture.whenStable();

    expect(host.querySelector('.forgot-password-sent-icon lucide-icon svg')).not.toBeNull();
  });
});
