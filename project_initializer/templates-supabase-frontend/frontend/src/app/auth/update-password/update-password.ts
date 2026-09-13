import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  computed,
  ElementRef,
  inject,
  Injector,
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
import { MatButton } from '@angular/material/button';
import {
  MatCard,
  MatCardContent,
  MatCardHeader,
  MatCardSubtitle,
  MatCardTitle,
} from '@angular/material/card';
import { ErrorStateMatcher } from '@angular/material/core';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressSpinner } from '@angular/material/progress-spinner';
import { RouterLink } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';
import { AuthService } from '../../services/auth';
import { MIN_PASSWORD_LENGTH } from '../password-rules';

/** Shown when the update fails without an error message of its own. */
const UPDATE_FAILED_MESSAGE = "Couldn't update your password. Try again.";

/** Flags the group once a confirmation is typed that differs from the new password. */
const passwordsMatch: ValidatorFn = (group: AbstractControl): ValidationErrors | null => {
  const password = group.get('password')?.value;
  const confirmPassword = group.get('confirmPassword')?.value;
  return confirmPassword && password !== confirmPassword ? { passwordMismatch: true } : null;
};

@Component({
  selector: 'app-update-password',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    LucideAngularModule,
    MatButton,
    MatCard,
    MatCardContent,
    MatCardHeader,
    MatCardSubtitle,
    MatCardTitle,
    MatError,
    MatFormField,
    MatHint,
    MatInput,
    MatLabel,
    MatProgressSpinner,
  ],
  templateUrl: './update-password.html',
  styleUrl: './update-password.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UpdatePasswordComponent {
  private readonly authService = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  private readonly injector = inject(Injector);

  private readonly passwordInput = viewChild<ElementRef<HTMLInputElement>>('passwordInput');
  private readonly confirmPasswordInput =
    viewChild<ElementRef<HTMLInputElement>>('confirmPasswordInput');
  private readonly successHeading = viewChild<ElementRef<HTMLElement>>('successHeading');

  readonly minPasswordLength = MIN_PASSWORD_LENGTH;

  form = this.fb.nonNullable.group(
    {
      password: ['', [Validators.required, Validators.minLength(MIN_PASSWORD_LENGTH)]],
      confirmPassword: ['', Validators.required],
    },
    { validators: passwordsMatch },
  );

  isLoading = signal(false);
  errorMessage = signal('');
  updated = signal(false);
  noRecoverySession = signal(false);

  /** The account being changed, so password managers save the new password under it. */
  readonly accountEmail = computed(() => this.authService.currentUser()?.email ?? '');

  /**
   * Material's default timing (after a blur or a submit), plus the group's mismatch error. The new
   * password field uses Material's default matcher. A failed request never marks either field
   * invalid: it has no field message, and the alert carries it.
   */
  readonly confirmPasswordErrorMatcher: ErrorStateMatcher = {
    isErrorState: (control: AbstractControl | null, form: FormGroupDirective | NgForm | null) =>
      (!!control?.invalid || this.form.hasError('passwordMismatch')) &&
      !!(control?.touched || form?.submitted),
  };

  constructor() {
    this.authService.waitUntilInitialized().then(() => {
      if (!this.authService.isPasswordRecovery() && !this.authService.isAuthenticated()) {
        this.noRecoverySession.set(true);
      }
    });
  }

  async onSubmit(): Promise<void> {
    // The busy submit button stays focusable (disabledInteractive), so a click or Enter in a
    // field still submits the form: ignore it until the request settles.
    if (this.isLoading()) return;

    if (this.form.invalid) {
      // The submit button stays enabled so Enter and click can reveal what's missing.
      this.form.markAllAsTouched();
      this.focusFirstInvalidField();
      return;
    }

    const { password } = this.form.getRawValue();

    this.isLoading.set(true);
    this.errorMessage.set('');

    const result = await this.authService.updatePassword(password);

    this.isLoading.set(false);

    if (result.success) {
      this.updated.set(true);
      // The form (and the focused button) is gone; move focus to the confirmation heading so it's
      // read. The view never navigates on its own (WCAG 2.2.1): the link after the heading opens
      // the app when the user is ready.
      afterNextRender(() => this.successHeading()?.nativeElement.focus(), {
        injector: this.injector,
      });
    } else {
      // Focus stays on the submit button, ready for another attempt; the alert announces the error.
      this.errorMessage.set(result.message || UPDATE_FAILED_MESSAGE);
    }
  }

  private focusFirstInvalidField(): void {
    const target = this.form.controls.password.invalid
      ? this.passwordInput()
      : this.confirmPasswordInput();
    target?.nativeElement.focus();
  }
}
