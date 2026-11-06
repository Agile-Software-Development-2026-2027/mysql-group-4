import { Component, computed, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { Topbar } from '../../components/topbar/topbar';

@Component({
  selector: 'app-refund-review',
  imports: [Topbar, DatePipe, DecimalPipe],
  templateUrl: './refund-review.html',
  styleUrl: './refund-review.scss',
})
export class RefundReview {
  // Mock data: will be replaced by the backend call
  readonly refund = signal({
    status: 'SUBMITTED',
    requester: { name: 'Mario', surname: 'Rossi', department: 'DEMACS' },
    mission: { subject: 'Software Engineering Conference', destination: 'London', estimatedCost: 500 },
    expenses: [
      { id: 'e1', category: 'Transport', transportMode: 'Flight', description: 'Outbound flight', date: '2026-11-10', amount: 180, currency: 'EUR', traceable: true, receiptUrl: '#' },
      { id: 'e2', category: 'Accommodation', transportMode: '', description: 'Hotel, 2 nights', date: '2026-11-10', amount: 320, currency: 'EUR', traceable: true, receiptUrl: '#' },
      { id: 'e3', category: 'Meal', transportMode: '', description: 'Lunch', date: '2026-11-11', amount: 25.5, currency: 'EUR', traceable: false, receiptUrl: '#' },
      { id: 'e4', category: 'Meal', transportMode: '', description: 'Dinner', date: '2026-11-11', amount: 32, currency: 'EUR', traceable: true, receiptUrl: '#' },
    ],
  });

  readonly expandedId = signal<string | null>(null);

  readonly totalRequested = computed(() =>
    this.refund().expenses.reduce((sum, e) => sum + e.amount, 0)
  );
  readonly refundableAmounts = signal<Record<string, number>>({});
  readonly totalRefund = computed(() =>
    Object.values(this.refundableAmounts()).reduce((sum, value) => sum + value, 0)
  );
  readonly notRefundable = computed(() => this.totalRequested()-this.totalRefund() );

  readonly exceedsEstimatedCost = computed(
    () => this.totalRequested() > this.refund().mission.estimatedCost
  );

  toggle(id: string): void {
    this.expandedId.update((current) => (current === id ? null : id));
  }
  setRefundable(id: string, value: string): void {
    this.refundableAmounts.update((amounts) => ({ ...amounts, [id]: Number(value) || 0 }));
  }
}
