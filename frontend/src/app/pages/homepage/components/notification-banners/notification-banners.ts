import { Component, input, output } from '@angular/core';
import { DashboardNotification } from '../../../../services/notification.service';

@Component({
  selector: 'app-notification-banners',
  standalone: true,
  templateUrl: './notification-banners.html',
  styleUrl: './notification-banners.scss',
})
export class NotificationBanners {
  readonly notifications = input<DashboardNotification[]>([]);

  readonly open = output<DashboardNotification>();
  readonly dismiss = output<string>();
  readonly dismissAll = output<void>();

  onCardClick(item: DashboardNotification): void {
    this.open.emit(item);
  }

  onDismissClick(key: string, event: Event): void {
    event.stopPropagation();
    this.dismiss.emit(key);
  }
}
