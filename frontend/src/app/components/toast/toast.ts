import { Component, inject } from '@angular/core';
import { ToastService, Toast } from '../../services/toast.service';

@Component({
  selector: 'app-toast',
  standalone: true,
  templateUrl: './toast.html',
  styleUrl: './toast.scss',
})
export class ToastComponent {
  protected toastService = inject(ToastService);

  dismiss(toast: Toast): void {
    this.toastService.dismiss(toast.id);
  }
}
