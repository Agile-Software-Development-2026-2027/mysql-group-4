import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';
import { RefundApprovePayload, RefundItemDTO, RefundReviewDTO, RefundStatus } from '../../core/models';
import { RefundService } from '../../services/refund.service';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-refund-review',
  imports: [Topbar, DatePipe, DecimalPipe],
  templateUrl: './refund-review.html',
  styleUrl: './refund-review.scss',
})
export class RefundReview {
  private route = inject(ActivatedRoute);
  private refundService = inject(RefundService);
  private toastService = inject(ToastService);
  private sanitizer = inject(DomSanitizer);

  readonly refund = signal<RefundReviewDTO | null>(null);
  readonly loadError = signal(false);
  readonly expandedId = signal<string | null>(null);
  readonly refundableAmounts = signal<Record<string, number>>({});
  readonly notes = signal<Record<string, string>>({});
  readonly receipt = signal<{ itemId: string; url: SafeResourceUrl; fileURL: string; isPdf: boolean; filename: string } | null>(null);
  readonly confirmOpen = signal(false);

  readonly isEditable = computed(() => this.refund()?.status === RefundStatus.SUBMITTED);

  readonly totalRequested = computed(() =>
    (this.refund()?.items ?? []).reduce((sum, item) => sum + Number(item.requestedAmount), 0)
  );

  readonly totalRefund = computed(() =>
    Object.values(this.refundableAmounts()).reduce((sum, value) => sum + value, 0)
  );

  readonly exceedsEstimatedCost = computed(() => {
    const refund = this.refund();
    return !!refund && this.totalRequested() > Number(refund.mission.estimatedCost);
  });

  isNegative(item: RefundItemDTO): boolean {
    return (this.refundableAmounts()[item.id] ?? 0) < 0;
  }

  exceedsRequested(item: RefundItemDTO): boolean {
    return (this.refundableAmounts()[item.id] ?? 0) > Number(item.requestedAmount);
  }

  readonly canApprove = computed(() =>
    (this.refund()?.items ?? []).every((item) => {
      const amount = this.refundableAmounts()[item.id] ?? 0;
      return !this.isNegative(item) && !this.exceedsRequested(item);
    })
  );

  constructor() {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.refundService.getReview(id).subscribe({
      next: (refund) => {
        this.refund.set(refund);
        this.refundableAmounts.set(
          Object.fromEntries(
            refund.items
              .filter((item) => item.reimbursedAmount != null)
              .map((item) => [item.id, Number(item.reimbursedAmount)])
          )
        );
      },
      error: () => this.loadError.set(true),
    });
  }

  toggle(id: string): void {
    this.expandedId.update((current) => (current === id ? null : id));
  }

  setRefundable(id: string, value: string): void {
    this.refundableAmounts.update((amounts) => ({ ...amounts, [id]: Number(value) || 0 }));
  }

  setNote(id: string, value: string): void {
    this.notes.update((notes) => ({ ...notes, [id]: value }));
  }

  approve(): void {
    const refund = this.refund();
    if (!refund) return;
    this.confirmOpen.set(false);

    const payload: RefundApprovePayload = {
      items: refund.items.map((item) => ({
        itemId: item.id,
        reimbursedAmount: (this.refundableAmounts()[item.id] ?? 0).toFixed(2),
        adminNotes: this.notes()[item.id]?.trim() || null,
      })),
    };

    this.refundService.approve(refund.id, payload).subscribe((updated) => {
      this.refund.set(updated);
      this.expandedId.set(null);
    });
  }

  viewReceipt(item: RefundItemDTO): void {
    const refund = this.refund();
    if (!refund) return;
    this.refundService.downloadReceipt(refund.id, item.id).subscribe({
      next: (blob) => {
        const fileURL = URL.createObjectURL(blob);
        this.closeReceipt();
        this.receipt.set({
          itemId: item.id,
          url: this.sanitizer.bypassSecurityTrustResourceUrl(fileURL),
          fileURL,
          isPdf: blob.type === 'application/pdf',
          filename: item.receiptOriginalFilename,
        });
      },
      error: () => {
        this.toastService.showError('Could not open the receipt.', 'View Error');
      },
    });
  }

  closeReceipt(): void {
    const receipt = this.receipt();
    if (receipt) URL.revokeObjectURL(receipt.fileURL);
    this.receipt.set(null);
  }
}
