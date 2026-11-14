import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule, DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { Topbar } from '../../components/topbar/topbar';
import { AddRefundItemModal } from './components/add-refund-item-modal/add-refund-item-modal';
import { ExpenseCategory, RefundItemDTO, RefundRequestDTO } from '../../core/models';
import { RefundService } from '../../services/refund.service';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-refund-request',
  standalone: true,
  imports: [CommonModule, DatePipe, DecimalPipe, Topbar, AddRefundItemModal],
  templateUrl: './refund-request.html',
  styleUrl: './refund-request.scss',
})
export class RefundRequestComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private refundService = inject(RefundService);
  private toastService = inject(ToastService);
  private sanitizer = inject(DomSanitizer);

  readonly refundId = signal<string | null>(null);
  readonly refund = signal<RefundRequestDTO | null>(null);
  readonly items = signal<RefundItemDTO[]>([]);
  readonly isLoading = signal(true);
  readonly loadError = signal(false);
  readonly expandedId = signal<string | null>(null);
  readonly activeReceipt = signal<{ item: RefundItemDTO; url: SafeResourceUrl; fileURL: string; isPdf: boolean } | null>(null);
  readonly isAddModalOpen = signal(false);

  readonly totalRequested = computed(() =>
    this.items().reduce((sum, item) => sum + Number(item.requestedAmount), 0)
  );

  readonly categoryTotals = computed(() => {
    const totals: Record<ExpenseCategory, number> = {
      [ExpenseCategory.TRANSPORT]: 0,
      [ExpenseCategory.ACCOMMODATION]: 0,
      [ExpenseCategory.MEALS]: 0,
      [ExpenseCategory.OTHER]: 0,
    };
    for (const item of this.items()) {
      totals[item.category] = (totals[item.category] ?? 0) + Number(item.requestedAmount);
    }
    return totals;
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    this.refundId.set(id);
    if (!id) {
      this.isLoading.set(false);
      this.loadError.set(true);
      return;
    }

    this.refundService.getById(id).subscribe({
      next: (data) => {
        this.refund.set(data);
        this.items.set(data.items ?? []);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.loadError.set(true);
      },
    });
  }

  ngOnDestroy(): void {
    this.closeReceipt();
  }

  toggleExpand(id: string): void {
    this.expandedId.update((curr) => (curr === id ? null : id));
  }

  viewReceipt(item: RefundItemDTO, event: Event): void {
    event.stopPropagation();
    const id = this.refundId();
    if (!id) return;

    if (this.activeReceipt()?.item.id === item.id) {
      this.closeReceipt();
      return;
    }

    this.refundService.downloadReceipt(id, item.id).subscribe({
      next: (blob) => {
        this.closeReceipt();
        const fileURL = URL.createObjectURL(blob);
        this.activeReceipt.set({
          item,
          url: this.sanitizer.bypassSecurityTrustResourceUrl(fileURL),
          fileURL,
          isPdf: blob.type === 'application/pdf',
        });
      },
      error: () => {
        this.toastService.showError('Could not load the receipt file.', 'Preview Error');
      },
    });
  }

  closeReceipt(): void {
    const current = this.activeReceipt();
    if (current) URL.revokeObjectURL(current.fileURL);
    this.activeReceipt.set(null);
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

  formatCategory(cat: ExpenseCategory): string {
    const labels: Record<ExpenseCategory, string> = {
      [ExpenseCategory.TRANSPORT]: 'Transport',
      [ExpenseCategory.ACCOMMODATION]: 'Accommodation',
      [ExpenseCategory.MEALS]: 'Meals',
      [ExpenseCategory.OTHER]: 'Other',
    };
    return labels[cat] ?? cat;
  }
}
