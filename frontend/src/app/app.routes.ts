import { Routes } from '@angular/router';
import { authGuard } from './core/auth-guard';
import { consentGuard } from './core/consent-guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/login/login').then((m) => m.Login),
  },
  {
    path: 'consent',
    loadComponent: () => import('./features/consent/consent').then((m) => m.Consent),
    canActivate: [authGuard],
  },
  {
    path: 'home',
    loadComponent: () => import('./features/home/home').then((m) => m.Home),
    canActivate: [authGuard, consentGuard],
  },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: '**', redirectTo: 'login' },
];

