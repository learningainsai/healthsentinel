import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export type BadgeTone = 'sky' | 'violet' | 'indigo' | 'amber' | 'slate' | 'emerald' | 'red';

const TONE_CLASSES: Record<BadgeTone, string> = {
  sky: 'bg-sky-100 text-sky-700',
  violet: 'bg-violet-100 text-violet-700',
  indigo: 'bg-indigo-100 text-indigo-700',
  amber: 'bg-amber-100 text-amber-700',
  slate: 'bg-slate-100 text-slate-600',
  emerald: 'bg-emerald-100 text-emerald-700',
  red: 'bg-red-100 text-red-700',
};

// Small presentational pill used across About App (pipeline stage kind),
// Run Analysis (trend verdict) and Profile (consent status) so tone/style
// stays consistent instead of each feature re-deriving Tailwind classes.
@Component({
  selector: 'app-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="rounded-full px-2 py-0.5 text-xs font-medium" [class]="toneClass()"><ng-content /></span>`,
})
export class Badge {
  readonly tone = input<BadgeTone>('slate');
  protected toneClass(): string {
    return TONE_CLASSES[this.tone()];
  }
}
