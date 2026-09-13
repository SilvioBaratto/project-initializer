import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MatCard,
  MatCardContent,
  MatCardHeader,
  MatCardSubtitle,
  MatCardTitle,
} from '@angular/material/card';
import { MatProgressSpinner } from '@angular/material/progress-spinner';
import { AuthService } from '../../core/services/auth.service';

/** Shown when the Microsoft sign-in redirect can't start. */
const START_FAILED_MESSAGE = "Couldn't start sign-in with Microsoft. Try again.";

@Component({
  selector: 'app-login',
  imports: [
    MatButton,
    MatCard,
    MatCardContent,
    MatCardHeader,
    MatCardSubtitle,
    MatCardTitle,
    MatProgressSpinner,
  ],
  templateUrl: './login.html',
  styleUrl: './login.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginComponent {
  private readonly authService = inject(AuthService);

  readonly isLoading = signal(false);
  readonly errorMessage = signal('');

  /**
   * Starts the MSAL redirect. The page navigates away on success, so loading never resets then.
   * MSAL's loginRedirect() is async and reports every failure (interaction_in_progress, an
   * uninitialized client) as a rejection, so the call is awaited: a synchronous try/catch would
   * never see it and the button would stay busy.
   */
  async onMicrosoftLogin(): Promise<void> {
    if (this.isLoading()) return;
    this.isLoading.set(true);
    this.errorMessage.set('');
    try {
      await this.authService.login();
    } catch {
      this.errorMessage.set(START_FAILED_MESSAGE);
      this.isLoading.set(false);
    }
  }
}
