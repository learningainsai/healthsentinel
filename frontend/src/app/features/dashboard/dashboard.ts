import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { Auth } from '../../core/auth';
import { Staging } from '../../core/staging';

interface QuickLink {
  path: string;
  icon: string;
  title: string;
  description: string;
}

const QUICK_LINKS: QuickLink[] = [
  { path: '/log/meal', icon: '🍽️', title: 'Log a meal', description: 'Attach a photo or describe what you ate today.' },
  { path: '/log/lab', icon: '🧪', title: 'Upload a lab report', description: 'Extract readings for glucose, lipids, and more.' },
  { path: '/log/activity', icon: '🏃', title: 'Record an activity', description: 'Workouts, steps, sleep, or travel plans.' },
  { path: '/analysis', icon: '📈', title: 'Run analysis', description: 'Submit your staged data through the pipeline.' },
  { path: '/ask', icon: '💬', title: 'Ask Health Sentinel', description: 'Describe a symptom and get contributing factors.' },
];

@Component({
  imports: [RouterLink, DatePipe],
  selector: 'app-dashboard',
  templateUrl: './dashboard.html',
})
export class Dashboard {
  private readonly auth = inject(Auth);
  private readonly staging = inject(Staging);

  protected readonly account = this.auth.currentAccount;
  protected readonly quickLinks = QUICK_LINKS;
  protected readonly queueCount = computed(() => this.staging.items().length);
  protected readonly lastRunAt = this.staging.lastRunAt;
}
