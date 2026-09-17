import { Injectable, computed, signal } from '@angular/core';

export type StagedKind = 'meal' | 'lab' | 'activity';

export interface StagedItem {
  id: string;
  kind: StagedKind;
  label: string;
  detail?: string;
  // Mock per-entry analysis shown to the user immediately after logging --
  // must be reviewed (and may be edited) before Run Analysis will use it.
  analysis: string;
  reviewed: boolean;
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

function summarizeMealAnalysis(label: string): string {
  return (
    `Meal nutrition summary — Calories: ~450 kcal, Protein: ~30g, Carbs: ~55g, Fat: ~12g, ` +
    `Fiber: ~6g, Magnesium: ~140mg (estimated from: "${label}")`
  );
}

function summarizeLabAnalysis(fileName: string): string {
  return (
    `Lab report summary (${fileName}) — Extracted readings: Glucose: 108 mg/dL, Iron: 65 \u00b5g/dL.\n` +
    `Doctor's final verdict (add your own note if reviewing this report): `
  );
}

function summarizeActivityAnalysis(type: string, amount: string): string {
  return `Activity summary — ${type}: ${amount}. Logged for sleep/steps/exercise trend analysis.`;
}

// Shared staging queue for everything a user logs (meal / lab / activity)
// before an explicit "Run Analysis" submits it through the pipeline. Kept as
// a single injectable signal so state survives navigation between the Log
// Data sub-tabs and the Run Analysis screen. Every entry gets an immediate
// mock analysis that the user must review/confirm (editable) -- Run
// Analysis only ever uses the confirmed text, never the raw draft.
@Injectable({ providedIn: 'root' })
export class Staging {
  private readonly _items = signal<StagedItem[]>([]);
  private readonly _lastRunAt = signal<Date | null>(null);

  readonly items = this._items.asReadonly();
  readonly lastRunAt = this._lastRunAt.asReadonly();
  readonly allReviewed = computed(() => this._items().every((item) => item.reviewed));

  addMeal(input: AddMealInput): void {
    if (!input.text.trim() && !input.photoName) return;
    const label = input.text.trim() || input.photoName || 'Meal photo';
    const detail = input.photoName && input.text.trim() ? `Photo: ${input.photoName}` : undefined;
    this.push({ kind: 'meal', label, detail, analysis: summarizeMealAnalysis(label), reviewed: false });
  }

  addLabFile(fileName: string): void {
    this.push({ kind: 'lab', label: fileName, analysis: summarizeLabAnalysis(fileName), reviewed: false });
  }

  addActivity(input: AddActivityInput): void {
    const when = input.occurredAt ? new Date(input.occurredAt) : new Date();
    const label = `${input.type} · ${input.amount}`;
    this.push({
      kind: 'activity',
      label,
      detail: input.notes || when.toLocaleString(),
      analysis: summarizeActivityAnalysis(input.type, input.amount),
      reviewed: false,
    });
  }

  remove(id: string): void {
    this._items.set(this._items().filter((item) => item.id !== id));
  }

  /** Locks in the (possibly edited) analysis text for one staged entry. */
  confirmAnalysis(id: string, text: string): void {
    this._items.set(this._items().map((item) => (item.id === id ? { ...item, analysis: text, reviewed: true } : item)));
  }

  /** Re-opens a confirmed entry for editing (e.g. the user wants to revise it). */
  reopenForReview(id: string): void {
    this._items.set(this._items().map((item) => (item.id === id ? { ...item, reviewed: false } : item)));
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

