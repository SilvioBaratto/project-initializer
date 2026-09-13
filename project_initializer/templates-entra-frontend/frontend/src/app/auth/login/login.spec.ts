/**
 * Tests for LoginComponent (Microsoft Entra ID sign-in view on Angular Material).
 * Criteria: one h1 inside a single main landmark in an outlined card; one filled button named by
 * its visible text with a decorative Microsoft logo; a click starts the MSAL redirect once; while
 * the redirect starts the button is disabled but keeps keyboard focus (aria-disabled, never the
 * native attribute), is busy with a spinner and the status is announced; a failure to start,
 * which MSAL reports as a rejected promise, shows an alert, restores the idle state and leaves
 * focus on the button; a new attempt clears the alert.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HarnessLoader } from '@angular/cdk/testing';
import { TestbedHarnessEnvironment } from '@angular/cdk/testing/testbed';
import { MatButtonHarness } from '@angular/material/button/testing';
import { MatCardHarness } from '@angular/material/card/testing';
import { MatProgressSpinnerHarness } from '@angular/material/progress-spinner/testing';
import { vi } from 'vitest';
import { AuthService } from '../../core/services/auth.service';
import { LoginComponent } from './login';

const START_FAILED = "Couldn't start sign-in with Microsoft. Try again.";

describe('LoginComponent (Entra)', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let loader: HarnessLoader;
  let login: ReturnType<typeof vi.fn<() => void | Promise<void>>>;

  beforeEach(async () => {
    login = vi.fn<() => void | Promise<void>>();

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [{ provide: AuthService, useValue: { login } }],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    loader = TestbedHarnessEnvironment.loader(fixture);
    await fixture.whenStable();
  });

  /** Lets an awaited login() promise settle, then renders. */
  async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve));
    await fixture.whenStable();
  }

  const host = (): HTMLElement => fixture.nativeElement;
  const nativeButton = (): HTMLButtonElement => host().querySelector('button')!;
  const signInButton = () =>
    loader.getHarness(MatButtonHarness.with({ text: 'Sign in with Microsoft' }));
  const alert = () => host().querySelector('[role="alert"]');
  const status = () => host().querySelector('[role="status"]')!;

  /** Focuses the button the way a keyboard user would, then activates it. */
  async function focusAndClick(): Promise<void> {
    nativeButton().focus();
    await (await signInButton()).click();
    await settle();
  }

  describe('structure', () => {
    it('renders one h1 naming the view inside a single main landmark', async () => {
      const headings = host().querySelectorAll('h1');
      expect(headings.length).toBe(1);
      expect(headings[0].textContent?.trim()).toBe('Sign in');
      expect(host().querySelectorAll('main').length).toBe(1);
      expect(host().querySelector('main h1')).toBe(headings[0]);

      const card = await loader.getHarness(MatCardHarness);
      expect(await card.getTitleText()).toBe('Sign in');
      expect(await card.getSubtitleText()).toBe('Use your Microsoft account to continue');
      expect(host().querySelector('mat-card')!.classList).toContain('mat-mdc-card-outlined');
    });

    it('uses one filled button, named by its visible text, as the primary action', async () => {
      const buttons = await loader.getAllHarnesses(MatButtonHarness);
      expect(buttons.length).toBe(1);

      const button = await signInButton();
      expect(await button.getAppearance()).toBe('filled');
      expect(await button.getType()).toBe('button');
      expect(await button.isDisabled()).toBe(false);
      // Visible text is the accessible name; no aria-label that could diverge from it.
      expect(nativeButton().hasAttribute('aria-label')).toBe(false);
      expect(nativeButton().hasAttribute('aria-busy')).toBe(false);
      expect(nativeButton().hasAttribute('aria-disabled')).toBe(false);
    });

    it('shows the Microsoft logo as a decorative icon in the button icon slot', () => {
      const logo = nativeButton().querySelector('svg.login-logo')!;
      expect(logo).not.toBeNull();
      expect(logo.hasAttribute('matButtonIcon')).toBe(true);
      expect(logo.getAttribute('aria-hidden')).toBe('true');
      expect(logo.getAttribute('focusable')).toBe('false');
    });

    it('shows no alert and an empty status before a sign-in attempt', () => {
      expect(alert()).toBeNull();
      expect(status().textContent?.trim()).toBe('');
      expect(status().classList).toContain('cdk-visually-hidden');
    });
  });

  describe('starting sign-in', () => {
    it('starts the Microsoft redirect when the button is clicked', async () => {
      await (await signInButton()).click();

      expect(login).toHaveBeenCalledTimes(1);
      expect(alert()).toBeNull();
    });

    it('marks the button disabled and busy but keeps keyboard focus on it, swaps the logo for a spinner and announces the status', async () => {
      // The redirect never settles here: on success the page navigates away.
      login.mockReturnValue(new Promise<void>(() => undefined));
      await focusAndClick();

      // Focusable disabled state: a native `disabled` attribute would drop keyboard focus to <body>.
      expect(await (await signInButton()).isDisabled()).toBe(true);
      expect(nativeButton().hasAttribute('disabled')).toBe(false);
      expect(nativeButton().getAttribute('aria-disabled')).toBe('true');
      expect(document.activeElement).toBe(nativeButton());

      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(1);
      // The spinner takes the logo's place in the leading icon slot.
      const spinner = nativeButton().querySelector('mat-progress-spinner')!;
      expect(spinner.hasAttribute('matButtonIcon')).toBe(true);
      expect(spinner.classList).toContain('login-button-icon');
      // A <button> may not contain a descendant with a tabindex attribute.
      expect(nativeButton().querySelectorAll('[tabindex]')).toHaveLength(0);
      expect(nativeButton().querySelector('svg.login-logo')).toBeNull();
      expect(nativeButton().getAttribute('aria-busy')).toBe('true');

      expect(status().textContent?.trim()).toBe('Signing in with Microsoft…');
      expect(status().closest('[aria-busy]')).toBeNull();
    });

    it('keeps the button label while signing in instead of an in-progress label', async () => {
      await (await signInButton()).click();
      await fixture.whenStable();

      expect(await (await signInButton()).getText()).toBe('Sign in with Microsoft');
    });

    it('ignores another attempt, including a click on the busy button, while the redirect is starting', async () => {
      login.mockReturnValue(new Promise<void>(() => undefined));
      fixture.componentInstance.onMicrosoftLogin();
      fixture.componentInstance.onMicrosoftLogin();
      await settle();

      // The busy button isn't natively disabled, so the click reaches the handler.
      await (await signInButton()).click();
      await settle();

      expect(login).toHaveBeenCalledTimes(1);
    });
  });

  describe('when the redirect fails to start', () => {
    beforeEach(() => {
      // MSAL's loginRedirect() is async: every failure arrives as a rejection.
      login.mockRejectedValueOnce(new Error('interaction_in_progress'));
    });

    it('shows an alert that says what happened and how to recover', async () => {
      await focusAndClick();

      expect(alert()?.textContent?.trim()).toBe(START_FAILED);
    });

    it('restores the idle state and leaves focus on the button so the person can try again', async () => {
      await focusAndClick();

      expect(await (await signInButton()).isDisabled()).toBe(false);
      expect(nativeButton().hasAttribute('aria-disabled')).toBe(false);
      expect(document.activeElement).toBe(nativeButton());
      expect(await loader.getAllHarnesses(MatProgressSpinnerHarness)).toHaveLength(0);
      expect(nativeButton().querySelector('svg.login-logo')).not.toBeNull();
      expect(nativeButton().hasAttribute('aria-busy')).toBe(false);
      expect(status().textContent?.trim()).toBe('');
    });

    it('clears the alert when a new attempt starts', async () => {
      await focusAndClick();
      expect(alert()).not.toBeNull();

      await (await signInButton()).click();
      await settle();

      expect(login).toHaveBeenCalledTimes(2);
      expect(alert()).toBeNull();
    });
  });

  describe('when the service throws before returning a promise', () => {
    it('still reports the failure and ends the busy state', async () => {
      login.mockImplementationOnce(() => {
        throw new Error('MSAL not initialized');
      });

      await focusAndClick();

      expect(alert()?.textContent?.trim()).toBe(START_FAILED);
      expect(await (await signInButton()).isDisabled()).toBe(false);
    });
  });
});
