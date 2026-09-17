import { Component } from '@angular/core';
import { SymptomInsight } from './symptom-insight/symptom-insight';

@Component({
  imports: [SymptomInsight],
  selector: 'app-ask',
  templateUrl: './ask.html',
})
export class Ask {}
