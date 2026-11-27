import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Subscription, interval, of } from 'rxjs';
import { catchError, finalize } from 'rxjs/operators';

import { RefundNotificationDTO } from '../core/models';
import { AuthService } from './auth.service';
import { RefundService } from './refund.service';
import { ToastService } from './toast.service';

export interface DashboardNotification {
  key: string;
  refundId: string;
  missionId: string;
  variant: 'success' | 'danger';
  title: string;
  message: string;
  feedback: string | null;
  approvedAt: string;
}

const POLL_INTERVAL_MS = 30_000;

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private authService = inject(AuthService);
  private refundService = inject(RefundService);
  private toastService = inject(ToastService);

  private pollSub: Subscription | null = null;
  private refreshSub: Subscription | null = null;
  private toastedKeys = new Set<string>();
  private pendingSeenIds = new Set<string>();
  private activeUserId: string | null = null;
  private initialLoadDone = false;

  readonly notifications = signal<DashboardNotification[]>([]);
  readonly unreadCount = computed(() => this.notifications().length);
  readonly hasUnread = computed(() => this.unreadCount() > 0);

  constructor() {
    effect(() => {
      const user = this.authService.currentUser();
      const isAdmin = this.authService.isAdmin();

      if (!user || isAdmin) {
        this.stopPolling();
        this.activeUserId = null;
        this.initialLoadDone = false;
        this.toastedKeys.clear();
        this.pendingSeenIds.clear();
        this.notifications.set([]);
        return;
      }

      if (this.activeUserId !== user.id) {
        this.stopPolling();
        this.activeUserId = user.id;
        this.initialLoadDone = false;
        this.toastedKeys.clear();
        this.pendingSeenIds.clear();
        this.notifications.set([]);
        this.startPolling();
      }
    });
  }

  refresh(emitToastForNew = false): void {
    const userId = this.activeUserId;
    if (!userId) {
      return;
    }

    this.refreshSub?.unsubscribe();
    const shouldEmitToast = emitToastForNew && this.initialLoadDone;

    this.refreshSub = this.refundService
      .getMyNotifications()
      .pipe(catchError(() => of(null)))
      .subscribe((items) => {
        if (this.activeUserId !== userId || items === null) {
          return;
        }

        const built = items
          .filter((dto) => !this.pendingSeenIds.has(dto.refundId))
          .map((dto) => this.buildRefundNotification(dto));
        const previousKeys = new Set(this.notifications().map((n) => n.key));
        this.notifications.set(built);
        this.initialLoadDone = true;

        if (shouldEmitToast) {
          for (const item of built) {
            if (!previousKeys.has(item.key) && !this.toastedKeys.has(item.key)) {
              this.toastedKeys.add(item.key);
              const detail = item.feedback ? `${item.message} Admin note: ${item.feedback}` : item.message;
              if (item.variant === 'success') {
                this.toastService.showSuccess(detail, item.title);
              } else {
                this.toastService.showError(detail, item.title);
              }
            }
          }
        } else {
          for (const item of built) {
            this.toastedKeys.add(item.key);
          }
        }
      });
  }

  markAsSeen(refundId: string): void {
    const user = this.authService.currentUser();
    this.notifications.update((list) => list.filter((item) => item.refundId !== refundId));
    if (!user || this.authService.isAdmin()) return;

    this.pendingSeenIds.add(refundId);
    this.refundService
      .markNotificationsSeen([refundId])
      .pipe(
        catchError(() => of(undefined)),
        finalize(() => this.pendingSeenIds.delete(refundId))
      )
      .subscribe();
  }

  markAllAsSeen(): void {
    const user = this.authService.currentUser();
    const ids = this.notifications().map((item) => item.refundId);
    this.notifications.set([]);
    if (!user || this.authService.isAdmin() || ids.length === 0) return;

    ids.forEach((id) => this.pendingSeenIds.add(id));
    this.refundService
      .markNotificationsSeen(ids)
      .pipe(
        catchError(() => of(undefined)),
        finalize(() => ids.forEach((id) => this.pendingSeenIds.delete(id)))
      )
      .subscribe();
  }

  markVisibleAsSeenOnLeave(): void {
    this.markAllAsSeen();
  }

  private startPolling(): void {
    this.stopPolling();
    this.refresh(false);
    this.pollSub = interval(POLL_INTERVAL_MS).subscribe(() => {
      if (typeof document === 'undefined' || !document.hidden) {
        this.refresh(true);
      }
    });
  }

  private stopPolling(): void {
    this.pollSub?.unsubscribe();
    this.pollSub = null;
    this.refreshSub?.unsubscribe();
    this.refreshSub = null;
  }

  private buildRefundNotification(dto: RefundNotificationDTO): DashboardNotification {
    const requested = Number(dto.totalRequestedAmount ?? 0);
    const reimbursed = Number(dto.totalReimbursedAmount ?? 0);
    const key = `refund:${dto.refundId}:${dto.approvedAt}`;
    const notes = (dto.adminNotes ?? []).map((n) => n.trim()).filter(Boolean);
    const feedback = notes.length > 0 ? notes.join(' · ') : null;

    const fmt = (val: number) =>
      val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    if (reimbursed === 0) {
      return {
        key,
        refundId: dto.refundId,
        missionId: dto.missionId,
        variant: 'danger',
        title: 'Refund Not Approved',
        message: `€ ${fmt(reimbursed)} out of € ${fmt(requested)} requested was refunded for "${dto.missionSubject}".`,
        feedback,
        approvedAt: dto.approvedAt,
      };
    }

    if (reimbursed >= requested && requested > 0) {
      return {
        key,
        refundId: dto.refundId,
        missionId: dto.missionId,
        variant: 'success',
        title: 'Refund Approved',
        message: `Your reimbursement of € ${fmt(reimbursed)} for "${dto.missionSubject}" has been approved.`,
        feedback,
        approvedAt: dto.approvedAt,
      };
    }

    return {
      key,
      refundId: dto.refundId,
      missionId: dto.missionId,
      variant: 'success',
      title: 'Refund Partially Approved',
      message: `€ ${fmt(reimbursed)} out of € ${fmt(requested)} requested was refunded for "${dto.missionSubject}".`,
      feedback,
      approvedAt: dto.approvedAt,
    };
  }
}
