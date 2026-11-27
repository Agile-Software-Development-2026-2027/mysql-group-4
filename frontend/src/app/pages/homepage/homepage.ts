import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';
import { MissionDTO, MissionStatus } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { MissionService } from '../../services/mission.service';
import { DashboardNotification, NotificationService } from '../../services/notification.service';
import { NotificationBanners } from './components/notification-banners/notification-banners';

let mobileFocusDismissedInMemory = false;

function toNaiveIso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

@Component({
  selector: 'app-homepage',
  imports: [DatePipe, NgTemplateOutlet, RouterLink, Topbar, NotificationBanners],
  templateUrl: './homepage.html',
  styleUrl: './homepage.scss',
})
export class Homepage implements OnInit, OnDestroy {
  private missionService = inject(MissionService);
  private authService = inject(AuthService);
  private notificationService = inject(NotificationService);
  private router = inject(Router);

  siteName = 'MYSOL';
  readonly user = this.authService.currentUser;
  readonly notifications = this.notificationService.notifications;

  missionsLoading = signal(true);
  currentMission = signal<MissionDTO | null>(null);
  nextMission = signal<MissionDTO | null>(null);

  readonly isMobileDevice = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches;
  mobileFocusDismissed = signal(mobileFocusDismissedInMemory);
  selectedReceiptsCount = signal(0);
  readonly showMobileActiveFocus = computed(
    () => this.isMobileDevice && !this.mobileFocusDismissed() && !!this.currentMission()
  );

  dismissMobileFocus(): void {
    mobileFocusDismissedInMemory = true;
    this.mobileFocusDismissed.set(true);
  }

  onReceiptsSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedReceiptsCount.set(input.files?.length ?? 0);
  }

  onOpenNotification(item: DashboardNotification): void {
    this.notificationService.markAsSeen(item.refundId);
    this.router.navigate(['/missionreview'], {
      queryParams: { view: 'requester', missionId: item.missionId },
    });
  }

  onDismissNotification(refundId: string): void {
    this.notificationService.markAsSeen(refundId);
  }

  onDismissAllNotifications(): void {
    this.notificationService.markAllAsSeen();
  }

  ngOnDestroy(): void {
    if (!this.showMobileActiveFocus()) {
      this.notificationService.markVisibleAsSeenOnLeave();
    }
  }

  ngOnInit(): void {
    this.notificationService.refresh(false);
    const now = toNaiveIso(new Date());

    this.missionService
      .getMySentMissions({ status: MissionStatus.ACCEPTED, endsAtFrom: now })
      .subscribe({
        next: (page) => {
          const sorted = [...page.content].sort((a, b) => a.startsAt.localeCompare(b.startsAt));
          this.currentMission.set(sorted.find((m) => m.startsAt <= now) ?? null);
          this.nextMission.set(sorted.find((m) => m.startsAt > now) ?? null);
          this.missionsLoading.set(false);
        },
        error: () => {
          this.currentMission.set(null);
          this.nextMission.set(null);
          this.missionsLoading.set(false);
        },
      });
  }

  formatStartsIn(startsAt: string): string {
    const start = new Date(startsAt);
    const today = new Date();
    const startDay = new Date(start.getFullYear(), start.getMonth(), start.getDate());
    const todayDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const days = Math.round((startDay.getTime() - todayDay.getTime()) / 86_400_000);
    if (days <= 0) return 'Starts today';
    if (days === 1) return 'Starts tomorrow';
    if (days < 14) return `Starts in ${days} days`;
    if (days < 60) return `Starts in ${Math.round(days / 7)} weeks`;
    return `Starts in ${Math.round(days / 30)} months`;
  }
}
