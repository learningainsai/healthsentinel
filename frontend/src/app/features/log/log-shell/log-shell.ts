import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { assertSafeForLlm } from '../../../core/prompt-safety';
import { Staging } from '../../../core/staging';

const SUB_TABS = [
  { path: '/log/meal', icon: '🍽️', label: 'Meal' },
  { path: '/log/lab', icon: '🧪', label: 'Lab report' },
  { path: '/log/activity', icon: '🏃', label: 'Activity' },
];

// Segmented sub-nav for the three logging modes, plus a queue panel that
// stays visible across all three (backed by the shared Staging service) so
// switching tabs never loses what's already been staged. Every newly staged
// entry shows its mock analysis here immediately for review -- it must be
// confirmed (edits are prompt-injection scanned) before Run Analysis will
// use it.
@Component({
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  selector: 'app-log-shell',
  templateUrl: './log-shell.html',
})
export class LogShell {
  private readonly staging = inject(Staging);

  protected readonly subTabs = SUB_TABS;
  protected readonly items = this.staging.items;

  protected readonly drafts = signal<Record<string, string>>({});
  protected readonly errors = signal<Record<string, string>>({});

  protected remove(id: string): void {
    this.staging.remove(id);
  }

  protected reopen(id: string, currentText: string): void {
    this.staging.reopenForReview(id);
    this.drafts.set({ ...this.drafts(), [id]: currentText });
  }

  protected draftFor(item: { id: string; analysis: string }): string {
    return this.drafts()[item.id] ?? item.analysis;
  }

  protected setDraft(id: string, text: string): void {
    this.drafts.set({ ...this.drafts(), [id]: text });
  }

  protected confirm(id: string): void {
    const text = this.draftFor({ id, analysis: '' });
    const check = assertSafeForLlm(text);
    if (!check.safe) {
      this.errors.set({ ...this.errors(), [id]: check.issues.join('; ') });
      return;
    }
    const nextErrors = { ...this.errors() };
    delete nextErrors[id];
    this.errors.set(nextErrors);
    this.staging.confirmAnalysis(id, check.cleanText);
  }

  protected kindIcon(kind: string): string {
    return kind === 'meal' ? '🍽️' : kind === 'lab' ? '🧪' : '🏃';
  }
}

