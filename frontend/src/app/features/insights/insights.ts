import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Auth } from '../../core/auth';
import { HEALTH_METRICS, HealthMetric, metricTone } from '../../core/health-metrics';
import { Badge } from '../../shared/ui/badge/badge';

const CHART_WIDTH = 240;
const CHART_HEIGHT = 64;

// Line color per verdict, independent of the Badge palette since an SVG
// stroke needs a literal color, not a Tailwind class.
const LINE_COLOR: Record<HealthMetric['verdict'], string> = {
  worsening: '#dc2626',
  improving: '#059669',
  stable: '#64748b',
};

@Component({
  imports: [Badge, RouterLink],
  selector: 'app-insights',
  templateUrl: './insights.html',
})
export class Insights {
  private readonly auth = inject(Auth);

  protected readonly account = this.auth.currentAccount;
  protected readonly metrics = computed(() => HEALTH_METRICS[this.auth.currentUsername() ?? ''] ?? HEALTH_METRICS['demo-user']);
  protected readonly metricTone = metricTone;
  protected readonly chartWidth = CHART_WIDTH;
  protected readonly chartHeight = CHART_HEIGHT;

  /** Builds an SVG polyline `points` attribute from a metric's illustrative series. */
  protected linePoints(series: number[]): string {
    if (series.length < 2) return '';
    const min = Math.min(...series);
    const max = Math.max(...series);
    const range = max - min || 1;
    const step = CHART_WIDTH / (series.length - 1);
    const pad = 6;
    return series
      .map((v, i) => {
        const x = i * step;
        const y = pad + (1 - (v - min) / range) * (CHART_HEIGHT - pad * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }

  protected lineColor(verdict: HealthMetric['verdict']): string {
    return LINE_COLOR[verdict];
  }
}
