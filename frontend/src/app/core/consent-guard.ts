import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth } from './auth';
import { Consent } from './consent';

export const consentGuard: CanActivateFn = () => {
  const auth = inject(Auth);
  const consent = inject(Consent);
  const router = inject(Router);
  return consent.hasConsented(auth.currentUsername()) ? true : router.parseUrl('/consent');
};
