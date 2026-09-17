import { Component, computed, inject, signal } from '@angular/core';
import { Auth } from '../../core/auth';
import { assertSafeForLlm } from '../../core/prompt-safety';
import { Staging } from '../../core/staging';
import { Badge, BadgeTone } from '../../shared/ui/badge/badge';

interface TrendMetric {
  metric: string;
  verdict: 'stable' | 'improving' | 'worsening';
  detail: string;
}

type ReviewStageId = 'medical' | 'prediction' | 'nutritionist' | 'recommendation' | 'critic' | 'insight';

interface ReviewStep {
  id: ReviewStageId;
  label: string;
  content: string;
}

const STAGE_LABELS: Record<ReviewStageId, string> = {
  medical: 'Medical document context',
  prediction: 'Prediction results',
  nutritionist: 'Nutritionist review',
  recommendation: 'Recommendations',
  critic: 'Critic review',
  insight: 'AI observations',
};

export interface FinalReportSection {
  title: string;
  bullets: string[];
  intro?: string;
}

export interface FinalReportData {
  predictions?: FinalReportSection;
  recommendations?: FinalReportSection;
  critic?: { passed: boolean; text: string };
  insight?: FinalReportSection;
  loggedEntries: { icon: string; label: string; analysis: string }[];
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

  // Mandatory human-edit review checkpoint state — one step per LLM stage,
  // mirroring the real backend's graph.py review_checkpoints (see
  // review_checkpoints.py / graph.py): every stage's output must be
  // reviewed (and may be edited) before the next stage runs or the final
  // report is stored. Every edit is re-checked with the same
  // prompt-injection scanner used client-side in Ask Sentinel.
  protected readonly reviewQueue = signal<ReviewStep[]>([]);
  protected readonly currentIndex = signal(0);
  protected readonly editableText = signal('');
  protected readonly reviewError = signal<string | null>(null);
  protected readonly reviewedSummaries = signal<Partial<Record<ReviewStageId, string>>>({});
  protected readonly severity = signal<'LOW' | 'MEDIUM' | 'HIGH'>('LOW');
  protected readonly rejected = signal(false);
  protected readonly finalReport = signal<FinalReportData | null>(null);

  protected readonly currentStep = computed(() => this.reviewQueue()[this.currentIndex()] ?? null);
  protected readonly allReviewed = this.staging.allReviewed;
  private readonly blockedRecommendations = signal<string[]>([]);
  // Snapshot of confirmed staged entries taken at run start (before the
  // queue is cleared) so the final report can show what was actually used.
  private loggedEntriesSnapshot: { icon: string; label: string; analysis: string }[] = [];

  protected remove(id: string): void {
    this.staging.remove(id);
  }

  protected kindIcon(kind: string): string {
    return kind === 'meal' ? '🍽️' : kind === 'lab' ? '🧪' : '🏃';
  }

  protected runAnalysis(): void {
    if (this.items().length === 0 || this.isRunning() || !this.allReviewed()) return;
    this.isRunning.set(true);
    this.hasRun.set(false);
    this.finalReport.set(null);
    this.rejected.set(false);
    this.reviewedSummaries.set({});
    this.loggedEntriesSnapshot = this.items().map((i) => ({
      icon: this.kindIcon(i.kind),
      label: i.label,
      analysis: i.analysis,
    }));
    // Simulated pipeline latency (intake → nutrition/lab/activity agents →
    // trend agent → prediction/critic) before the first review checkpoint.
    // The confirmed per-entry analyses (reviewed in Log Data) are the only
    // input this pipeline ever reads -- never the raw, unconfirmed draft.
    setTimeout(() => {
      this.isRunning.set(false);
      const queue = this.buildReviewQueue();
      this.reviewQueue.set(queue);
      this.currentIndex.set(0);
      this.editableText.set(queue[0]?.content ?? '');
      this.reviewError.set(null);
    }, 1200);
  }

  protected confirmStep(): void {
    const step = this.currentStep();
    if (!step) return;
    const check = assertSafeForLlm(this.editableText());
    if (!check.safe) {
      this.reviewError.set(check.issues.join('; '));
      return;
    }
    this.reviewError.set(null);
    this.reviewedSummaries.set({ ...this.reviewedSummaries(), [step.id]: check.cleanText });
    this.advance();
  }

  protected decideNutritionist(decision: 'approve' | 'modify' | 'reject'): void {
    if (decision === 'reject') {
      this.rejected.set(true);
      this.reviewQueue.set([]);
      this.staging.markRun();
      this.staging.clear();
      this.hasRun.set(true);
      return;
    }
    this.advance();
  }

  private advance(): void {
    const nextIndex = this.currentIndex() + 1;
    const queue = this.reviewQueue();
    if (nextIndex >= queue.length) {
      this.finalizeReport();
      return;
    }
    this.currentIndex.set(nextIndex);
    this.editableText.set(queue[nextIndex].content);
  }

  private finalizeReport(): void {
    const s = this.reviewedSummaries();
    const report: FinalReportData = { loggedEntries: this.loggedEntriesSnapshot };
    if (s.prediction) report.predictions = this.toSection('Predictions', s.prediction);
    if (s.recommendation) report.recommendations = this.toSection('Recommendations', s.recommendation);
    if (s.critic) report.critic = { passed: !s.critic.includes('ISSUES FOUND'), text: s.critic };
    if (s.insight) report.insight = this.toSection('AI observations', s.insight);

    this.finalReport.set(report);
    this.reviewQueue.set([]);
    this.staging.markRun();
    this.staging.clear();
    this.hasRun.set(true);
  }

  /** Splits a "Label:\n- bullet\n- bullet" mock string into a display section. */
  private toSection(title: string, text: string): FinalReportSection {
    const lines = text.split('\n').filter((l) => l.trim());
    const bullets = lines.filter((l) => l.trim().startsWith('-')).map((l) => l.replace(/^-\s*/, ''));
    const intro = lines.find((l) => !l.trim().startsWith('-') && !l.trim().endsWith(':'));
    return { title, bullets, intro };
  }

  private buildReviewQueue(): ReviewStep[] {
    const steps: ReviewStep[] = [];
    steps.push({ id: 'medical', label: STAGE_LABELS.medical, content: this.summarizeMedical() });
    steps.push({ id: 'prediction', label: STAGE_LABELS.prediction, content: this.summarizePrediction() });

    const severity = this.computeSeverity();
    this.severity.set(severity);
    if (severity === 'HIGH') {
      steps.push({ id: 'nutritionist', label: STAGE_LABELS.nutritionist, content: '' });
    }

    steps.push({ id: 'recommendation', label: STAGE_LABELS.recommendation, content: this.summarizeRecommendation() });
    steps.push({ id: 'critic', label: STAGE_LABELS.critic, content: this.summarizeCritic() });
    steps.push({ id: 'insight', label: STAGE_LABELS.insight, content: this.summarizeInsight() });
    return steps;
  }

  private summarizeMedical(): string {
    const account = this.auth.currentAccount();
    const conditions = account?.conditions?.length ? account.conditions.join(', ') : 'no known conditions on file';
    const allergies = account?.allergies?.length ? account.allergies.join(', ') : 'no known allergies on file';
    const loggedNote = this.loggedEntriesSnapshot.length
      ? `\nConfirmed entries considered: ${this.loggedEntriesSnapshot.map((e) => e.label).join(', ')}.`
      : '';
    return (
      `Medical context: Known conditions: ${conditions}. Known allergies: ${allergies}.` +
      loggedNote +
      `\nCitations: medical_history.md, blood_report_latest.md`
    );
  }


  private summarizePrediction(): string {
    const worsening = this.trends().filter((t) => t.verdict === 'worsening');
    if (worsening.length === 0) {
      return (
        'Predictions:\n- general_wellness (90% confidence, severity LOW): Overall indicators are ' +
        'stable — why: no worsening trends detected this period.'
      );
    }
    return (
      'Predictions:\n' +
      worsening
        .map((t) => `- lifestyle_trend (78% confidence, severity MEDIUM): ${t.metric} trend needs attention — why: ${t.detail}`)
        .join('\n')
    );
  }

  private computeSeverity(): 'LOW' | 'MEDIUM' | 'HIGH' {
    const worseningCount = this.trends().filter((t) => t.verdict === 'worsening').length;
    return worseningCount >= 2 ? 'HIGH' : worseningCount === 1 ? 'MEDIUM' : 'LOW';
  }

  private summarizeRecommendation(): string {
    const account = this.auth.currentAccount();
    const allergies = new Set((account?.allergies ?? []).map((a) => a.toLowerCase()));
    const candidates: { title: string; detail: string; allergensIn: string[] }[] = [
      { title: 'Increase Magnesium Intake', detail: 'Add leafy greens, nuts, and whole grains to your meals this week.', allergensIn: [] },
      { title: 'Peanut Butter Snack for Magnesium', detail: 'A tablespoon of peanut butter is a good magnesium source.', allergensIn: ['peanuts'] },
      { title: 'Maintain Healthy Sleep Patterns', detail: 'Keep a consistent bedtime to support your current sleep average.', allergensIn: [] },
      { title: 'Shellfish-based Omega-3 Boost', detail: 'Shrimp and other shellfish are rich in omega-3s.', allergensIn: ['shellfish'] },
    ];

    const blocked: string[] = [];
    const kept = candidates.filter((c) => {
      const hit = c.allergensIn.find((a) => allergies.has(a));
      if (hit) {
        blocked.push(`${c.title} (blocked: contains ${hit})`);
        return false;
      }
      return true;
    });
    this.blockedRecommendations.set(blocked);
    return 'Recommendations:\n' + kept.map((c) => `- ${c.title} — ${c.detail}`).join('\n');
  }

  private summarizeCritic(): string {
    const blocked = this.blockedRecommendations();
    if (blocked.length > 0) {
      return (
        `Critic review: ISSUES FOUND (guardrail score 75%)\nThe following recommendation(s) were ` +
        `correctly blocked by the allergen guardrail before reaching you: ${blocked.join('; ')}`
      );
    }
    return (
      'Critic review: PASSED (guardrail score 96%)\nNo issues found — recommendations respect all ' +
      'declared allergies and safety bounds.'
    );
  }

  private summarizeInsight(): string {
    const worsening = this.trends()
      .filter((t) => t.verdict === 'worsening')
      .map((t) => t.metric);
    if (worsening.length === 0) {
      return 'AI observations (advisory):\n- No concerning cross-metric patterns detected this period.';
    }
    return (
      `AI observations (advisory):\n- Your ${worsening.join(' and ')} trend(s) may be related — ` +
      `consider reviewing sleep hygiene and stress load together.`
    );
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

