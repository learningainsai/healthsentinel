import { Injectable, signal } from '@angular/core';

export type StagedKind = 'meal' | 'lab' | 'activity';

export interface StagedItem {
  id: string;
  kind: StagedKind;
  label: string;
  detail?: string;
  addedAt: Date;
}

export interface AddMealInput {
  text: string;
  photoName?: string;
}

export interface AddActivityInput {
  type: string;
  amount: string;
  occurredAt: string;
  notes?: string;
}

// Shared staging queue for everything a user logs (meal / lab / activity)
// before an explicit "Run Analysis" submits it through the pipeline. Kept as
// a single injectable signal so state survives navigation between the Log
// Data sub-tabs and the Run Analysis screen.
@Injectable({ providedIn: 'root' })
export class Staging {
  private readonly _items = signal<StagedItem[]>([]);
  private readonly _lastRunAt = signal<Date | null>(null);

  readonly items = this._items.asReadonly();
  readonly lastRunAt = this._lastRunAt.asReadonly();

  addMeal(input: AddMealInput): void {
    if (!input.text.trim() && !input.photoName) return;
    const label = input.text.trim() || input.photoName || 'Meal photo';
    const detail = input.photoName && input.text.trim() ? `Photo: ${input.photoName}` : undefined;
    this.push({ kind: 'meal', label, detail });
  }

  addLabFile(fileName: string): void {
    this.push({ kind: 'lab', label: fileName });
  }

  addActivity(input: AddActivityInput): void {
    const when = input.occurredAt ? new Date(input.occurredAt) : new Date();
    const label = `${input.type} · ${input.amount}`;
    this.push({ kind: 'activity', label, detail: input.notes || when.toLocaleString() });
  }

  remove(id: string): void {
    this._items.set(this._items().filter((item) => item.id !== id));
  }

  clear(): void {
    this._items.set([]);
  }

  markRun(): void {
    this._lastRunAt.set(new Date());
  }

  private push(item: Omit<StagedItem, 'id' | 'addedAt'>): void {
    this._items.set([...this._items(), { ...item, id: crypto.randomUUID(), addedAt: new Date() }]);
  }
}
