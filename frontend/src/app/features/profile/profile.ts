import { Component, computed, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Auth } from '../../core/auth';
import { Consent } from '../../core/consent';

@Component({
  imports: [DatePipe, RouterLink],
  selector: 'app-profile',
  templateUrl: './profile.html',
})
export class Profile {
  private readonly auth = inject(Auth);
  private readonly consentService = inject(Consent);

  protected readonly account = this.auth.currentAccount;
  protected readonly consentState = computed(() => this.consentService.stateFor(this.auth.currentUsername()));
}
