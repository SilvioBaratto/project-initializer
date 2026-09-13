import {
  ChangeDetectionStrategy,
  Component,
  computed,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  FormGroupDirective,
  NgForm,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { ErrorStateMatcher } from '@angular/material/core';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { AuthService } from '../../services/auth';
import { MIN_PASSWORD_LENGTH } from '../password-rules';

/** Shown after an account is created; Supabase emails the confirmation link. */
const SIGN_UP_CONFIRMATION_MESSAGE = 'Check your email to confirm your account';

/** Shown when sign-in fails without a message of its own. */
const SIGN_IN_FAILED_MESSAGE = "Couldn't sign you in. Try again.";

/** Shown when account creation fails without a message of its own. */
const SIGN_UP_FAILED_MESSAGE = "Couldn't create your account. Try again.";

/** Group-level mismatch, reported only once a confirmation has been typed (sign-up mode). */
const passwordsMatch: ValidatorFn = (group: AbstractControl): ValidationErrors | null => {
  const password = group.get('password')?.value;
  const confirmPassword = group.get('confirmPassword')?.value;
  return confirmPassword && password !== confirmPassword ? { passwordMismatch: true } : null;
};

/**
 * Supabase sign-in and account creation on one routed view (`/login`), rendered
 * outside the app shell.
 *
 * Material 3 structure: one `<main>` with a single `h1` (the card title), an
 * outlined `mat-card`, outlined text fields with `mat-error` messages, one filled
 * primary action (Sign in / Create account), an outlined Google action and text
 * buttons for the secondary links. The primary action stays enabled while the
 * form is invalid, so Enter and click reveal every missing value and move focus
 * to the first field to fix. While a request runs both actions report disabled
 * but stay focusable (`disabledInteractive`); only the one the user activated is
 * `aria-busy` and shows an indeterminate spinner in its icon slot (its label
 * never changes), and a visually hidden status region announces that request. Request failures render in a persistent `role="alert"`
 * region, confirmations in `role="status"`; validation errors, including a
 * password mismatch, stay on their fields.
 */
@Component({
  selector: 'app-login',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatInputModule,
    MatProgressSpinnerModule,
    LucideAngularModule,
  ],
  templateUrl: './login.html',
  styleUrl: './login.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);

  private readonly formDirective = viewChild(FormGroupDirective);
  private readonly emailInput = viewChild<ElementRef<HTMLInputElement>>('emailInput');
  private readonly passwordInput = viewChild<ElementRef<HTMLInputElement>>('passwordInput');
  private readonly confirmPasswordInput =
    viewChild<ElementRef<HTMLInputElement>>('confirmPasswordInput');

  readonly minPasswordLength = MIN_PASSWORD_LENGTH;

  form = this.fb.nonNullable.group(
    {
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(MIN_PASSWORD_LENGTH)]],
      confirmPassword: ['', Validators.required],
    },
    { validators: passwordsMatch },
  );

  mode = signal<'login' | 'signup'>('login');
  /** The request in progress, so only the action the user activated shows as busy. */
  readonly pending = signal<'email' | 'google' | null>(null);
  /** Any request in progress: both actions ignore activation until it settles. */
  readonly isLoading = computed(() => this.pending() !== null);
  errorMessage = signal('');
  successMessage = signal('');

  /** Material's default timing (after a blur or a submit), plus the group's mismatch error. */
  readonly confirmPasswordErrorMatcher: ErrorStateMatcher = {
    isErrorState: (control: AbstractControl | null, form: FormGroupDirective | NgForm | null) =>
      (!!control?.invalid || this.form.hasError('passwordMismatch')) &&
      !!(control?.touched || form?.submitted),
  };

  private returnUrl = this.sanitizeReturnUrl(
    this.route.snapshot.queryParams['returnUrl']
  );

  toggleMode() {
    const next = this.mode() === 'login' ? 'signup' : 'login';
    this.mode.set(next);
    this.errorMessage.set('');
    this.successMessage.set('');
    this.resetForm();
  }

  async onGoogleLogin(): Promise<void> {
    if (this.isLoading()) return;
    this.pending.set('google');
    this.errorMessage.set('');
    try {
      await this.authService.loginWithGoogle();
    } catch {
      this.errorMessage.set("Couldn't open Google sign-in. Try again.");
      this.pending.set(null);
    }
  }

  async onSubmit(): Promise<void> {
    // The busy primary action stays focusable (disabledInteractive), so a click or Enter in a
    // field still submits the form: ignore it until the request settles.
    if (this.isLoading()) return;

    const controls = this.form.controls;
    if (controls.email.invalid || controls.password.invalid) {
      // The primary action stays enabled so Enter and click can reveal what's missing.
      this.form.markAllAsTouched();
      const firstInvalid = controls.email.invalid ? this.emailInput() : this.passwordInput();
      firstInvalid?.nativeElement.focus();
      return;
    }

    if (this.mode() === 'signup') {
      const confirm = controls.confirmPassword;
      if (confirm.invalid || this.form.hasError('passwordMismatch')) {
        // The error shows on the confirmation field; move focus there so it can be fixed.
        confirm.markAsTouched();
        this.confirmPasswordInput()?.nativeElement.focus();
        return;
      }
    }

    const { email, password } = this.form.getRawValue();

    this.pending.set('email');
    this.errorMessage.set('');
    this.successMessage.set('');

    const trimmedEmail = email.trim();

    if (this.mode() === 'login') {
      const result = await this.authService.login(trimmedEmail, password.trim());
      this.pending.set(null);

      if (result.success) {
        this.router.navigate([this.returnUrl], { replaceUrl: true });
      } else {
        this.errorMessage.set(result.message || SIGN_IN_FAILED_MESSAGE);
      }
    } else {
      const result = await this.authService.signup(trimmedEmail, password.trim());
      this.pending.set(null);

      if (result.success) {
        // The view owns its confirmation copy, like the password reset screens.
        this.successMessage.set(SIGN_UP_CONFIRMATION_MESSAGE);
        this.resetForm({ email: this.form.controls.email.value, password: '', confirmPassword: '' });
      } else {
        this.errorMessage.set(result.message || SIGN_UP_FAILED_MESSAGE);
      }
    }
  }

  /**
   * Resets through the form directive so its `submitted` flag clears too; `FormGroup.reset()`
   * alone leaves it set, and every emptied required field would show its error at once.
   */
  private resetForm(value?: { email: string; password: string; confirmPassword: string }): void {
    const directive = this.formDirective();
    if (directive) {
      directive.resetForm(value);
    } else {
      this.form.reset(value);
    }
  }

  private sanitizeReturnUrl(url: string | undefined): string {
    if (!url) return '/';
    try {
      const parsed = this.router.parseUrl(url);
      const serialized = this.router.serializeUrl(parsed);
      return serialized.startsWith('/') ? serialized : '/';
    } catch {
      return '/';
    }
  }
}
