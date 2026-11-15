import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule, DatePipe, DecimalPipe, Location } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { Topbar } from '../../components/topbar/topbar';
import { AddRefundItemModal } from './components/add-refund-item-modal/add-refund-item-modal';
import { API_CONFIG } from '../../core/config/api.config';
import { ExpenseCategory, ExpenseSubtype, MissionDTO, RefundItemDTO, RefundItemFilterPayload, RefundRequestDTO } from '../../core/models';
import { RefundService } from '../../services/refund.service';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-refund-request',
  standalone: true,
  imports: [CommonModule, DatePipe, DecimalPipe, ReactiveFormsModule, RouterLink, Topbar, AddRefundItemModal],
  templateUrl: './refund-request.html',
  styleUrl: './refund-request.scss',
})
export class RefundRequestComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private location = inject(Location);
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);
  private refundService = inject(RefundService);
  private toastService = inject(ToastService);
  private sanitizer = inject(DomSanitizer);

  readonly ExpenseCategory = ExpenseCategory;
  readonly subtypeMap: Record<ExpenseCategory, { value: ExpenseSubtype; label: string }[]> = {
    [ExpenseCategory.TRANSPORT]: [
      { value: ExpenseSubtype.TRAIN, label: 'Train' },
      { value: ExpenseSubtype.PLANE, label: 'Plane' },
      { value: ExpenseSubtype.SHIP, label: 'Ship / Ferry' },
      { value: ExpenseSubtype.PUBLIC_TRANSPORT, label: 'Public Transit' },
      { value: ExpenseSubtype.TAXI_RENTAL, label: 'Taxi / Car Rental' },
      { value: ExpenseSubtype.OWN_VEHICLE, label: 'Personal Vehicle' },
    ],
    [ExpenseCategory.ACCOMMODATION]: [
      { value: ExpenseSubtype.ACCOMMODATION_EXPENSE, label: 'Hotel / Lodging' },
      { value: ExpenseSubtype.OTHER_ACCOMMODATION_EXPENSE, label: 'Other Accommodation' },
    ],
    [ExpenseCategory.MEALS]: [
      { value: ExpenseSubtype.MEALS_EXPENSE, label: 'Restaurant / Meal' },
      { value: ExpenseSubtype.OTHER_MEALS_EXPENSE, label: 'Other Meal' },
    ],
    [ExpenseCategory.OTHER]: [],
  };

  readonly refundId = signal<string | null>(null);
  readonly refund = signal<RefundRequestDTO | null>(null);
  readonly mission = signal<MissionDTO | null>(null);
  readonly items = signal<RefundItemDTO[]>([]);
  readonly isLoading = signal(true);
  readonly loadError = signal(false);
  readonly isAddModalOpen = signal(false);

  readonly selectedItem = signal<RefundItemDTO | null>(null);
  readonly isReceiptLoading = signal(false);
  readonly receiptError = signal(false);
  readonly receiptPreview = signal<{ url: SafeResourceUrl; fileURL: string; isPdf: boolean; filename: string } | null>(null);

  editForm: FormGroup = this.fb.group({
    category: [ExpenseCategory.TRANSPORT, Validators.required],
    subtype: [null],
    itineraryFrom: [''],
    itineraryTo: [''],
    startsAt: ['', Validators.required],
    endsAt: [''],
    requestedAmount: [null, [Validators.required, Validators.min(0.01), Validators.max(10000)]],
    isTraceable: [true],
    description: ['', [Validators.required, Validators.maxLength(255)]],
  });

  readonly totalRequested = computed(() =>
    this.items().reduce((sum, item) => sum + Number(item.requestedAmount), 0)
  );

  readonly categoryTotals = computed(() => {
    const totals: Record<ExpenseCategory, number> = {
      [ExpenseCategory.TRANSPORT]: 0, [ExpenseCategory.ACCOMMODATION]: 0,
      [ExpenseCategory.MEALS]: 0, [ExpenseCategory.OTHER]: 0,
    };
    for (const item of this.items()) {
      totals[item.category] = (totals[item.category] ?? 0) + Number(item.requestedAmount);
    }
    return totals;
  });

  readonly exceedsEstimatedCost = computed(() => {
    const est = this.mission()?.estimatedCost;
    return est != null && this.totalRequested() > Number(est);
  });

  readonly categories: ExpenseCategory[] = [
    ExpenseCategory.TRANSPORT,
    ExpenseCategory.ACCOMMODATION,
    ExpenseCategory.MEALS,
    ExpenseCategory.OTHER,
  ];
  readonly selectedCategories = signal<Set<ExpenseCategory>>(new Set(this.categories));
  readonly priceSort = signal<'none' | 'asc' | 'desc'>('none');

  readonly categoryCounts = computed(() => {
    const counts: Record<ExpenseCategory, number> = {
      [ExpenseCategory.TRANSPORT]: 0,
      [ExpenseCategory.ACCOMMODATION]: 0,
      [ExpenseCategory.MEALS]: 0,
      [ExpenseCategory.OTHER]: 0,
    };
    for (const item of this.items()) {
      counts[item.category] = (counts[item.category] ?? 0) + 1;
    }
    return counts;
  });

  readonly isAllCategoriesSelected = computed(
    () => this.selectedCategories().size === this.categories.length
  );

  readonly filteredItems = signal<RefundItemDTO[]>([]);
  readonly isFiltering = signal(true);
  readonly pageSize = 5;
  readonly skeletonPlaceholders = [1, 2, 3, 4, 5];
  readonly currentPage = signal(0);
  readonly totalPages = signal(0);
  readonly totalFilteredCount = signal(0);
  readonly mathMin = Math.min;

  goToPage(page: number): void {
    if (page < 0 || page >= this.totalPages()) return;
    this.currentPage.set(page);
    this.loadFilteredItems(false);
  }

  selectAllCategories(): void {
    this.selectedCategories.set(new Set(this.categories));
    this.loadFilteredItems(true);
  }

  loadFilteredItems(resetPage: boolean = false): void {
    const id = this.refundId();
    if (!id) return;

    if (resetPage) {
      this.currentPage.set(0);
    }

    const active = this.selectedCategories();
    if (active.size === 0) {
      this.filteredItems.set([]);
      this.totalPages.set(0);
      this.totalFilteredCount.set(0);
      this.isFiltering.set(false);
      return;
    }

    const payload: RefundItemFilterPayload = {
      categories: active.size === this.categories.length ? null : Array.from(active),
      sortByAmount: this.priceSort() === 'asc' ? 'asc' : this.priceSort() === 'desc' ? 'desc' : null,
    };

    this.isFiltering.set(true);
    this.refundService.filterItems(id, payload, this.currentPage(), this.pageSize).subscribe({
      next: (page) => {
        this.filteredItems.set(page.content);
        this.totalPages.set(page.totalPages);
        this.totalFilteredCount.set(page.totalElements);
        this.currentPage.set(page.number);
        this.isFiltering.set(false);
      },
      error: () => {
        this.isFiltering.set(false);
        this.toastService.showError('Could not filter receipt items.', 'Filter Error');
      },
    });
  }

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
        this.loadFilteredItems();
        this.http
          .get<MissionDTO>(`${API_CONFIG.baseUrl}/api/v1/missions/${data.missionId}`, { withCredentials: true })
          .subscribe({ next: (m) => this.mission.set(m) });
      },
      error: () => {
        this.isLoading.set(false);
        this.loadError.set(true);
      },
    });
  }

  ngOnDestroy(): void { this.revokePreviewUrl(); }

  openItemModal(item: RefundItemDTO): void {
    const id = this.refundId();
    this.selectedItem.set(item);
    this.editForm.reset({
      category: item.category,
      subtype: item.subtype ?? null,
      itineraryFrom: item.itineraryFrom ?? '',
      itineraryTo: item.itineraryTo ?? '',
      startsAt: this.toInputDateTime(item.startsAt),
      endsAt: this.toInputDateTime(item.endsAt),
      requestedAmount: Number(item.requestedAmount),
      isTraceable: item.isTraceable,
      description: item.description,
    });
    this.revokePreviewUrl();
    this.receiptError.set(false);
    if (!id) return;

    this.isReceiptLoading.set(true);
    this.refundService.downloadReceipt(id, item.id).subscribe({
      next: (blob) => {
        const fileURL = URL.createObjectURL(blob);
        this.receiptPreview.set({
          url: this.sanitizer.bypassSecurityTrustResourceUrl(fileURL),
          fileURL,
          isPdf: blob.type === 'application/pdf',
          filename: item.receiptOriginalFilename,
        });
        this.isReceiptLoading.set(false);
      },
      error: () => {
        this.isReceiptLoading.set(false);
        this.receiptError.set(true);
        this.toastService.showError('Could not load the receipt file.', 'Preview Error');
      },
    });
  }

  get currentSubtypes(): { value: ExpenseSubtype; label: string }[] {
    const cat = this.editForm.get('category')?.value as ExpenseCategory | null;
    return cat ? this.subtypeMap[cat] ?? [] : [];
  }

  onEditCategoryChange(): void {
    const cat = this.editForm.get('category')?.value as ExpenseCategory;
    const options = this.subtypeMap[cat] ?? [];
    this.editForm.patchValue({
      subtype: options[0]?.value ?? null,
      itineraryFrom: cat === ExpenseCategory.TRANSPORT ? this.editForm.value.itineraryFrom : '',
      itineraryTo: cat === ExpenseCategory.TRANSPORT ? this.editForm.value.itineraryTo : '',
      endsAt: cat === ExpenseCategory.TRANSPORT || cat === ExpenseCategory.ACCOMMODATION ? this.editForm.value.endsAt : '',
    });
  }

  onReplaceReceipt(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.revokePreviewUrl();
    this.receiptError.set(false);
    const fileURL = URL.createObjectURL(file);
    this.receiptPreview.set({
      url: this.sanitizer.bypassSecurityTrustResourceUrl(fileURL),
      fileURL,
      isPdf: file.type === 'application/pdf',
      filename: file.name,
    });
  }

  saveItemChanges(): void {
    const current = this.selectedItem();
    if (!current || this.editForm.invalid) {
      this.editForm.markAllAsTouched();
      return;
    }
    const v = this.editForm.value;
    const cat = v.category as ExpenseCategory;
    const updated: RefundItemDTO = {
      ...current,
      category: cat,
      subtype: cat === ExpenseCategory.OTHER ? null : v.subtype,
      itineraryFrom: cat === ExpenseCategory.TRANSPORT ? v.itineraryFrom?.trim() || null : null,
      itineraryTo: cat === ExpenseCategory.TRANSPORT ? v.itineraryTo?.trim() || null : null,
      startsAt: v.startsAt,
      endsAt: cat === ExpenseCategory.TRANSPORT || cat === ExpenseCategory.ACCOMMODATION ? v.endsAt || null : null,
      requestedAmount: Number(v.requestedAmount),
      isTraceable: Boolean(v.isTraceable),
      description: String(v.description).trim(),
      receiptOriginalFilename: this.receiptPreview()?.filename ?? current.receiptOriginalFilename,
    };
    this.items.update((list) => list.map((it) => (it.id === updated.id ? updated : it)));
    this.toastService.showSuccess('Expense item updated.', 'Saved');
    this.closeItemModal();
  }

  closeItemModal(): void {
    this.selectedItem.set(null);
    this.isReceiptLoading.set(false);
    this.receiptError.set(false);
    this.revokePreviewUrl();
  }

  private revokePreviewUrl(): void {
    const current = this.receiptPreview();
    if (current) URL.revokeObjectURL(current.fileURL);
    this.receiptPreview.set(null);
  }

  private toInputDateTime(val?: string | null): string {
    return val ? val.slice(0, 16) : '';
  }

  isCategorySelected(cat: ExpenseCategory): boolean {
    return this.selectedCategories().has(cat);
  }

  toggleCategory(cat: ExpenseCategory): void {
    this.selectedCategories.update((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
    this.loadFilteredItems(true);
  }

  setPriceSort(order: string): void {
    this.priceSort.set(order === 'asc' || order === 'desc' ? order : 'none');
    this.loadFilteredItems(true);
  }

  resetFilters(): void {
    this.selectedCategories.set(new Set(this.categories));
    this.priceSort.set('none');
    this.loadFilteredItems(true);
  }

  deleteItem(item: RefundItemDTO, event: Event): void {
    event.stopPropagation();
    this.items.update((list) => list.filter((it) => it.id !== item.id));
    if (this.selectedItem()?.id === item.id) this.closeItemModal();
    this.toastService.showSuccess('Expense item removed.', 'Deleted');
  }

  goBack(): void {
    if (window.history.length > 1) {
      this.location.back();
    } else {
      this.router.navigate(['/']);
    }
  }

  openAddModal(): void { this.isAddModalOpen.set(true); }
  closeAddModal(): void { this.isAddModalOpen.set(false); }
  onItemAdded(item: RefundItemDTO): void {
    this.items.update((current) => [...current, item]);
    this.closeAddModal();
    this.loadFilteredItems();
  }

  formatCategory(cat: ExpenseCategory): string {
    const labels: Record<ExpenseCategory, string> = {
      [ExpenseCategory.TRANSPORT]: 'Transport', [ExpenseCategory.ACCOMMODATION]: 'Accommodation',
      [ExpenseCategory.MEALS]: 'Meals', [ExpenseCategory.OTHER]: 'Other',
    };
    return labels[cat] ?? cat;
  }
}
