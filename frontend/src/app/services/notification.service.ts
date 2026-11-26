import { Injectable, Injector, computed, effect, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subscription, forkJoin, interval, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { MissionDTO, RefundRequestDTO, RefundStatus } from '../core/models';
import { AuthService } from './auth.service';
import { MissionService } from './mission.service';
import { RefundService } from './refund.service';
import { ToastService } from './toast.service';

export interface DashboardNotification {
  key: string;
  variant: 'success' | 'danger';
  title: string;
  message: string;
  feedback: string | null;
  approvedAt: string;
  mission: MissionDTO;
  refundId: string;
}

const POLL_INTERVAL_MS = 30_000;

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private injector = inject(Injector);
  private http = inject(HttpClient, { optional: true });
  private toastService = inject(ToastService);

  private pollSub: Subscription | null = null;
  private toastedKeys = new Set<string>();
  private activeUserId: string | null = null;
  private isRefreshing = false;

  readonly notifications = signal<DashboardNotification[]>([]);
  readonly unreadCount = computed(() => this.notifications().length);
  readonly hasUnread = computed(() => this.unreadCount() > 0);

  constructor() {
    if (!this.http) {
      return;
    }

    const authService = this.injector.get(AuthService);

    effect(() => {
      const user = authService.currentUser();
      const isAdmin = authService.isAdmin();

      if (!user || isAdmin) {
        this.stopPolling();
        this.activeUserId = null;
        this.toastedKeys.clear();
        this.notifications.set([]);
        return;
      }

      if (this.activeUserId !== user.id) {
        this.activeUserId = user.id;
        this.toastedKeys.clear();
        this.startPolling();
      }
    });
  }

  refresh(emitToastForNew = false): void {
    if (!this.http || !this.activeUserId || this.isRefreshing) {
      return;
    }

    const userId = this.activeUserId;
    const missionService = this.injector.get(MissionService);
    const refundService = this.injector.get(RefundService);

    this.isRefreshing = true;
    missionService
      .getMyCompletedMissions()
      .pipe(catchError(() => of(null)))
      .subscribe((page) => {
        if (this.activeUserId !== userId) {
          this.isRefreshing = false;
          return;
        }

        const completedMissions = page?.content ?? [];
        if (completedMissions.length === 0) {
          this.notifications.set([]);
          this.isRefreshing = false;
          return;
        }

        forkJoin(
          completedMissions.map((mission) =>
            refundService.getByMissionId(mission.id).pipe(
              catchError(() => of(null))
            )
          )
        ).subscribe({
          next: (refunds) => {
            this.isRefreshing = false;
            if (this.activeUserId !== userId) {
              return;
            }

            const seenMap = this.loadSeenMap(userId);
            const built: DashboardNotification[] = [];

            completedMissions.forEach((mission, index) => {
              const refund = refunds[index];
              if (!refund || refund.status !== RefundStatus.APPROVED) {
                return;
              }
              const notification = this.buildRefundNotification(mission, refund);
              if (!seenMap[notification.key]) {
                built.push(notification);
              }
            });

            built.sort((a, b) => b.approvedAt.localeCompare(a.approvedAt));

            const previousKeys = new Set(this.notifications().map((n) => n.key));
            this.notifications.set(built);

            if (emitToastForNew) {
              for (const item of built) {
                if (!previousKeys.has(item.key) && !this.toastedKeys.has(item.key)) {
                  this.toastedKeys.add(item.key);
                  if (item.variant === 'success') {
                    this.toastService.showSuccess(item.message, item.title);
                  } else {
                    const detail = item.feedback ? `${item.message} ${item.feedback}` : item.message;
                    this.toastService.showError(detail, item.title);
                  }
                }
              }
            } else {
              for (const item of built) {
                this.toastedKeys.add(item.key);
              }
            }
          },
          error: () => {
            this.isRefreshing = false;
          },
        });
      });
  }

  markAsSeen(key: string): void {
    const userId = this.activeUserId;
    if (userId) {
      const seenMap = this.loadSeenMap(userId);
      seenMap[key] = new Date().toISOString();
      this.saveSeenMap(userId, seenMap);
    }
    this.notifications.update((list) => list.filter((item) => item.key !== key));
  }

  markAllAsSeen(): void {
    const userId = this.activeUserId;
    const current = this.notifications();
    if (userId && current.length > 0) {
      const seenMap = this.loadSeenMap(userId);
      const now = new Date().toISOString();
      for (const item of current) {
        seenMap[item.key] = now;
      }
      this.saveSeenMap(userId, seenMap);
    }
    this.notifications.set([]);
  }

  private startPolling(): void {
    this.stopPolling();
    this.refresh(false);
    this.pollSub = interval(POLL_INTERVAL_MS).subscribe(() => {
      this.refresh(true);
    });
  }

  private stopPolling(): void {
    this.pollSub?.unsubscribe();
    this.pollSub = null;
  }

  private buildRefundNotification(mission: MissionDTO, refund: RefundRequestDTO): DashboardNotification {
    const requested = Number(refund.totalRequestedAmount ?? 0);
    const reimbursed = Number(refund.totalReimbursedAmount ?? 0);
    const approvedAt = refund.approvedAt ?? refund.updatedAt;
    const key = `refund:${refund.id}:${approvedAt}`;

    const isFullRefund = reimbursed >= requested && requested > 0;
    const notes = (refund.items ?? [])
      .map((item) => item.adminNotes?.trim())
      .filter((note): note is string => Boolean(note));
    const feedback = notes.length > 0 ? notes.join(' · ') : null;

    const fmt = (val: number) =>
      val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    if (reimbursed === 0) {
      return {
        key,
        variant: 'danger',
        title: 'Refund Not Approved (€ 0.00)',
        message: `€ ${fmt(reimbursed)} out of € ${fmt(requested)} requested was refunded for "${mission.subject}".`,
        feedback,
        approvedAt,
        mission,
        refundId: refund.id,
      };
    }

    if (isFullRefund) {
      return {
        key,
        variant: 'success',
        title: 'Refund Approved',
        message: `Your reimbursement of € ${fmt(reimbursed)} for "${mission.subject}" has been approved.`,
        feedback,
        approvedAt,
        mission,
        refundId: refund.id,
      };
    }

    return {
      key,
      variant: 'success',
      title: 'Refund Partially Approved',
      message: `€ ${fmt(reimbursed)} out of € ${fmt(requested)} requested was refunded for "${mission.subject}".`,
      feedback,
      approvedAt,
      mission,
      refundId: refund.id,
    };
  }

  private storageKey(userId: string): string {
    return `mysol_seen_notifications_${userId}`;
  }

  private loadSeenMap(userId: string): Record<string, string> {
    if (typeof localStorage === 'undefined') {
      return {};
    }
    try {
      const raw = localStorage.getItem(this.storageKey(userId));
      return raw ? (JSON.parse(raw) as Record<string, string>) : {};
    } catch {
      return {};
    }
  }

  private saveSeenMap(userId: string, map: Record<string, string>): void {
    if (typeof localStorage === 'undefined') {
      return;
    }
    try {
      localStorage.setItem(this.storageKey(userId), JSON.stringify(map));
    } catch {
      // Ignore storage quota / privacy mode errors
    }
  }
}
