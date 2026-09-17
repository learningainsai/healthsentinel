import { Component, inject, signal } from '@angular/core';
import { AskApi, AskCategory } from '../../../core/ask-api';
import { Auth } from '../../../core/auth';
import { assertSafeForLlm } from '../../../core/prompt-safety';

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
  category: AskCategory;
  severity: 'low' | 'medium' | 'high';
  escalated: boolean;
  insufficientEvidence: boolean;
  factors: Factor[];
  suggestions: string[];
}

@Component({
  imports: [],
  selector: 'app-symptom-insight',
  styleUrl: './symptom-insight.scss',
  templateUrl: './symptom-insight.html',
})
export class SymptomInsight {
  private readonly auth = inject(Auth);
  private readonly askApi = inject(AskApi);

  protected readonly question = signal('');
  protected readonly isAnalyzing = signal(false);
  protected readonly result = signal<AnalysisResult | null>(null);
  protected readonly refusalIssues = signal<string[] | null>(null);
  protected readonly needsSymptomDetail = signal(false);
  protected readonly classification = signal<{ category: AskCategory; reason: string } | null>(null);
  protected readonly apiError = signal<string | null>(null);

  protected readonly factorLabels = FACTOR_LABELS;

  useSuggestion(text: string): void {
    this.question.set(text);
  }

  protected onAnalyze(): void {
    const raw = this.question().trim();
    if (!raw) return;

    this.result.set(null);
    this.needsSymptomDetail.set(false);
    this.classification.set(null);
    this.apiError.set(null);

    // Client-side UX check; the authoritative scan runs again in the API.
    const check = assertSafeForLlm(raw);
    if (!check.safe) {
      this.refusalIssues.set(check.issues);
      return;
    }
    this.refusalIssues.set(null);

    this.isAnalyzing.set(true);
    this.apiError.set(null);
    this.askApi.classify(check.cleanText, this.auth.currentUsername()).subscribe({
      next: (classification) => {
        this.classification.set({ category: classification.category, reason: classification.reason });
        if (classification.needs_more_details) {
          this.needsSymptomDetail.set(true);
          this.isAnalyzing.set(false);
          return;
        }
        const analysis = classification.analysis;
        if (!analysis) {
          this.apiError.set('The Ask Sentinel flow returned no analysis. Please try again.');
          this.isAnalyzing.set(false);
          return;
        }
        this.result.set({
          category: classification.category,
          severity: analysis.severity,
          escalated: analysis.severity === 'high',
          insufficientEvidence: analysis.insufficient_evidence,
          factors: analysis.factors,
          suggestions: analysis.suggestions,
        });
        this.isAnalyzing.set(false);
      },
      error: (error: { error?: { detail?: { issues?: string[] } | string } }) => {
        const detail = error.error?.detail;
        const issues = typeof detail === 'object' && detail?.issues ? detail.issues : null;
        if (issues) {
          this.refusalIssues.set(issues);
        } else {
          this.apiError.set('The guarded Ask Sentinel API is unavailable. Start the API server and try again.');
        }
        this.isAnalyzing.set(false);
      },
    });
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

  protected categoryLabel(category: AskCategory): string {
    return category === 'other' ? 'Needs more detail' : category.replace('_', ' ');
  }
}


