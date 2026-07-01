import { Component, signal, inject, ChangeDetectionStrategy } from '@angular/core';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  imports: [],
  templateUrl: './login.html',
  styleUrl: './login.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginComponent {
  private readonly authService = inject(AuthService);

  readonly isLoading = signal(false);
  readonly errorMessage = signal('');

  onMicrosoftLogin(): void {
    if (this.isLoading()) return;
    this.isLoading.set(true);
    this.errorMessage.set('');
    try {
      this.authService.login();
    } catch {
      this.errorMessage.set('Failed to start sign in.');
      this.isLoading.set(false);
    }
  }
}
