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
  readonly fullRefundIds = signal<Set<string>>(new Set());
  readonly notes = signal<Record<string, string>>({});
  readonly receipt = signal<{ itemId: string; url: SafeResourceUrl; fileURL: string; isPdf: boolean; filename: string } | null>(null);
  readonly confirmOpen = signal(false);
  readonly zoomed = signal(false);

  readonly isEditable = computed(() => this.refund()?.status === RefundStatus.SUBMITTED);

  readonly allFullRefundSelected = computed(() => {
    const items = this.refund()?.items ?? [];
    return items.length > 0 && items.every((item) => this.fullRefundIds().has(item.id));
  });

  readonly someFullRefundSelected = computed(() => {
    const items = this.refund()?.items ?? [];
    if (items.length === 0 || this.allFullRefundSelected()) return false;
    return items.some((item) => this.fullRefundIds().has(item.id) || this.isItemPartialRefund(item));
  });

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

    const item = this.refund()?.items.find((i) => i.id === id);
    const parsed = Number(sanitized);
    const isFull = !!item && sanitized !== '' && !Number.isNaN(parsed) && parsed === Number(item.requestedAmount);
    if (isFull !== this.fullRefundIds().has(id)) {
      this.fullRefundIds.update((prev) => {
        const next = new Set(prev);
        if (isFull) next.add(id);
        else next.delete(id);
        return next;
      });
    }
  }

  isItemFullRefund(id: string): boolean {
    return this.fullRefundIds().has(id);
  }

  isItemPartialRefund(item: RefundItemDTO): boolean {
    const amount = this.refundableAmounts()[item.id] ?? 0;
    return amount > 0 && amount < Number(item.requestedAmount);
  }

  toggleItemFullRefund(item: RefundItemDTO, checked: boolean): void {
    this.applyFullRefund([item], checked);
  }

  toggleAllFullRefund(checked: boolean): void {
    this.applyFullRefund(this.refund()?.items ?? [], checked);
  }

  private applyFullRefund(items: RefundItemDTO[], checked: boolean): void {
    const nextSelected = new Set(this.fullRefundIds());
    const nextInputs = { ...this.refundableInputs() };
    const nextAmounts = { ...this.refundableAmounts() };

    for (const item of items) {
      const amount = checked ? Number(item.requestedAmount) : 0;
      nextInputs[item.id] = checked ? amount.toFixed(2) : '';
      nextAmounts[item.id] = amount;
      if (checked) nextSelected.add(item.id);
      else nextSelected.delete(item.id);
    }

    this.fullRefundIds.set(nextSelected);
    this.refundableInputs.set(nextInputs);
    this.refundableAmounts.set(nextAmounts);
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
        this.fullRefundIds.set(new Set());
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
          url: this.sanitizer.bypassSecurityTrustResourceUrl(
            blob.type === 'application/pdf' ? `${fileURL}#toolbar=0&navpanes=0&view=FitH` : fileURL
          ),
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
    this.zoomed.set(false);
    this.receipt.set(null);
  }
}
