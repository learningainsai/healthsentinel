import { BadgeTone } from '../shared/ui/badge/badge';

export interface HealthMetric {
  metric: string;
  /** Latest observed value, formatted for display (e.g. "112 mg/dL (fasting)"). */
  current: string;
  /** The range/target a healthy adult is expected to sit within. */
  healthyRange: string;
  verdict: 'stable' | 'improving' | 'worsening';
  detail: string;
}

// Mocked per-profile trend data — a real backend computes verdicts
// deterministically in trend_agent from historic metrics_store readings
// (see src/healthsentinel/trends.py) and current/healthyRange from the
// latest lab panel + config.py thresholds. Shared by the Dashboard (home
// page summary) and Run Analysis (post-pipeline trend list) so both
// screens always agree.
export const HEALTH_METRICS: Record<string, HealthMetric[]> = {
  'demo-user': [
    {
      metric: 'Glucose',
      current: '112 mg/dL (fasting)',
      healthyRange: '70–99 mg/dL',
      verdict: 'worsening',
      detail: 'Trending up over the last 90 days, now in the prediabetic range (100–125 mg/dL).',
    },
    {
      metric: 'Sleep',
      current: '5.6 h/night (avg)',
      healthyRange: '7–9 h/night',
      verdict: 'worsening',
      detail: 'Averaging under 6h/night for 2 of the last 3 weeks.',
    },
    {
      metric: 'Weight',
      current: '78.4 kg',
      healthyRange: 'within ±2% of your 78.0 kg baseline',
      verdict: 'stable',
      detail: 'Within ±2% over the trend window.',
    },
    {
      metric: 'Stress',
      current: 'High meeting density',
      healthyRange: 'Low–moderate workday load',
      verdict: 'worsening',
      detail: 'Meeting density up on most workdays this month.',
    },
    {
      metric: 'Food pattern',
      current: 'Frequent high-glycemic snacks',
      healthyRange: 'Balanced meals, mostly whole foods & fiber',
      verdict: 'worsening',
      detail: 'Logged meals over the last 2 weeks skew toward refined carbs and low fiber — consistent with the glucose trend above.',
    },
  ],
  'hypertension-user': [
    {
      metric: 'Glucose',
      current: '92 mg/dL (fasting)',
      healthyRange: '70–99 mg/dL',
      verdict: 'stable',
      detail: 'Consistently within normal range.',
    },
    {
      metric: 'Sleep',
      current: '6.4 h/night (avg)',
      healthyRange: '7–9 h/night',
      verdict: 'stable',
      detail: 'Averaging 6–7h/night, consistent with prior months.',
    },
    {
      metric: 'Weight',
      current: 'Within baseline',
      healthyRange: 'within ±2% of baseline',
      verdict: 'stable',
      detail: 'Within ±2% over the trend window.',
    },
    {
      metric: 'Stress',
      current: 'Elevated meeting load',
      healthyRange: 'Low–moderate workday load',
      verdict: 'worsening',
      detail: 'Elevated meeting load flagged by the calendar connector.',
    },
    {
      metric: 'Food pattern',
      current: 'Frequent high-sodium takeout',
      healthyRange: 'Home-cooked, low-sodium meals (<2000mg/day)',
      verdict: 'worsening',
      detail: '3 of the last 7 logged meals were high-sodium takeout — above your physician-recommended sodium ceiling.',
    },
  ],
  'healthy-baseline-user': [
    {
      metric: 'Glucose',
      current: '88 mg/dL (fasting)',
      healthyRange: '70–99 mg/dL',
      verdict: 'stable',
      detail: 'Consistently within normal range.',
    },
    {
      metric: 'Sleep',
      current: '7.6 h/night (avg)',
      healthyRange: '7–9 h/night',
      verdict: 'improving',
      detail: 'Averaging 7.5h+/night, trending upward.',
    },
    {
      metric: 'Weight',
      current: 'Within baseline',
      healthyRange: 'within ±2% of baseline',
      verdict: 'stable',
      detail: 'Within ±2% over the trend window.',
    },
    {
      metric: 'Stress',
      current: 'No elevated signal',
      healthyRange: 'Low–moderate workday load',
      verdict: 'stable',
      detail: 'No elevated signal detected.',
    },
    {
      metric: 'Food pattern',
      current: 'Balanced, whole-food meals',
      healthyRange: 'Balanced meals, mostly whole foods & fiber',
      verdict: 'improving',
      detail: 'Logged meals consistently include lean protein, vegetables, and whole grains.',
    },
  ],
  'family-history-user': [
    {
      metric: 'Glucose',
      current: '91 mg/dL (fasting)',
      healthyRange: '70–99 mg/dL',
      verdict: 'stable',
      detail: 'Consistently within normal range.',
    },
    {
      metric: 'Sleep',
      current: '6.8 h/night (avg)',
      healthyRange: '7–9 h/night',
      verdict: 'stable',
      detail: 'Averaging 6.5–7h/night, consistent with prior months.',
    },
    {
      metric: 'Weight',
      current: 'Within baseline',
      healthyRange: 'within ±2% of baseline',
      verdict: 'stable',
      detail: 'Within ±2% over the trend window.',
    },
    {
      metric: 'Stress',
      current: 'No elevated signal',
      healthyRange: 'Low–moderate workday load',
      verdict: 'stable',
      detail: 'No elevated signal detected.',
    },
    {
      metric: 'Food pattern',
      current: 'Balanced meals, occasional red meat',
      healthyRange: 'Balanced meals, mostly whole foods & fiber',
      verdict: 'stable',
      detail: 'No concerning pattern detected; consider trimming red-meat frequency given your family heart history.',
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
