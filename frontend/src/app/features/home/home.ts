import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Auth } from '../../core/auth';
import { Consent } from '../../core/consent';
import { NavBar } from '../../shared/nav-bar/nav-bar';
import { SymptomInsight } from './symptom-insight/symptom-insight';

type QuickActionId = 'meal' | 'lab' | 'trends';

interface StagedItem {
  id: string;
  kind: 'meal' | 'lab';
  label: string;
  addedAt: Date;
}

interface TrendMetric {
  metric: string;
  verdict: 'stable' | 'improving' | 'worsening';
  detail: string;
}

// Mocked per-profile trend verdicts — a real backend computes these
// deterministically in trend_agent from historic metrics_store readings.
const TREND_MOCKS: Record<string, TrendMetric[]> = {
  'demo-user': [
    { metric: 'Glucose', verdict: 'worsening', detail: 'Trending up over the last 90 days, now in the prediabetic range.' },
    { metric: 'Sleep', verdict: 'worsening', detail: 'Averaging under 6h/night for 2 of the last 3 weeks.' },
    { metric: 'Weight', verdict: 'stable', detail: 'Within \u00b12% over the trend window.' },
    { metric: 'Stress', verdict: 'worsening', detail: 'Meeting density up on most workdays this month.' },
  ],
  'hypertension-user': [
    { metric: 'Glucose', verdict: 'stable', detail: 'Consistently within normal range.' },
    { metric: 'Sleep', verdict: 'stable', detail: 'Averaging 6–7h/night, consistent with prior months.' },
    { metric: 'Weight', verdict: 'stable', detail: 'Within \u00b12% over the trend window.' },
    { metric: 'Stress', verdict: 'worsening', detail: 'Elevated meeting load flagged by the calendar connector.' },
  ],
  'healthy-baseline-user': [
    { metric: 'Glucose', verdict: 'stable', detail: 'Consistently within normal range.' },
    { metric: 'Sleep', verdict: 'improving', detail: 'Averaging 7.5h+/night, trending upward.' },
    { metric: 'Weight', verdict: 'stable', detail: 'Within \u00b12% over the trend window.' },
    { metric: 'Stress', verdict: 'stable', detail: 'No elevated signal detected.' },
  ],
  'family-history-user': [
    { metric: 'Glucose', verdict: 'stable', detail: 'Consistently within normal range.' },
    { metric: 'Sleep', verdict: 'stable', detail: 'Averaging 6.5–7h/night, consistent with prior months.' },
    { metric: 'Weight', verdict: 'stable', detail: 'Within \u00b12% over the trend window.' },
    { metric: 'Stress', verdict: 'stable', detail: 'No elevated signal detected.' },
  ],
};

interface PipelineStage {
  name: string;
  kind: 'code' | 'llm' | 'hybrid' | 'human';
  tier?: string;
  description: string;
}

const PIPELINE_STAGES: PipelineStage[] = [
  {
    name: 'Consent + rate-limit gates',
    kind: 'code',
    description: 'Hard-stops the run if Tier 1 consent is missing or the rate limit is exceeded.',
  },
  {
    name: 'Intake agent',
    kind: 'hybrid',
    tier: 'cheap',
    description: 'Classifies staged notes/attachments and routes them to the right agent.',
  },
  {
    name: 'Vision agent',
    kind: 'llm',
    tier: 'cheap',
    description: 'Meal-photo food recognition with a hallucination confidence floor.',
  },
  {
    name: 'Nutrition agent',
    kind: 'hybrid',
    tier: 'mid',
    description: 'Maps meals to canonical foods; macros/micros computed deterministically.',
  },
  {
    name: 'Medical RAG agent',
    kind: 'llm',
    tier: 'mid',
    description: 'Retrieves and answers from your medical documents — refuses rather than fabricate.',
  },
  {
    name: 'Activity / SMS / Calendar agents',
    kind: 'code',
    description: 'Simulated MCP connectors (iWatch, SMS, Google Calendar) — no model call.',
  },
  {
    name: 'Lab report agent',
    kind: 'hybrid',
    tier: 'mid',
    description: 'Extracts lab readings, validated against a metric allowlist and physiological bounds.',
  },
  {
    name: 'Trend agent',
    kind: 'code',
    description: 'Deterministic aggregation/threshold classification of historic metric series.',
  },
  {
    name: 'Prediction agent',
    kind: 'llm',
    tier: 'reasoning',
    description: 'Reasoning-tier risk prediction across nutrition, activity, and lab signals.',
  },
  {
    name: 'Guardrail gate',
    kind: 'code',
    description: 'Routes low-confidence, new-user, or high/critical-severity cases to human review.',
  },
  {
    name: 'Nutritionist review',
    kind: 'human',
    description: 'Human-in-the-loop approval for flagged predictions before recommendations run.',
  },
  {
    name: 'Recommendation agent',
    kind: 'llm',
    tier: 'mid',
    description: 'Generates recommendations, filtered by allergy and calorie/exercise guardrails.',
  },
  {
    name: 'Critic + Insight agents',
    kind: 'llm',
    tier: 'reasoning',
    description: 'Advisory-only review of the final report and longitudinal insight generation.',
  },
];

@Component({
  imports: [NavBar, DatePipe, SymptomInsight],
  selector: 'app-home',
  styleUrl: './home.scss',
  templateUrl: './home.html',
})
export class Home {
  private readonly auth = inject(Auth);
  private readonly consentService = inject(Consent);

  protected readonly account = this.auth.currentAccount;
  protected readonly consentState = computed(() =>
    this.consentService.stateFor(this.auth.currentUsername()),
  );
  protected readonly pipelineStages = PIPELINE_STAGES;

  protected readonly modelRouting = [
    { stage: 'Vision (meal photo)', model: 'gpt-4o-mini' },
    { stage: 'Nutrition / MCP agents / Recommendations', model: 'gpt-4o-mini' },
    { stage: 'Prediction engine + Critic', model: 'gpt-4o' },
  ];

  protected readonly quickActions: { id: QuickActionId; icon: string; title: string; description: string }[] = [
    { id: 'meal', icon: '🍽️', title: 'Log a meal', description: 'Attach a photo or describe what you ate today.' },
    { id: 'lab', icon: '🧪', title: 'Upload a lab report', description: 'Extract readings for glucose, lipids, and more.' },
    { id: 'trends', icon: '📈', title: 'View trends', description: 'See glucose, sleep, and stress trends over time.' },
  ];

  protected readonly activePanel = signal<QuickActionId | null>(null);
  protected readonly mealText = signal('');
  protected readonly stagedItems = signal<StagedItem[]>([]);
  protected readonly trends = computed(() => TREND_MOCKS[this.auth.currentUsername() ?? ''] ?? TREND_MOCKS['demo-user']);

  protected toggleAction(id: QuickActionId): void {
    this.activePanel.set(this.activePanel() === id ? null : id);
  }

  protected addMeal(): void {
    const text = this.mealText().trim();
    if (!text) return;
    this.stagedItems.set([
      ...this.stagedItems(),
      { id: crypto.randomUUID(), kind: 'meal', label: text, addedAt: new Date() },
    ]);
    this.mealText.set('');
  }

  protected onLabFileSelected(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.stagedItems.set([
      ...this.stagedItems(),
      { id: crypto.randomUUID(), kind: 'lab', label: file.name, addedAt: new Date() },
    ]);
    (event.target as HTMLInputElement).value = '';
  }

  protected removeStagedItem(id: string): void {
    this.stagedItems.set(this.stagedItems().filter((item) => item.id !== id));
  }

  protected trendBadgeClass(verdict: TrendMetric['verdict']): string {
    switch (verdict) {
      case 'improving':
        return 'bg-emerald-100 text-emerald-700';
      case 'worsening':
        return 'bg-red-100 text-red-700';
      case 'stable':
        return 'bg-slate-100 text-slate-600';
    }
  }

  protected kindBadgeClass(kind: PipelineStage['kind']): string {
    switch (kind) {
      case 'code':
        return 'bg-sky-100 text-sky-700';
      case 'llm':
        return 'bg-violet-100 text-violet-700';
      case 'hybrid':
        return 'bg-indigo-100 text-indigo-700';
      case 'human':
        return 'bg-amber-100 text-amber-700';
    }
  }

  protected kindLabel(kind: PipelineStage['kind']): string {
    switch (kind) {
      case 'code':
        return 'Deterministic';
      case 'llm':
        return 'LLM';
      case 'hybrid':
        return 'Hybrid';
      case 'human':
        return 'Human-in-the-loop';
    }
  }
}

