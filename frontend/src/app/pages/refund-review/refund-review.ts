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
  readonly refundableInputs = signal<Record<string, string>>({});
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
        const initialInputs = Object.fromEntries(
          refund.items
            .filter((item) => item.reimbursedAmount != null)
            .map((item) => [item.id, String(item.reimbursedAmount)])
        );
        this.refundableInputs.set(initialInputs);
        this.refundableAmounts.set(
          Object.fromEntries(
            Object.entries(initialInputs).map(([id, val]) => [id, Number(val) || 0])
          )
        );
      },
      error: () => this.loadError.set(true),
    });
  }

  toggle(id: string): void {
    this.expandedId.update((current) => (current === id ? null : id));
  }

  allowDigitsAndDot(event: KeyboardEvent): void {
    if (event.ctrlKey || event.metaKey || event.altKey || event.key.length > 1) {
      return;
    }
    const input = event.target as HTMLInputElement;
    if (!/^[0-9.]$/.test(event.key) || (event.key === '.' && input.value.includes('.'))) {
      event.preventDefault();
    }
  }

  setRefundable(id: string, input: HTMLInputElement): void {
    const cleaned = input.value.replace(/[^0-9.]/g, '');
    const dotIndex = cleaned.indexOf('.');

    let intPart = dotIndex === -1 ? cleaned : cleaned.slice(0, dotIndex);
    let decPart = dotIndex === -1 ? '' : cleaned.slice(dotIndex + 1).replace(/\./g, '');

    // Match backend Numeric(12, 2): max 10 integer digits and 2 decimal digits
    if (intPart.length > 10) {
      intPart = intPart.slice(0, 10);
    }
    if (decPart.length > 2) {
      decPart = decPart.slice(0, 2);
    }

    const sanitized = dotIndex === -1 ? intPart : `${intPart}.${decPart}`;
    if (sanitized !== input.value) {
      input.value = sanitized;
    }

    this.refundableInputs.update((inputs) => ({ ...inputs, [id]: sanitized }));
    this.refundableAmounts.update((amounts) => ({ ...amounts, [id]: Number(sanitized) || 0 }));
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

    this.refundService.approve(refund.id, payload).subscribe({
      next: (updated) => {
        this.refund.set(updated);
        this.expandedId.set(null);
      },
      error: (err) => {
        this.toastService.showError(err?.error?.message ?? 'Could not approve the refund.', 'Approval Error');
      },
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
