import { Component, signal, inject, ChangeDetectionStrategy } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { AuthService, AuthResponse } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);

  form = this.fb.nonNullable.group({
    token: ['', Validators.required],
  });

  isLoading = signal(false);
  errorMessage = signal('');

  private returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/';

  onSubmit(): void {
    if (this.isLoading() || this.form.invalid) return;

    this.isLoading.set(true);
    this.errorMessage.set('');

    this.authService.login(this.form.getRawValue().token.trim()).subscribe({
      next: (response: AuthResponse) => {
        this.isLoading.set(false);
        if (response.authenticated) {
          this.router.navigate([this.returnUrl], { replaceUrl: true });
        } else {
          this.errorMessage.set(response.message || 'Authentication failed');
        }
      },
      error: (error) => {
        this.isLoading.set(false);
        this.errorMessage.set(error?.message || 'An unexpected error occurred');
      },
    });
  }
}
