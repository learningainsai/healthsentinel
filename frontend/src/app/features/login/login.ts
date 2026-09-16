import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormField, form, required, submit } from '@angular/forms/signals';
import { Auth } from '../../core/auth';
import { Consent } from '../../core/consent';

@Component({
  imports: [FormField],
  selector: 'app-login',
  styleUrl: './login.scss',
  templateUrl: './login.html',
})
export class Login {
  private readonly auth = inject(Auth);
  private readonly consent = inject(Consent);
  private readonly router = inject(Router);

  protected readonly demoAccounts = this.auth.demoAccounts;
  protected readonly errorMessage = signal('');

  protected readonly credentials = signal({ username: '', password: '' });
  protected readonly loginForm = form(this.credentials, (p) => {
    required(p.username, { message: 'Username is required' });
    required(p.password, { message: 'Password is required' });
  });

  protected onSubmit(): void {
    submit(this.loginForm, async () => {
      const { username, password } = this.credentials();
      if (!this.auth.login(username, password)) {
        this.errorMessage.set('Invalid username or password — try one of the test credentials below.');
        return;
      }
      this.errorMessage.set('');
      const destination = this.consent.hasConsented(this.auth.currentUsername()) ? '/home' : '/consent';
      this.router.navigateByUrl(destination);
    });
  }

  protected fillDemoAccount(username: string): void {
    this.credentials.set({ username, password: 'HealthSentinel!1' });
    this.errorMessage.set('');
  }
}

