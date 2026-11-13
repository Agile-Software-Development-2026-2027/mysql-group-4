import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule, DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';

import { Topbar } from '../../components/topbar/topbar';
import { AddRefundItemModal } from './components/add-refund-item-modal/add-refund-item-modal';
import { RefundItemDTO, RefundReviewDTO } from '../../core/models';
import { RefundService } from '../../services/refund.service';

@Component({
  selector: 'app-refund-request',
  standalone: true,
  imports: [CommonModule, DatePipe, DecimalPipe, Topbar, AddRefundItemModal],
  templateUrl: './refund-request.html',
  styleUrl: './refund-request.scss',
})
export class RefundRequestComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private refundService = inject(RefundService);

  refundId = signal<string | null>(null);
  refund = signal<RefundReviewDTO | null>(null);
  items = signal<RefundItemDTO[]>([]);
  isAddModalOpen = signal(false);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    this.refundId.set(id);
    if (id) {
      this.refundService.getReview(id).subscribe({
        next: (data) => {
          this.refund.set(data);
          this.items.set(data.items ?? []);
        },
      });
    }
  }

  openAddModal(): void {
    this.isAddModalOpen.set(true);
  }

  closeAddModal(): void {
    this.isAddModalOpen.set(false);
  }

  onItemAdded(item: RefundItemDTO): void {
    this.items.update((current) => [...current, item]);
    this.closeAddModal();
  }
}