import { Component, computed, inject, signal } from '@angular/core';
import { Auth } from '../../core/auth';
import { Staging } from '../../core/staging';
import { Badge, BadgeTone } from '../../shared/ui/badge/badge';

interface TrendMetric {
  metric: string;
  verdict: 'stable' | 'improving' | 'worsening';
  detail: string;
}

// Mocked per-profile trend verdicts — a real backend computes these
// deterministically in trend_agent from historic metrics_store readings.
// Moved here from the old monolithic home.ts: trends are an analysis
// *output*, not a logging action, so they belong on the Run Analysis screen.
const TREND_MOCKS: Record<string, TrendMetric[]> = {
  'demo-user': [
    { metric: 'Glucose', verdict: 'worsening', detail: 'Trending up over the last 90 days, now in the prediabetic range.' },
    { metric: 'Sleep', verdict: 'worsening', detail: 'Averaging under 6h/night for 2 of the last 3 weeks.' },
    { metric: 'Weight', verdict: 'stable', detail: 'Within ±2% over the trend window.' },
    { metric: 'Stress', verdict: 'worsening', detail: 'Meeting density up on most workdays this month.' },
  ],
  'hypertension-user': [
    { metric: 'Glucose', verdict: 'stable', detail: 'Consistently within normal range.' },
    { metric: 'Sleep', verdict: 'stable', detail: 'Averaging 6–7h/night, consistent with prior months.' },
    { metric: 'Weight', verdict: 'stable', detail: 'Within ±2% over the trend window.' },
    { metric: 'Stress', verdict: 'worsening', detail: 'Elevated meeting load flagged by the calendar connector.' },
  ],
  'healthy-baseline-user': [
    { metric: 'Glucose', verdict: 'stable', detail: 'Consistently within normal range.' },
    { metric: 'Sleep', verdict: 'improving', detail: 'Averaging 7.5h+/night, trending upward.' },
    { metric: 'Weight', verdict: 'stable', detail: 'Within ±2% over the trend window.' },
    { metric: 'Stress', verdict: 'stable', detail: 'No elevated signal detected.' },
  ],
  'family-history-user': [
    { metric: 'Glucose', verdict: 'stable', detail: 'Consistently within normal range.' },
    { metric: 'Sleep', verdict: 'stable', detail: 'Averaging 6.5–7h/night, consistent with prior months.' },
    { metric: 'Weight', verdict: 'stable', detail: 'Within ±2% over the trend window.' },
    { metric: 'Stress', verdict: 'stable', detail: 'No elevated signal detected.' },
  ],
};

@Component({
  imports: [Badge],
  selector: 'app-analysis',
  templateUrl: './analysis.html',
})
export class Analysis {
  private readonly auth = inject(Auth);
  private readonly staging = inject(Staging);

  protected readonly items = this.staging.items;
  protected readonly isRunning = signal(false);
  protected readonly hasRun = signal(false);
  protected readonly trends = computed(() => TREND_MOCKS[this.auth.currentUsername() ?? ''] ?? TREND_MOCKS['demo-user']);

  protected remove(id: string): void {
    this.staging.remove(id);
  }

  protected kindIcon(kind: string): string {
    return kind === 'meal' ? '🍽️' : kind === 'lab' ? '🧪' : '🏃';
  }

  protected runAnalysis(): void {
    if (this.items().length === 0 || this.isRunning()) return;
    this.isRunning.set(true);
    // Simulated pipeline latency (intake → nutrition/lab/activity agents →
    // trend agent → prediction/critic). A real backend would stream stage
    // progress instead of a flat delay.
    setTimeout(() => {
      this.isRunning.set(false);
      this.hasRun.set(true);
      this.staging.markRun();
      this.staging.clear();
    }, 1200);
  }

  protected trendTone(verdict: TrendMetric['verdict']): BadgeTone {
    switch (verdict) {
      case 'improving':
        return 'emerald';
      case 'worsening':
        return 'red';
      case 'stable':
        return 'slate';
    }
  }
}
