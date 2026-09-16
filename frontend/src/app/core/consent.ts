import { Service, signal } from '@angular/core';

export interface ConsentState {
  tier1Image: boolean;
  tier1NotMedical: boolean;
  tier2MedicalDocs: boolean;
  tier2Iwatch: boolean;
  tier2Sms: boolean;
  tier2Calendar: boolean;
  tier3Analytics: boolean;
  tier4Notify: boolean;
  acceptedAt: string;
}

export function defaultConsentState(): ConsentState {
  return {
    tier1Image: false,
    tier1NotMedical: false,
    tier2MedicalDocs: true,
    tier2Iwatch: true,
    tier2Sms: true,
    tier2Calendar: true,
    tier3Analytics: false,
    tier4Notify: true,
    acceptedAt: '',
  };
}

const STORAGE_PREFIX = 'healthsentinel.consent.';

@Service()
export class Consent {
  private readonly _consentByUser = signal<Record<string, ConsentState>>(this.restoreAll());

  hasConsented(username: string | null): boolean {
    if (!username) return false;
    const state = this._consentByUser()[username];
    return !!state && state.tier1Image && state.tier1NotMedical;
  }

  stateFor(username: string | null): ConsentState | undefined {
    if (!username) return undefined;
    return this._consentByUser()[username];
  }

  save(username: string, state: ConsentState): void {
    this._consentByUser.set({ ...this._consentByUser(), [username]: state });
    sessionStorage.setItem(STORAGE_PREFIX + username, JSON.stringify(state));
  }

  private restoreAll(): Record<string, ConsentState> {
    const result: Record<string, ConsentState> = {};
    if (typeof sessionStorage === 'undefined') return result;
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (!key?.startsWith(STORAGE_PREFIX)) continue;
      const raw = sessionStorage.getItem(key);
      if (!raw) continue;
      try {
        result[key.slice(STORAGE_PREFIX.length)] = JSON.parse(raw);
      } catch {
        // ignore malformed entries
      }
    }
    return result;
  }
}
