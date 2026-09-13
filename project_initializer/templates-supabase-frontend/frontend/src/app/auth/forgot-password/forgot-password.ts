import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  inject,
  Injector,
  signal,
  viewChild,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import {
  MatCard,
  MatCardActions,
  MatCardContent,
  MatCardHeader,
  MatCardSubtitle,
  MatCardTitle,
} from '@angular/material/card';
import { MatError, MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressSpinner } from '@angular/material/progress-spinner';
import { RouterLink } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';
import { AuthService } from '../../services/auth';

/** Shown when the reset request fails without an error message of its own. */
const UNEXPECTED_ERROR_MESSAGE = "Couldn't send the reset link. Try again.";

@Component({
  selector: 'app-forgot-password',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    LucideAngularModule,
    MatButton,
    MatCard,
    MatCardActions,
    MatCardContent,
    MatCardHeader,
    MatCardSubtitle,
    MatCardTitle,
    MatError,
    MatFormField,
    MatInput,
    MatLabel,
    MatProgressSpinner,
  ],
  templateUrl: './forgot-password.html',
  styleUrl: './forgot-password.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgotPasswordComponent {
  private readonly authService = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  private readonly injector = inject(Injector);

  private readonly emailInput = viewChild<ElementRef<HTMLInputElement>>('emailInput');
  private readonly sentHeading = viewChild<ElementRef<HTMLElement>>('sentHeading');

  form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  isLoading = signal(false);
  errorMessage = signal('');
  emailSent = signal(false);

  /** The address the reset link went to, repeated in the confirmation so a typo is easy to spot. */
  sentTo = signal('');

  async onSubmit(): Promise<void> {
    // The busy submit button stays focusable (disabledInteractive), so a click or Enter in the
    // field still submits the form: ignore it until the request settles.
    if (this.isLoading()) return;

    if (this.form.invalid) {
      // The submit button stays enabled so Enter and click can reveal what's missing.
      this.form.markAllAsTouched();
      this.emailInput()?.nativeElement.focus();
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set('');

    const email = this.form.getRawValue().email.trim();
    let result: { success: boolean; message: string };
    try {
      result = await this.authService.forgotPassword(email);
    } catch {
      result = { success: false, message: '' };
    }

    this.isLoading.set(false);

    if (result.success) {
      this.sentTo.set(email);
      this.emailSent.set(true);
      // The form, and the submit button that had focus, is replaced by the confirmation.
      // Move focus to its heading so keyboard and screen reader users land on the outcome.
      afterNextRender(() => this.sentHeading()?.nativeElement.focus(), {
        injector: this.injector,
      });
    } else {
      // Focus stays on the submit button, ready for another attempt; the alert announces the error.
      this.errorMessage.set(result.message || UNEXPECTED_ERROR_MESSAGE);
    }
  }
}
