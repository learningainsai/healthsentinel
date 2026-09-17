import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Staging } from '../../../core/staging';

const SUB_TABS = [
  { path: '/log/meal', icon: '🍽️', label: 'Meal' },
  { path: '/log/lab', icon: '🧪', label: 'Lab report' },
  { path: '/log/activity', icon: '🏃', label: 'Activity' },
];

// Segmented sub-nav for the three logging modes, plus a queue panel that
// stays visible across all three (backed by the shared Staging service) so
// switching tabs never loses what's already been staged.
@Component({
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  selector: 'app-log-shell',
  templateUrl: './log-shell.html',
})
export class LogShell {
  private readonly staging = inject(Staging);

  protected readonly subTabs = SUB_TABS;
  protected readonly items = this.staging.items;

  protected remove(id: string): void {
    this.staging.remove(id);
  }

  protected kindIcon(kind: string): string {
    return kind === 'meal' ? '🍽️' : kind === 'lab' ? '🧪' : '🏃';
  }
}
