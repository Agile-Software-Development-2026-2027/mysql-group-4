import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';

import { Topbar } from '../../components/topbar/topbar';
import { AddRefundItemModal } from './components/add-refund-item-modal/add-refund-item-modal';
import { RefundItemDTO } from '../../core/models';

@Component({
  selector: 'app-refund-request',
  standalone: true,
  imports: [CommonModule, Topbar, AddRefundItemModal],
  templateUrl: './refund-request.html',
  styleUrl: './refund-request.scss',
})
export class RefundRequestComponent implements OnInit {
  private route = inject(ActivatedRoute);

  refundId = signal<string | null>(null);
  isAddModalOpen = signal(false);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    this.refundId.set(id);
  }

  openAddModal(): void {
    this.isAddModalOpen.set(true);
  }

  closeAddModal(): void {
    this.isAddModalOpen.set(false);
  }

  onItemAdded(item: RefundItemDTO): void {
    console.log('Item added successfully:', item);
    this.closeAddModal();
  }
}
