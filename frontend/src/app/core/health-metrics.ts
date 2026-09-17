import { BadgeTone } from '../shared/ui/badge/badge';

export interface HealthMetric {
  metric: string;
  /** Latest observed value, formatted for display (e.g. "112 mg/dL (fasting)"). */
  current: string;
  /** The range/target a healthy adult is expected to sit within. */
  healthyRange: string;
  verdict: 'stable' | 'improving' | 'worsening';
  detail: string;
  /** Illustrative ~90-day sample series for the sparkline on the Insights page (not raw device readings). */
  series: number[];
  /** A concrete, actionable step for this specific parameter (shown on the Insights page). */
  recommendation: string;
}

// Mocked per-profile trend data — a real backend computes verdicts
// deterministically in trend_agent from historic metrics_store readings
// (see src/healthsentinel/trends.py) and current/healthyRange from the
// latest lab panel + config.py thresholds. Shared by the Dashboard (home
// page summary), Insights (graphical trend + recommendation view) and Run
// Analysis (post-pipeline trend list) so all three screens always agree.
export const HEALTH_METRICS: Record<string, HealthMetric[]> = {
  'demo-user': [
    {
      metric: 'Glucose',
      current: '112 mg/dL (fasting)',
      healthyRange: '70–99 mg/dL',
      verdict: 'worsening',
      detail: 'Trending up over the last 90 days, now in the prediabetic range (100–125 mg/dL).',
      series: [92, 96, 101, 105, 109, 112],
      recommendation: 'Cut back on refined carbs and sugary drinks, and add a 10–15 min walk after meals to blunt post-meal glucose spikes.',
    },
    {
      metric: 'Sleep',
      current: '5.6 h/night (avg)',
      healthyRange: '7–9 h/night',
      verdict: 'worsening',
      detail: 'Averaging under 6h/night for 2 of the last 3 weeks.',
      series: [6.8, 6.5, 6.1, 5.9, 5.7, 5.6],
      recommendation: 'Set a consistent lights-out time and avoid screens 30 min before bed to close the gap to 7h+.',
    },
    {
      metric: 'Weight',
      current: '78.4 kg',
      healthyRange: 'within ±2% of your 78.0 kg baseline',
      verdict: 'stable',
      detail: 'Within ±2% over the trend window.',
      series: [78.0, 78.2, 77.9, 78.3, 78.1, 78.4],
      recommendation: "You're within your stable range — no changes needed here.",
    },
    {
      metric: 'Stress',
      current: 'High meeting density',
      healthyRange: 'Low–moderate workday load',
      verdict: 'worsening',
      detail: 'Meeting density up on most workdays this month.',
      series: [3, 4, 5, 6, 7, 8],
      recommendation: 'Block 2–3 no-meeting focus windows per week and add a short mid-day walk to offset the elevated meeting load.',
    },
    {
      metric: 'Food pattern',
      current: 'Frequent high-glycemic snacks',
      healthyRange: 'Balanced meals, mostly whole foods & fiber',
      verdict: 'worsening',
      detail: 'Logged meals over the last 2 weeks skew toward refined carbs and low fiber — consistent with the glucose trend above.',
      series: [7, 6, 5, 5, 4, 3],
      recommendation: 'Swap afternoon snacks for nuts, fruit, or plain yogurt to add fiber and blunt glucose spikes.',
    },
  ],
  'hypertension-user': [
    {
      metric: 'Glucose',
      current: '92 mg/dL (fasting)',
      healthyRange: '70–99 mg/dL',
      verdict: 'stable',
      detail: 'Consistently within normal range.',
      series: [90, 91, 89, 93, 91, 92],
      recommendation: 'Maintain your current diet — glucose is well within range.',
    },
    {
      metric: 'Sleep',
      current: '6.4 h/night (avg)',
      healthyRange: '7–9 h/night',
      verdict: 'stable',
      detail: 'Averaging 6–7h/night, consistent with prior months.',
      series: [6.3, 6.5, 6.2, 6.6, 6.3, 6.4],
      recommendation: "You're at the low end of the healthy range — an extra 30–45 min of sleep would add more buffer.",
    },
    {
      metric: 'Weight',
      current: 'Within baseline',
      healthyRange: 'within ±2% of baseline',
      verdict: 'stable',
      detail: 'Within ±2% over the trend window.',
      series: [70.0, 70.2, 69.8, 70.1, 69.9, 70.0],
      recommendation: 'No changes needed — weight is stable.',
    },
    {
      metric: 'Stress',
      current: 'Elevated meeting load',
      healthyRange: 'Low–moderate workday load',
      verdict: 'worsening',
      detail: 'Elevated meeting load flagged by the calendar connector.',
      series: [3, 4, 5, 6, 7, 8],
      recommendation: 'Consolidate meetings where possible and protect a daily lunch break to lower your overall workday load.',
    },
    {
      metric: 'Food pattern',
      current: 'Frequent high-sodium takeout',
      healthyRange: 'Home-cooked, low-sodium meals (<2000mg/day)',
      verdict: 'worsening',
      detail: '3 of the last 7 logged meals were high-sodium takeout — above your physician-recommended sodium ceiling.',
      series: [7, 6, 6, 5, 4, 3],
      recommendation: 'Swap high-sodium takeout for home-cooked meals at least 3x/week to get under your 2000mg/day sodium ceiling.',
    },
  ],
  'healthy-baseline-user': [
    {
      metric: 'Glucose',
      current: '88 mg/dL (fasting)',
      healthyRange: '70–99 mg/dL',
      verdict: 'stable',
      detail: 'Consistently within normal range.',
      series: [86, 89, 87, 90, 88, 88],
      recommendation: 'Great — keep your current habits.',
    },
    {
      metric: 'Sleep',
      current: '7.6 h/night (avg)',
      healthyRange: '7–9 h/night',
      verdict: 'improving',
      detail: 'Averaging 7.5h+/night, trending upward.',
      series: [6.8, 7.0, 7.2, 7.4, 7.5, 7.6],
      recommendation: "Keep up the consistent sleep schedule that's driving this improvement.",
    },
    {
      metric: 'Weight',
      current: 'Within baseline',
      healthyRange: 'within ±2% of baseline',
      verdict: 'stable',
      detail: 'Within ±2% over the trend window.',
      series: [65.0, 65.2, 64.9, 65.1, 65.0, 65.0],
      recommendation: 'No changes needed — weight is stable.',
    },
    {
      metric: 'Stress',
      current: 'No elevated signal',
      healthyRange: 'Low–moderate workday load',
      verdict: 'stable',
      detail: 'No elevated signal detected.',
      series: [2, 2, 3, 2, 3, 2],
      recommendation: 'No elevated signal — keep your current workload balance.',
    },
    {
      metric: 'Food pattern',
      current: 'Balanced, whole-food meals',
      healthyRange: 'Balanced meals, mostly whole foods & fiber',
      verdict: 'improving',
      detail: 'Logged meals consistently include lean protein, vegetables, and whole grains.',
      series: [6, 7, 7, 8, 8, 9],
      recommendation: 'Keep favoring whole foods, lean protein and vegetables like you have been.',
    },
  ],
  'family-history-user': [
    {
      metric: 'Glucose',
      current: '91 mg/dL (fasting)',
      healthyRange: '70–99 mg/dL',
      verdict: 'stable',
      detail: 'Consistently within normal range.',
      series: [89, 90, 91, 90, 92, 91],
      recommendation: 'No changes needed — glucose is well within range.',
    },
    {
      metric: 'Sleep',
      current: '6.8 h/night (avg)',
      healthyRange: '7–9 h/night',
      verdict: 'stable',
      detail: 'Averaging 6.5–7h/night, consistent with prior months.',
      series: [6.9, 6.7, 6.8, 7.0, 6.8, 6.8],
      recommendation: 'An extra 30 min of sleep would add more buffer, especially given your family history.',
    },
    {
      metric: 'Weight',
      current: 'Within baseline',
      healthyRange: 'within ±2% of baseline',
      verdict: 'stable',
      detail: 'Within ±2% over the trend window.',
      series: [72.0, 72.1, 71.9, 72.2, 72.0, 72.0],
      recommendation: 'No changes needed — weight is stable.',
    },
    {
      metric: 'Stress',
      current: 'No elevated signal',
      healthyRange: 'Low–moderate workday load',
      verdict: 'stable',
      detail: 'No elevated signal detected.',
      series: [2, 3, 2, 3, 2, 2],
      recommendation: 'No elevated signal detected — keep it up.',
    },
    {
      metric: 'Food pattern',
      current: 'Balanced meals, occasional red meat',
      healthyRange: 'Balanced meals, mostly whole foods & fiber',
      verdict: 'stable',
      detail: 'No concerning pattern detected; consider trimming red-meat frequency given your family heart history.',
      series: [6, 6, 7, 6, 6, 6],
      recommendation: 'Consider trimming red-meat frequency in favor of fish or plant protein, given your family heart history.',
    },
  ],
};

// A one-line reminder of the condition-specific baseline that the 4 tracked
// parameters above don't otherwise capture (e.g. blood pressure isn't a
// trend.py classifier yet) — folded into the dashboard write-up only.
export const CONDITION_CONTEXT: Record<string, string> = {
  'demo-user':
    'Your last HbA1c was 6.1% (prediabetic range is 5.7–6.4%) with a mild magnesium deficiency (1.5 mg/dL vs. 1.7–2.2 mg/dL healthy) — both consistent with the glucose trend above.',
  'hypertension-user':
    'Your last home blood pressure average was 135/86 mmHg (Stage 1 hypertension) against a healthy target of under 120/80 mmHg — keep sodium under 2000mg/day and monitor weekly per your last visit.',
  'family-history-user':
    'You have a family history of heart disease, but your own readings remain in the healthy range — the biggest lever for staying there is keeping sleep and stress from drifting.',
};

export function metricTone(verdict: HealthMetric['verdict']): BadgeTone {
  switch (verdict) {
    case 'improving':
      return 'emerald';
    case 'worsening':
      return 'red';
    case 'stable':
      return 'slate';
  }
}

export interface HealthNarrative {
  /** Overall tone driving the callout's color treatment. */
  tone: 'good' | 'watch';
  headline: string;
  detail: string;
  /** Off-target metric names, rendered as chips under the headline. */
  watchItems: string[];
  conditionNote?: string;
}

/** Builds the styled "where you stand vs. where you're expected to be" brief for the home page. */
export function buildHealthNarrative(displayName: string, metrics: HealthMetric[], conditionContext?: string): HealthNarrative {
  const worsening = metrics.filter((m) => m.verdict === 'worsening');
  const improving = metrics.filter((m) => m.verdict === 'improving');
  const stable = metrics.filter((m) => m.verdict === 'stable');

  const tone: HealthNarrative['tone'] = worsening.length === 0 ? 'good' : 'watch';
  const headline =
    tone === 'good'
      ? `${displayName}, you're on track — all ${metrics.length} tracked parameters are healthy or improving.`
      : `${displayName}, ${worsening.length} of your ${metrics.length} tracked parameters need attention.`;

  const detailParts: string[] = [];
  if (worsening.length > 0) {
    const gaps = worsening.map((m) => `${m.metric} (currently ${m.current}, healthy is ${m.healthyRange})`).join('; ');
    detailParts.push(`${gaps}.`);
  }
  if (improving.length > 0) {
    detailParts.push(`${improving.map((m) => m.metric).join(' and ')} ${improving.length === 1 ? 'is' : 'are'} trending in the right direction.`);
  }
  if (stable.length > 0 && worsening.length > 0) {
    detailParts.push(`${stable.map((m) => m.metric).join(', ')} remain${stable.length === 1 ? 's' : ''} steady in the meantime.`);
  }

  return {
    tone,
    headline,
    detail: detailParts.join(' '),
    watchItems: worsening.map((m) => m.metric),
    conditionNote: conditionContext,
  };
}
