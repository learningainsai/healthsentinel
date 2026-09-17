import { Component, inject, signal } from '@angular/core';
import { Staging } from '../../../core/staging';

type ActivityType = 'Workout' | 'Steps' | 'Sleep' | 'Travel';

const ACTIVITY_TYPES: ActivityType[] = ['Workout', 'Steps', 'Sleep', 'Travel'];

const AMOUNT_PLACEHOLDER: Record<ActivityType, string> = {
  Workout: 'e.g. 45 min, strength training',
  Steps: 'e.g. 8,200 steps',
  Sleep: 'e.g. 6.5 hours',
  Travel: 'e.g. Flight SFO → AUS, 4h',
};

// New: previously the backend's simulated Activity / SMS / Calendar
// connectors had no way to receive user-entered data at all — this closes
// that gap with a simple structured form (workout, steps, sleep, travel).
function toDatetimeLocal(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

@Component({
  selector: 'app-log-activity',
  templateUrl: './activity.html',
})
export class LogActivity {
  private readonly staging = inject(Staging);

  protected readonly types = ACTIVITY_TYPES;
  protected readonly amountPlaceholder = AMOUNT_PLACEHOLDER;

  protected readonly type = signal<ActivityType>('Workout');
  protected readonly amount = signal('');
  protected readonly occurredAt = signal(toDatetimeLocal(new Date()));
  protected readonly notes = signal('');

  protected addActivity(): void {
    const amount = this.amount().trim();
    if (!amount) return;

    this.staging.addActivity({
      type: this.type(),
      amount,
      occurredAt: this.occurredAt(),
      notes: this.notes().trim() || undefined,
    });

    this.amount.set('');
    this.notes.set('');
  }
}
