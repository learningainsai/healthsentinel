import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormField, form, submit, validate } from '@angular/forms/signals';
import { Auth } from '../../core/auth';
import { Consent as ConsentService, defaultConsentState } from '../../core/consent';
import { NavBar } from '../../shared/nav-bar/nav-bar';

@Component({
  imports: [FormField, NavBar],
  selector: 'app-consent',
  styleUrl: './consent.scss',
  templateUrl: './consent.html',
})
export class Consent {
  private readonly auth = inject(Auth);
  private readonly consentService = inject(ConsentService);
  private readonly router = inject(Router);

  protected readonly account = this.auth.currentAccount;

  protected readonly model = signal(defaultConsentState());
  protected readonly consentForm = form(this.model, (p) => {
    validate(p.tier1Image, ({ value }) =>
      value() ? undefined : { kind: 'required', message: 'Required to continue' },
    );
    validate(p.tier1NotMedical, ({ value }) =>
      value() ? undefined : { kind: 'required', message: 'Required to continue' },
    );
  });

  protected onSubmit(): void {
    submit(this.consentForm, async () => {
      const username = this.auth.currentUsername();
      if (!username) return;
      this.consentService.save(username, {
        ...this.model(),
        acceptedAt: new Date().toISOString(),
      });
      this.router.navigateByUrl('/home');
    });
  }
}

