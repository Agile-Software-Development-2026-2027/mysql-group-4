import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { concatMap, from, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Topbar } from '../../components/topbar/topbar';
import { MissionDTO, MissionStatus, RefundItemDTO, RefundRequestDTO, RefundStatus } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { MissionService } from '../../services/mission.service';
import { DashboardNotification, NotificationService } from '../../services/notification.service';
import { RefundService } from '../../services/refund.service';
import { ToastService } from '../../services/toast.service';
import { NotificationBanners } from './components/notification-banners/notification-banners';
import { QuickUploadReceiptModal } from './components/quick-upload-receipt-modal/quick-upload-receipt-modal';

let mobileFocusDismissedInMemory = false;

function toNaiveIso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

@Component({
  selector: 'app-homepage',
  imports: [DatePipe, NgTemplateOutlet, RouterLink, Topbar, NotificationBanners, QuickUploadReceiptModal],
  templateUrl: './homepage.html',
  styleUrl: './homepage.scss',
})
export class Homepage implements OnInit, OnDestroy {
  private missionService = inject(MissionService);
  private refundService = inject(RefundService);
  private toastService = inject(ToastService);
  private authService = inject(AuthService);
  private notificationService = inject(NotificationService);
  private router = inject(Router);

  siteName = 'MYSOL';
  readonly user = this.authService.currentUser;
  readonly notifications = this.notificationService.notifications;

  missionsLoading = signal(true);
  currentMission = signal<MissionDTO | null>(null);
  nextMission = signal<MissionDTO | null>(null);
  currentMissionRefund = signal<RefundRequestDTO | null>(null);
  refundLoading = signal(false);
  isQuickUploadOpen = signal(false);
  isMobileUploading = signal(false);

  readonly canUploadReceipts = computed(
    () => this.currentMissionRefund()?.status === RefundStatus.DRAFT
  );

  readonly isMobileDevice = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches;
  mobileFocusDismissed = signal(mobileFocusDismissedInMemory);
  selectedReceiptsCount = signal(0);
  readonly showMobileActiveFocus = computed(
    () =>
      this.isMobileDevice &&
      !this.mobileFocusDismissed() &&
      !!this.currentMission() &&
      this.canUploadReceipts()
  );

  dismissMobileFocus(): void {
    mobileFocusDismissedInMemory = true;
    this.mobileFocusDismissed.set(true);
  }

  openQuickUploadModal(event?: Event): void {
    event?.stopPropagation();
    if (!this.canUploadReceipts()) return;
    this.isQuickUploadOpen.set(true);
  }

  closeQuickUploadModal(): void {
    this.isQuickUploadOpen.set(false);
  }

  onReceiptUploaded(item: RefundItemDTO): void {
    this.currentMissionRefund.update((refund) =>
      refund ? { ...refund, items: [...(refund.items ?? []), item] } : refund
    );
  }

  onReceiptsSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = '';
    const refund = this.currentMissionRefund();
    if (!files.length || !refund || refund.status !== RefundStatus.DRAFT || this.isMobileUploading()) {
      return;
    }

    const allowed = ['.pdf', '.jpg', '.jpeg', '.png', '.webp'];
    const validFiles = files.filter(
      (f) => allowed.some((ext) => f.name.toLowerCase().endsWith(ext)) && f.size > 0 && f.size <= 10 * 1024 * 1024
    );
    if (validFiles.length === 0) {
      this.toastService.showError('Only non-empty PDF, JPG, PNG, or WEBP files up to 10MB are supported.', 'Invalid File');
      return;
    }

    this.selectedReceiptsCount.set(validFiles.length);
    this.isMobileUploading.set(true);
    let uploaded = 0;
    let failed = 0;

    from(validFiles)
      .pipe(
        concatMap((file) =>
          this.refundService.quickUploadReceipt(refund.id, file).pipe(
            catchError(() => {
              failed++;
              return of(null);
            })
          )
        )
      )
      .subscribe({
        next: (item) => {
          if (item) {
            uploaded++;
            this.onReceiptUploaded(item);
          }
        },
        complete: () => {
          this.isMobileUploading.set(false);
          if (uploaded > 0) {
            this.toastService.showSuccess(
              `${uploaded} ${uploaded === 1 ? 'receipt' : 'receipts'} uploaded and processed. Review them before submitting.`,
              'Receipts Uploaded'
            );
          }
          if (failed > 0) {
            this.toastService.showError(
              `${failed} ${failed === 1 ? 'file' : 'files'} could not be processed.`,
              'Upload Error'
            );
          }
        },
      });
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
          const active = sorted.find((m) => m.startsAt <= now) ?? null;
          this.currentMission.set(active);
          this.nextMission.set(sorted.find((m) => m.startsAt > now) ?? null);
          this.missionsLoading.set(false);
          if (active) {
            this.loadActiveMissionRefund(active.id);
          } else {
            this.currentMissionRefund.set(null);
          }
        },
        error: () => {
          this.currentMission.set(null);
          this.nextMission.set(null);
          this.currentMissionRefund.set(null);
          this.missionsLoading.set(false);
        },
      });
  }

  private loadActiveMissionRefund(missionId: string): void {
    this.refundLoading.set(true);
    this.refundService.getByMissionId(missionId).subscribe({
      next: (refund) => {
        this.currentMissionRefund.set(refund);
        this.refundLoading.set(false);
      },
      error: () => {
        this.currentMissionRefund.set(null);
        this.refundLoading.set(false);
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
