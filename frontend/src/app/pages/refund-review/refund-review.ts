import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';
import { RefundReviewDTO, RefundStatus } from '../../core/models';
import { RefundService } from '../../services/refund.service';

@Component({
  selector: 'app-refund-review',
  imports: [Topbar, DatePipe, DecimalPipe],
  templateUrl: './refund-review.html',
  styleUrl: './refund-review.scss',
})
export class RefundReview {
  private route = inject(ActivatedRoute);
  private refundService = inject(RefundService);

  readonly refund = signal<RefundReviewDTO | null>(null);
  readonly loadError = signal(false);
  readonly expandedId = signal<string | null>(null);
  readonly refundableAmounts = signal<Record<string, number>>({});

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
}
