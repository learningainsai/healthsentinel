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

// Simple line-icon paths (24x24 viewBox, Heroicons-style single stroke) so
// each activity type reads visually rather than as plain <select> text.
const TYPE_ICON_PATHS: Record<ActivityType, string> = {
  Workout: 'M6.5 6.5 3 10l4 4M17.5 6.5 21 10l-4 4M8 12h8M9 6.5h6M9 17.5h6',
  Steps: 'M9 4c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2Zm7 8c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2ZM7 10l1 6M17 18l1-6',
  Sleep: 'M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z',
  Travel: 'm2 16 20-7-7 20-2-9-9-2Z',
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
  protected readonly iconPaths = TYPE_ICON_PATHS;

  protected readonly type = signal<ActivityType>('Workout');
  protected readonly amount = signal('');
  protected readonly occurredAt = signal(toDatetimeLocal(new Date()));
  protected readonly notes = signal('');

  protected selectType(t: ActivityType): void {
    this.type.set(t);
  }

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
