import { Component, computed, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Auth } from '../../core/auth';
import { CONDITION_CONTEXT, HEALTH_METRICS, buildHealthNarrative, metricTone } from '../../core/health-metrics';
import { Staging } from '../../core/staging';
import { Badge } from '../../shared/ui/badge/badge';
import { Icon, IconName } from '../../shared/ui/icon/icon';

type Accent = 'amber' | 'rose' | 'sky' | 'violet' | 'teal';

interface QuickLink {
  path: string;
  icon: IconName;
  accent: Accent;
  title: string;
  description: string;
  /** Tailwind col-span for the bento grid — bigger span = higher priority tile. */
  span: string;
}

// Tile size reflects priority, not just content volume (bento-grid pattern):
// Meal is the highest-frequency action and gets the large tile; Analysis and
// Ask are secondary and share a row. Each category gets its own accent color
// so the grid is scannable by color, the way WHOOP uses a fixed 3-color
// vocabulary for readiness state.
const QUICK_LINKS: QuickLink[] = [
  { path: '/log/meal', icon: 'meal', accent: 'amber', title: 'Log a meal', description: 'Attach a photo or describe what you ate today.', span: 'sm:col-span-2' },
  { path: '/log/lab', icon: 'lab', accent: 'rose', title: 'Upload a lab report', description: 'Extract readings for glucose, lipids, and more.', span: 'sm:col-span-1' },
  { path: '/log/activity', icon: 'activity', accent: 'sky', title: 'Record an activity', description: 'Workouts, steps, sleep, or travel plans.', span: 'sm:col-span-1' },
  { path: '/analysis', icon: 'analysis', accent: 'violet', title: 'Run analysis', description: 'Submit your staged data through the pipeline.', span: 'sm:col-span-2' },
  { path: '/ask', icon: 'chat', accent: 'teal', title: 'Ask Health Sentinel', description: 'Describe a symptom and get contributing factors.', span: 'sm:col-span-2' },
];

const ACCENT_CLASSES: Record<Accent, { tile: string; icon: string }> = {
  amber: { tile: 'border-amber-200 bg-amber-50/70 hover:border-amber-300', icon: 'bg-amber-500' },
  rose: { tile: 'border-rose-200 bg-rose-50/70 hover:border-rose-300', icon: 'bg-rose-500' },
  sky: { tile: 'border-sky-200 bg-sky-50/70 hover:border-sky-300', icon: 'bg-sky-500' },
  violet: { tile: 'border-violet-200 bg-violet-50/70 hover:border-violet-300', icon: 'bg-violet-500' },
  teal: { tile: 'border-teal-200 bg-teal-50/70 hover:border-teal-300', icon: 'bg-teal-600' },
};

@Component({
  imports: [RouterLink, DatePipe, Icon, Badge],
  selector: 'app-dashboard',
  templateUrl: './dashboard.html',
})
export class Dashboard {
  private readonly auth = inject(Auth);
  private readonly staging = inject(Staging);

  protected readonly account = this.auth.currentAccount;
  protected readonly quickLinks = QUICK_LINKS;
  protected readonly accentClasses = ACCENT_CLASSES;
  protected readonly queueCount = computed(() => this.staging.items().length);
  protected readonly lastRunAt = this.staging.lastRunAt;

  // Health trends summary: same mock metric data shown after Run Analysis
  // (core/health-metrics.ts), surfaced here as an always-visible home-page
  // snapshot of where the user stands vs. a healthy adult's expected range.
  protected readonly healthMetrics = computed(() => HEALTH_METRICS[this.auth.currentUsername() ?? ''] ?? HEALTH_METRICS['demo-user']);
  protected readonly healthNarrative = computed(() =>
    buildHealthNarrative(
      this.account()?.displayName ?? 'You',
      this.healthMetrics(),
      CONDITION_CONTEXT[this.auth.currentUsername() ?? ''],
    ),
  );
  protected readonly metricTone = metricTone;
}
