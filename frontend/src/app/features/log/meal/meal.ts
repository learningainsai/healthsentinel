import { Component, inject, signal } from '@angular/core';
import { Staging } from '../../../core/staging';

// Meal logging now supports both entry modes the backend's Vision agent and
// Nutrition agent expect: a photo (preferred — routed to gpt-4o-mini vision)
// and/or a free-text description. Previously only text was wired up here.
@Component({
  selector: 'app-log-meal',
  templateUrl: './meal.html',
})
export class LogMeal {
  private readonly staging = inject(Staging);

  protected readonly mealText = signal('');
  protected readonly photoFile = signal<File | null>(null);
  protected readonly photoPreviewUrl = signal<string | null>(null);

  protected onPhotoSelected(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.clearPreview();
    this.photoFile.set(file);
    if (file) {
      this.photoPreviewUrl.set(URL.createObjectURL(file));
    }
  }

  protected removePhoto(): void {
    this.clearPreview();
    this.photoFile.set(null);
  }

  protected addMeal(): void {
    const text = this.mealText().trim();
    const photo = this.photoFile();
    if (!text && !photo) return;

    this.staging.addMeal({ text, photoName: photo?.name });

    this.mealText.set('');
    this.removePhoto();
  }

  private clearPreview(): void {
    const url = this.photoPreviewUrl();
    if (url) URL.revokeObjectURL(url);
    this.photoPreviewUrl.set(null);
  }
}
