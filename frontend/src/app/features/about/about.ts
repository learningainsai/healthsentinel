import { Component } from '@angular/core';
import { Badge, BadgeTone } from '../../shared/ui/badge/badge';

interface PipelineStage {
  name: string;
  kind: 'code' | 'llm' | 'hybrid' | 'human';
  tier?: string;
  description: string;
}

// Moved verbatim (content-wise) from the old home.ts God Component — this is
// architecture/dev-facing information and doesn't belong in the primary
// logging/analysis user loop.
const PIPELINE_STAGES: PipelineStage[] = [
  { name: 'Consent + rate-limit gates', kind: 'code', description: 'Hard-stops the run if Tier 1 consent is missing or the rate limit is exceeded.' },
  { name: 'Intake agent', kind: 'hybrid', tier: 'cheap', description: 'Classifies staged notes/attachments and routes them to the right agent.' },
  { name: 'Vision agent', kind: 'llm', tier: 'cheap', description: 'Meal-photo food recognition with a hallucination confidence floor.' },
  { name: 'Nutrition agent', kind: 'hybrid', tier: 'mid', description: 'Maps meals to canonical foods; macros/micros computed deterministically.' },
  { name: 'Medical RAG agent', kind: 'llm', tier: 'mid', description: 'Retrieves and answers from your medical documents — refuses rather than fabricate.' },
  { name: 'Activity / SMS / Calendar agents', kind: 'code', description: 'Simulated MCP connectors (iWatch, SMS, Google Calendar) — no model call.' },
  { name: 'Lab report agent', kind: 'hybrid', tier: 'mid', description: 'Extracts lab readings, validated against a metric allowlist and physiological bounds.' },
  { name: 'Trend agent', kind: 'code', description: 'Deterministic aggregation/threshold classification of historic metric series.' },
  { name: 'Prediction agent', kind: 'llm', tier: 'reasoning', description: 'Reasoning-tier risk prediction across nutrition, activity, and lab signals.' },
  { name: 'Guardrail gate', kind: 'code', description: 'Routes low-confidence, new-user, or high/critical-severity cases to human review.' },
  { name: 'Nutritionist review', kind: 'human', description: 'Human-in-the-loop approval for flagged predictions before recommendations run.' },
  { name: 'Recommendation agent', kind: 'llm', tier: 'mid', description: 'Generates recommendations, filtered by allergy and calorie/exercise guardrails.' },
  { name: 'Critic + Insight agents', kind: 'llm', tier: 'reasoning', description: 'Advisory-only review of the final report and longitudinal insight generation.' },
];

@Component({
  imports: [Badge],
  selector: 'app-about',
  templateUrl: './about.html',
})
export class About {
  protected readonly pipelineStages = PIPELINE_STAGES;

  protected readonly modelRouting = [
    { stage: 'Vision (meal photo)', model: 'gpt-4o-mini' },
    { stage: 'Nutrition / MCP agents / Recommendations', model: 'gpt-4o-mini' },
    { stage: 'Prediction engine + Critic', model: 'gpt-4o' },
  ];

  protected kindTone(kind: PipelineStage['kind']): BadgeTone {
    switch (kind) {
      case 'code': return 'sky';
      case 'llm': return 'violet';
      case 'hybrid': return 'indigo';
      case 'human': return 'amber';
    }
  }

  protected kindLabel(kind: PipelineStage['kind']): string {
    switch (kind) {
      case 'code': return 'Deterministic';
      case 'llm': return 'LLM';
      case 'hybrid': return 'Hybrid';
      case 'human': return 'Human-in-the-loop';
    }
  }
}
