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
    path: '',
    loadComponent: () => import('./layout/shell/shell').then((m) => m.Shell),
    canActivate: [authGuard, consentGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'log',
        loadComponent: () => import('./features/log/log-shell/log-shell').then((m) => m.LogShell),
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'meal' },
          { path: 'meal', loadComponent: () => import('./features/log/meal/meal').then((m) => m.LogMeal) },
          { path: 'lab', loadComponent: () => import('./features/log/lab/lab').then((m) => m.LogLab) },
          { path: 'activity', loadComponent: () => import('./features/log/activity/activity').then((m) => m.LogActivity) },
        ],
      },
      {
        path: 'analysis',
        loadComponent: () => import('./features/analysis/analysis').then((m) => m.Analysis),
      },
      {
        path: 'ask',
        loadComponent: () => import('./features/ask/ask').then((m) => m.Ask),
      },
      {
        path: 'about',
        loadComponent: () => import('./features/about/about').then((m) => m.About),
      },
      {
        path: 'profile',
        loadComponent: () => import('./features/profile/profile').then((m) => m.Profile),
      },
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
    ],
  },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: '**', redirectTo: 'login' },
];
