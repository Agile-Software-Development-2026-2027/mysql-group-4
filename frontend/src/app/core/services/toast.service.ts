import { Injectable, signal } from '@angular/core';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  title?: string;
  duration?: number;
}

@Injectable({
  providedIn: 'root',
})
export class ToastService {
  toasts = signal<Toast[]>([]);

  show(message: string, type: ToastType = 'info', title?: string, duration: number = 4000): void {
    const id = Math.random().toString(36).substring(2, 9);
    const toast: Toast = { id, type, message, title, duration };

    this.toasts.update((current) => [...current, toast]);

    if (duration > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, duration);
    }
  }

  showSuccess(message: string, title?: string, duration?: number): void {
    this.show(message, 'success', title ?? 'Success', duration);
  }

  showError(message: string, title?: string, duration?: number): void {
    this.show(message, 'error', title ?? 'Error', duration);
  }

  showInfo(message: string, title?: string, duration?: number): void {
    this.show(message, 'info', title, duration);
  }

  showWarning(message: string, title?: string, duration?: number): void {
    this.show(message, 'warning', title ?? 'Warning', duration);
  }

  dismiss(id: string): void {
    this.toasts.update((current) => current.filter((t) => t.id !== id));
  }
}
