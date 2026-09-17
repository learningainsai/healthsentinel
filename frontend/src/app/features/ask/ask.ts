import { Component } from '@angular/core';
import { SymptomInsight } from './symptom-insight/symptom-insight';

@Component({
  imports: [SymptomInsight],
  selector: 'app-ask',
  templateUrl: './ask.html',
})
export class Ask {
  protected readonly suggestions = [
    "💤 I feel exhausted even after sleeping",
    "🤕 I've had a headache since this afternoon",
    "😵‍💫 I feel a bit dizzy today",
  ];
}
