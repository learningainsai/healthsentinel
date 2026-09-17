import { Component, inject, signal } from '@angular/core';
import { Auth } from '../../../core/auth';
import { assertSafeForLlm } from '../../../core/prompt-safety';

interface HistoricSnapshot {
  avgSleepHours: number;
  magnesiumPctRda: number;
  lateNightMealsPerWeek: number;
  labFlags: string[];
  stressLoad: 'low' | 'moderate' | 'high';
}

// Closed set of contributing-factor categories — a real LLM-backed version
// must select only from this enum (never invent a new category), same
// pattern as KNOWN_ALLERGY_CATEGORIES on the backend.
type FactorCategory = 'sleep_debt' | 'low_magnesium' | 'late_night_meals' | 'lab_flag' | 'elevated_stress';

const FACTOR_LABELS: Record<FactorCategory, string> = {
  sleep_debt: 'Sleep debt',
  low_magnesium: 'Low dietary magnesium',
  late_night_meals: 'Frequent late-night meals',
  lab_flag: 'Lab flag',
  elevated_stress: 'Elevated stress load',
};

interface Factor {
  category: FactorCategory;
  detail: string;
  source: string;
  // 'confirmed' = crosses a hard numeric threshold; 'suggestive' = a weaker,
  // proxy signal (e.g. meeting density standing in for measured stress).
  confidence: 'confirmed' | 'suggestive';
}

interface AnalysisResult {
  severity: 'low' | 'medium' | 'high';
  escalated: boolean;
  insufficientEvidence: boolean;
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

// Words/phrases that indicate an actual symptom description is present. This
// mock only ever cross-checks a *stated* symptom against the historic
// snapshot below — a vague question with no symptom in it (e.g. "how is my
// health looking these days") has nothing for it to cross-check, so it must
// not silently return the same canned factor list every time regardless of
// what was typed (that's what made it look broken/not actually reading the
// query). A real backend would let an LLM classify this instead of a keyword list.
const SYMPTOM_KEYWORDS = [
  'dizzy', 'dizziness', 'faint', 'headache', 'head ache', 'migraine', 'tired', 'exhaust',
  'fatigue', 'sleepy', 'nausea', 'nauseous', 'vomit', 'sick', 'unwell', 'pain', 'ache',
  'cramp', 'weak', 'weakness', 'palpitation', 'chest', 'breath', 'short of breath',
  'insomnia', "can't sleep", 'cant sleep', 'stressed', 'anxious', 'anxiety', 'cold',
  'fever', 'cough', 'sore throat', 'sore', 'stomach', 'gas', 'bloat', 'rash', 'itch',
  'swelling', 'sweat', 'numb', 'tingling', 'blurry', 'blurred vision',
];

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
  protected readonly refusalIssues = signal<string[] | null>(null);
  protected readonly needsSymptomDetail = signal(false);

  protected readonly factorLabels = FACTOR_LABELS;

  useSuggestion(text: string): void {
    this.question.set(text);
  }

  protected onAnalyze(): void {
    const raw = this.question().trim();
    if (!raw) return;

    this.result.set(null);
    this.needsSymptomDetail.set(false);

    // Client-side mirror of guardrails/prompt_injection.py — a UX layer only,
    // NOT a security boundary (client code is bypassable). The authoritative
    // check must run server-side once a real backend LLM call exists.
    const check = assertSafeForLlm(raw);
    if (!check.safe) {
      this.refusalIssues.set(check.issues);
      return;
    }
    this.refusalIssues.set(null);

    // Nothing resembling a symptom to cross-check — don't dump the same
    // canned factor list regardless of what was asked; ask for specifics.
    const lowerQuestion = check.cleanText.toLowerCase();
    if (!SYMPTOM_KEYWORDS.some((term) => lowerQuestion.includes(term))) {
      this.needsSymptomDetail.set(true);
      return;
    }

    this.isAnalyzing.set(true);
    // Simulated latency to reflect the real pipeline's retrieval + LLM round trip.
    setTimeout(() => {
      this.result.set(this.analyze(check.cleanText));
      this.isAnalyzing.set(false);
    }, 700);
  }

  private analyze(question: string): AnalysisResult {
    const snapshot = HISTORIC_SNAPSHOTS[this.auth.currentUsername() ?? ''] ?? HISTORIC_SNAPSHOTS['demo-user'];
    const lowerQuestion = question.toLowerCase();
    const factors: Factor[] = [];

    if (snapshot.avgSleepHours < 6.5) {
      factors.push({
        category: 'sleep_debt',
        confidence: 'confirmed',
        source: 'Trend agent · iWatch sleep sessions',
        detail: `Averaging ${snapshot.avgSleepHours}h/night over the last 7 days — below the 7–9h range associated with daytime dizziness and fatigue.`,
      });
    }
    if (snapshot.magnesiumPctRda < 80) {
      factors.push({
        category: 'low_magnesium',
        confidence: 'confirmed',
        source: 'Nutrition agent · meal logs',
        detail: `Estimated at ${snapshot.magnesiumPctRda}% of RDA this week — magnesium deficiency is a known contributor to dizziness and muscle cramps.`,
      });
    }
    if (snapshot.lateNightMealsPerWeek >= 3) {
      factors.push({
        category: 'late_night_meals',
        confidence: 'confirmed',
        source: 'Nutrition agent + Calendar MCP',
        detail: `${snapshot.lateNightMealsPerWeek} meals logged after 9pm this week — late eating is linked to poorer sleep quality.`,
      });
    }
    for (const flag of snapshot.labFlags) {
      factors.push({ category: 'lab_flag', confidence: 'confirmed', source: 'Lab report agent', detail: flag });
    }
    if (snapshot.stressLoad === 'high') {
      factors.push({
        category: 'elevated_stress',
        confidence: 'suggestive',
        source: 'Calendar MCP + SMS signals',
        detail: 'Back-to-back meetings on most workdays this week — stress can manifest as dizziness or tension headaches.',
      });
    }

    const insufficientEvidence = factors.length === 0;

    const hasConcerningTerm = CONCERNING_TERMS.some((term) => lowerQuestion.includes(term));
    const severity: AnalysisResult['severity'] =
      hasConcerningTerm && snapshot.labFlags.length > 0
        ? 'high'
        : factors.length >= 2
          ? 'medium'
          : 'low';

    const suggestions: string[] = [];
    if (factors.some((f) => f.category === 'low_magnesium')) {
      suggestions.push('Add magnesium-rich foods (leafy greens, nuts, whole grains) to a couple of meals this week.');
    }
    if (factors.some((f) => f.category === 'sleep_debt')) {
      suggestions.push('Aim for a consistent bedtime and reduce screen time in the hour before sleep.');
    }
    if (factors.some((f) => f.category === 'late_night_meals')) {
      suggestions.push('Try shifting your last meal earlier — within 2\u20133 hours of bedtime.');
    }
    if (factors.some((f) => f.category === 'elevated_stress')) {
      suggestions.push('Block a short recovery gap between back-to-back meetings where possible.');
    }
    if (snapshot.labFlags.length > 0) {
      suggestions.push('Discuss the flagged lab reading with your clinician at your next visit.');
    }
    if (suggestions.length === 0) {
      suggestions.push(
        'Keep logging meals and sleep. Nothing in your recent data stands out — consider hydration, ' +
          'inner-ear causes, or a clinician visit if symptoms persist.',
      );
    }

    return { severity, escalated: severity === 'high', insufficientEvidence, factors, suggestions };
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


