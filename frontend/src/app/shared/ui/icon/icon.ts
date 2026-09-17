import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export type IconName = 'meal' | 'lab' | 'activity' | 'analysis' | 'chat' | 'queue' | 'clock' | 'arrow-right';

// Small, consistent Lucide-style line-icon set (24x24, single stroke) used in
// place of emoji across the dashboard — emoji render inconsistently across
// platforms and read as unpolished next to real photography.
const PATHS: Record<IconName, string> = {
  meal: 'M7 3v7a2 2 0 0 0 2 2h0a2 2 0 0 0 2-2V3M7 3v18M11 3v7M17 3c-1.7 0-3 2.2-3 5s1.3 5 3 5v10',
  lab: 'M9 3h6M10 3v6.5L5.5 18a2 2 0 0 0 1.8 3h9.4a2 2 0 0 0 1.8-3L14 9.5V3M8 14h8',
  activity: 'M13 3 4 14h7l-1 7 9-11h-7l1-7Z',
  analysis: 'M4 19h16M7 16V9M12 16V5M17 16v-6',
  chat: 'M21 12a8 8 0 1 1-3.4-6.5M21 4v5h-5',
  queue: 'M4 6h16M4 12h16M4 18h10',
  clock: 'M12 7v5l3 3M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  'arrow-right': 'M5 12h14M13 6l6 6-6 6',
};

// Host is styled to fill whatever size classes the caller puts on <app-icon>
// (e.g. class="h-5 w-5") — the inner svg fills the host in turn, since Tailwind
// classes on a custom element only reach the host, not its template content.
@Component({
  selector: 'app-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { style: 'display: inline-flex' },
  template: `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-full w-full">
      <path [attr.d]="path()" />
    </svg>
  `,
})
export class Icon {
  readonly name = input.required<IconName>();
  protected path(): string {
    return PATHS[this.name()];
  }
}
