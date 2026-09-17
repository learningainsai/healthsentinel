import { Component, inject } from '@angular/core';
import { Staging } from '../../../core/staging';

@Component({
  selector: 'app-log-lab',
  templateUrl: './lab.html',
})
export class LogLab {
  private readonly staging = inject(Staging);

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.staging.addLabFile(file.name);
    input.value = '';
  }
}
