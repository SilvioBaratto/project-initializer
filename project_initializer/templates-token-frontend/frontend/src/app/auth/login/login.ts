import {
  ChangeDetectionStrategy,
  Component,
  DOCUMENT,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  FormGroupDirective,
  NgForm,
  ReactiveFormsModule,
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
import { MatError, MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressSpinner } from '@angular/material/progress-spinner';
import { ActivatedRoute, Router } from '@angular/router';
import {
  AuthResponse,
  AuthService,
  SIGN_IN_FAILURE_MESSAGES,
  SignInFailure,
  signInFailureFromError,
} from '../../services/auth';

@Component({
  selector: 'app-login',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatCard,
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
  templateUrl: './login.html',
  styleUrl: './login.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);
  private readonly document = inject(DOCUMENT);

  private readonly tokenInput = viewChild.required<ElementRef<HTMLInputElement>>('tokenInput');

  form = this.fb.nonNullable.group({
    token: ['', Validators.required],
  });

  isLoading = signal(false);
  errorMessage = signal('');

  /**
   * True while the alert says the token itself was rejected. Other failures (the server can't be
   * reached, too many attempts) aren't about the field, so they don't flag it.
   */
  readonly tokenRejected = signal(false);

  /**
   * The token field shows its error state after an invalid submit or blur (Material's default),
   * and also while the API's rejection is on screen, so the field and the alert agree.
   */
  readonly tokenErrorMatcher: ErrorStateMatcher = {
    isErrorState: (control: AbstractControl | null, form: FormGroupDirective | NgForm | null) =>
      this.tokenRejected() || !!(control?.invalid && (control.touched || form?.submitted)),
  };

  private returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/';

  constructor() {
    // A failure describes the attempt with the token that was sent. Once the token is edited,
    // the alert and the field's invalid state no longer apply, so both clear until the next submit.
    this.form.controls.token.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.clearError());
  }

  onSubmit(): void {
    // The busy submit button stays focusable (disabledInteractive), so a click or Enter in the
    // field still submits the form: ignore it until the request settles.
    if (this.isLoading()) return;

    if (this.form.invalid) {
      // The submit button stays enabled so Enter and click can reveal what's missing.
      this.form.markAllAsTouched();
      this.tokenInput().nativeElement.focus();
      return;
    }

    this.isLoading.set(true);
    this.clearError();

    this.authService.login(this.form.getRawValue().token.trim()).subscribe({
      next: (response: AuthResponse) => {
        this.isLoading.set(false);
        if (response.authenticated) {
          this.router.navigate([this.returnUrl], { replaceUrl: true });
        } else {
          // A rejection without a failure kind is still a rejected token.
          this.showError(response.failure ?? 'invalid-token');
        }
      },
      // AuthService.login() doesn't error, but a failure here must not surface a raw message.
      error: (error: unknown) => {
        this.isLoading.set(false);
        this.showError(signInFailureFromError(error));
      },
    });
  }

  private clearError(): void {
    this.errorMessage.set('');
    this.tokenRejected.set(false);
  }

  /** The copy always comes from SIGN_IN_FAILURE_MESSAGES, never from the API or the transport. */
  private showError(failure: SignInFailure): void {
    this.errorMessage.set(SIGN_IN_FAILURE_MESSAGES[failure]);
    this.tokenRejected.set(failure === 'invalid-token');
    // The busy submit button keeps keyboard focus (disabledInteractive), so focus normally stays
    // on it for another attempt. If focus was lost anyway, put it on the field to correct.
    const active = this.document.activeElement;
    if (!active || active === this.document.body) {
      this.tokenInput().nativeElement.focus();
    }
  }
}
