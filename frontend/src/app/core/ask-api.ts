import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export type AskCategory = 'symptom' | 'sleep' | 'nutrition' | 'lab' | 'stress' | 'activity' | 'medication' | 'other';

export interface AskClassification {
  category: AskCategory;
  needs_more_details: boolean;
  reason: string;
  prompt_version: string;
  analysis?: {
    severity: 'low' | 'medium' | 'high';
    factors: Array<{
      category: 'sleep_debt' | 'low_magnesium' | 'late_night_meals' | 'lab_flag' | 'elevated_stress';
      detail: string;
      source: string;
      confidence: 'confirmed' | 'suggestive';
    }>;
    suggestions: string[];
    insufficient_evidence: boolean;
  } | null;
}

@Injectable({ providedIn: 'root' })
export class AskApi {
  private readonly http = inject(HttpClient);
  private readonly endpoint = 'http://localhost:8000/api/ask/classify';

  classify(prompt: string, userId: string | null): Observable<AskClassification> {
    return this.http.post<AskClassification>(this.endpoint, {
      prompt,
      user_id: userId ?? 'demo-user',
    });
  }
}
