import { Service, computed, signal } from '@angular/core';

export interface DemoAccount {
  username: string;
  password: string;
  displayName: string;
  conditions: string[];
  allergies: string[];
  summary: string;
}

// Seeded demo identities mirroring the profiles in the Streamlit app (data/medical_docs/*).
export const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    username: 'demo-user',
    password: 'HealthSentinel!1',
    displayName: 'Demo User',
    conditions: ['prediabetes'],
    allergies: ['peanuts'],
    summary: 'Prediabetes · Peanut allergy',
  },
  {
    username: 'healthy-baseline-user',
    password: 'HealthSentinel!1',
    displayName: 'Healthy Baseline User',
    conditions: [],
    allergies: [],
    summary: 'No known conditions or allergies',
  },
  {
    username: 'hypertension-user',
    password: 'HealthSentinel!1',
    displayName: 'Hypertension User',
    conditions: ['hypertension'],
    allergies: ['shellfish'],
    summary: 'Hypertension · Shellfish allergy',
  },
  {
    username: 'family-history-user',
    password: 'HealthSentinel!1',
    displayName: 'Family History User',
    conditions: [],
    allergies: [],
    summary: 'Family history of heart condition (patient is healthy)',
  },
];

const STORAGE_KEY = 'healthsentinel.auth.user';

@Service()
export class Auth {
  private readonly _currentUsername = signal<string | null>(this.restore());

  readonly currentUsername = this._currentUsername.asReadonly();
  readonly isAuthenticated = computed(() => this._currentUsername() !== null);
  readonly currentAccount = computed(() => this.accountFor(this._currentUsername()));
  readonly demoAccounts = DEMO_ACCOUNTS;

  login(username: string, password: string): boolean {
    const account = this.accountFor(username.trim().toLowerCase());
    if (!account || account.password !== password) {
      return false;
    }
    this._currentUsername.set(account.username);
    sessionStorage.setItem(STORAGE_KEY, account.username);
    return true;
  }

  logout(): void {
    this._currentUsername.set(null);
    sessionStorage.removeItem(STORAGE_KEY);
  }

  accountFor(username: string | null): DemoAccount | undefined {
    return DEMO_ACCOUNTS.find((account) => account.username === username);
  }

  private restore(): string | null {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(STORAGE_KEY);
  }
}
