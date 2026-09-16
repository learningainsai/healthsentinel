import { Component, inject, signal } from '@angular/core';
import { Auth } from '../../../core/auth';

interface HistoricSnapshot {
  avgSleepHours: number;
  magnesiumPctRda: number;
  lateNightMealsPerWeek: number;
  labFlags: string[];
  stressLoad: 'low' | 'moderate' | 'high';
}

interface Factor {
  label: string;
  detail: string;
  source: string;
}

interface AnalysisResult {
  severity: 'low' | 'medium' | 'high';
  escalated: boolean;
  factors: Factor[];
  suggestions: string[];
}

// Mocked per-profile historic signals — a real backend would pull these from
// trend_agent / nutrition_agent / lab_report_agent instead of hardcoding them.
const HISTORIC_SNAPSHOTS: Record<string, HistoricSnapshot> = {
  'demo-user': {
    avgSleepHours: 5.4,
    magnesiumPctRda: 58,
    lateNightMealsPerWeek: 4,
    labFlags: ['Fasting glucose 108 mg/dL (prediabetic range)'],
    stressLoad: 'moderate',
  },
  'hypertension-user': {
    avgSleepHours: 6.1,
    magnesiumPctRda: 71,
    lateNightMealsPerWeek: 1,
    labFlags: ['Sodium intake trending above target on 3 of the last 5 days'],
    stressLoad: 'high',
  },
  'healthy-baseline-user': {
    avgSleepHours: 7.6,
    magnesiumPctRda: 96,
    lateNightMealsPerWeek: 0,
    labFlags: [],
    stressLoad: 'low',
  },
  'family-history-user': {
    avgSleepHours: 6.4,
    magnesiumPctRda: 82,
    lateNightMealsPerWeek: 2,
    labFlags: ['LDL cholesterol 132 mg/dL (borderline high)'],
    stressLoad: 'moderate',
  },
};

const CONCERNING_TERMS = ['dizzy', 'dizziness', 'faint', 'chest pain', 'short of breath', 'palpitation'];

@Component({
  imports: [],
  selector: 'app-symptom-insight',
  styleUrl: './symptom-insight.scss',
  templateUrl: './symptom-insight.html',
})
export class SymptomInsight {
  private readonly auth = inject(Auth);

  protected readonly question = signal('');
  protected readonly isAnalyzing = signal(false);
  protected readonly result = signal<AnalysisResult | null>(null);

  protected onAnalyze(): void {
    const text = this.question().trim();
    if (!text) return;

    this.isAnalyzing.set(true);
    this.result.set(null);

    // Simulated latency to reflect the real pipeline's retrieval + LLM round trip.
    setTimeout(() => {
      this.result.set(this.analyze(text));
      this.isAnalyzing.set(false);
    }, 700);
  }

  private analyze(question: string): AnalysisResult {
    const snapshot = HISTORIC_SNAPSHOTS[this.auth.currentUsername() ?? ''] ?? HISTORIC_SNAPSHOTS['demo-user'];
    const lowerQuestion = question.toLowerCase();
    const factors: Factor[] = [];

    if (snapshot.avgSleepHours < 6.5) {
      factors.push({
        label: 'Sleep debt',
        source: 'Trend agent · iWatch sleep sessions',
        detail: `Averaging ${snapshot.avgSleepHours}h/night over the last 7 days — below the 7–9h range associated with daytime dizziness and fatigue.`,
      });
    }
    if (snapshot.magnesiumPctRda < 80) {
      factors.push({
        label: 'Low dietary magnesium',
        source: 'Nutrition agent · meal logs',
        detail: `Estimated at ${snapshot.magnesiumPctRda}% of RDA this week — magnesium deficiency is a known contributor to dizziness and muscle cramps.`,
      });
    }
    if (snapshot.lateNightMealsPerWeek >= 3) {
      factors.push({
        label: 'Frequent late-night meals',
        source: 'Nutrition agent + Calendar MCP',
        detail: `${snapshot.lateNightMealsPerWeek} meals logged after 9pm this week — late eating is linked to poorer sleep quality.`,
      });
    }
    for (const flag of snapshot.labFlags) {
      factors.push({ label: 'Lab flag', source: 'Lab report agent', detail: flag });
    }
    if (snapshot.stressLoad === 'high') {
      factors.push({
        label: 'Elevated stress load',
        source: 'Calendar MCP + SMS signals',
        detail: 'Back-to-back meetings on most workdays this week — stress can manifest as dizziness or tension headaches.',
      });
    }
    if (factors.length === 0) {
      factors.push({
        label: 'No strong signal found',
        source: 'Trend agent',
        detail: 'This week\u2019s sleep, nutrition, and lab data are within your normal ranges. Consider hydration, inner-ear causes, or a clinician visit if symptoms persist.',
      });
    }

    const hasConcerningTerm = CONCERNING_TERMS.some((term) => lowerQuestion.includes(term));
    const severity: AnalysisResult['severity'] =
      hasConcerningTerm && snapshot.labFlags.length > 0
        ? 'high'
        : factors.length >= 2
          ? 'medium'
          : 'low';

    const suggestions: string[] = [];
    if (factors.some((f) => f.label === 'Low dietary magnesium')) {
      suggestions.push('Add magnesium-rich foods (leafy greens, nuts, whole grains) to a couple of meals this week.');
    }
    if (factors.some((f) => f.label === 'Sleep debt')) {
      suggestions.push('Aim for a consistent bedtime and reduce screen time in the hour before sleep.');
    }
    if (factors.some((f) => f.label === 'Frequent late-night meals')) {
      suggestions.push('Try shifting your last meal earlier — within 2\u20133 hours of bedtime.');
    }
    if (factors.some((f) => f.label === 'Elevated stress load')) {
      suggestions.push('Block a short recovery gap between back-to-back meetings where possible.');
    }
    if (snapshot.labFlags.length > 0) {
      suggestions.push('Discuss the flagged lab reading with your clinician at your next visit.');
    }
    if (suggestions.length === 0) {
      suggestions.push('Keep logging meals and sleep — nothing concerning stands out yet.');
    }

    return { severity, escalated: severity === 'high', factors, suggestions };
  }

  protected severityBadgeClass(severity: AnalysisResult['severity']): string {
    switch (severity) {
      case 'high':
        return 'bg-red-100 text-red-700';
      case 'medium':
        return 'bg-amber-100 text-amber-700';
      case 'low':
        return 'bg-emerald-100 text-emerald-700';
    }
  }
}

