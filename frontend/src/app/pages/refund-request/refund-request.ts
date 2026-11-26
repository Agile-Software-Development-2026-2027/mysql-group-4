import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule, DatePipe, DecimalPipe, Location } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import {
  AbstractControl,
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { Topbar } from '../../components/topbar/topbar';
import { AddRefundItemModal } from './components/add-refund-item-modal/add-refund-item-modal';
import { AddMultipleReceiptsModel } from './components/add-multiple-receipts-model/add-multiple-receipts-model';
import { API_CONFIG } from '../../core/config/api.config';
import { ExpenseCategory, ExpenseSubtype, MissionDTO, RefundItemDTO, RefundItemFilterPayload, RefundItemUpdatePayload, RefundRequestDTO, RefundStatus } from '../../core/models';
import { RefundService } from '../../services/refund.service';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-refund-request',
  standalone: true,
  imports: [CommonModule, DatePipe, DecimalPipe, ReactiveFormsModule, RouterLink, Topbar, AddRefundItemModal, AddMultipleReceiptsModel],
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
  readonly isBatchModalOpen = signal(false);

  readonly selectedItem = signal<RefundItemDTO | null>(null);
  readonly isReceiptLoading = signal(false);
  readonly isSaving = signal(false);
  readonly receiptError = signal(false);
  readonly receiptPreview = signal<{ url: SafeResourceUrl; fileURL: string; isPdf: boolean; filename: string } | null>(null);
  readonly replacementFile = signal<File | null>(null);
  readonly isSubmitting = signal(false);
  readonly confirmSubmitOpen = signal(false);
  readonly isDraft = computed(() => this.refund()?.status === RefundStatus.DRAFT);
  readonly isMissionEnded = computed(() => {
    const m = this.mission();
    return m ? new Date(m.endsAt) <= new Date() : false;
  });
  readonly pendingReviewCount = computed(() => this.items().filter((it) => it.needsReview).length);
  readonly hasItemsPendingReview = computed(() => this.pendingReviewCount() > 0);

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
  }, { validators: [this.dateConsistencyValidator()] });

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

  readonly missionMinDateTime = computed(() => this.toInputDateTime(this.mission()?.startsAt) || null);
  readonly missionMaxDateTime = computed(() => this.toInputDateTime(this.mission()?.endsAt) || null);
  readonly missionPeriodLabel = computed(() => {
    const m = this.mission();
    if (!m?.startsAt || !m?.endsAt) return '';
    const fmt = (val: string) => new Date(val).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
    return `${fmt(m.startsAt)} – ${fmt(m.endsAt)}`;
  });

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
        if (page.content.length === 0 && page.totalPages > 0 && page.number >= page.totalPages) {
          this.currentPage.set(page.totalPages - 1);
          this.loadFilteredItems(false);
          return;
        }
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
          .subscribe({
            next: (m) => {
              this.mission.set(m);
              this.editForm.updateValueAndValidity();
            },
          });
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
    this.replacementFile.set(null);
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
    this.updateFormValidators(item.category);
    if (!this.isDraft()) {
      this.editForm.disable();
    } else {
      this.editForm.enable();
    }
    this.revokePreviewUrl();
    this.receiptError.set(false);
    if (!id || !item.receiptFilePath) return;

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

  private updateFormValidators(cat: ExpenseCategory): void {
    const [sub, from, to, end] = ['subtype', 'itineraryFrom', 'itineraryTo', 'endsAt'].map((k) => this.editForm.get(k));
    [sub, from, to, end].forEach((c) => c?.clearValidators());
    if (cat === ExpenseCategory.TRANSPORT) {
      [sub, from, to, end].forEach((c) => c?.setValidators([Validators.required]));
    } else if (cat === ExpenseCategory.ACCOMMODATION) {
      [sub, end].forEach((c) => c?.setValidators([Validators.required]));
    } else if (cat === ExpenseCategory.MEALS) {
      sub?.setValidators([Validators.required]);
    }
    [sub, from, to, end].forEach((c) => c?.updateValueAndValidity());
  }

  onEditCategoryChange(): void {
    const cat = this.editForm.get('category')?.value as ExpenseCategory;
    const options = this.subtypeMap[cat] ?? [];
    this.editForm.patchValue({
      subtype: cat === ExpenseCategory.OTHER ? null : options[0]?.value ?? null,
      itineraryFrom: cat === ExpenseCategory.TRANSPORT ? this.editForm.value.itineraryFrom : '',
      itineraryTo: cat === ExpenseCategory.TRANSPORT ? this.editForm.value.itineraryTo : '',
      endsAt: cat === ExpenseCategory.TRANSPORT || cat === ExpenseCategory.ACCOMMODATION ? this.editForm.value.endsAt : '',
    });
    this.updateFormValidators(cat);
  }

  onReplaceReceipt(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.replacementFile.set(file);
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

  private formatToIso(val?: string | null): string | null {
    if (!val) return null;
    const trimmed = val.trim();
    return trimmed.length === 16 ? `${trimmed}:00` : (trimmed || null);
  }

  private isOutsideMission(val: string | null): boolean {
    const m = this.mission();
    if (!val || !m?.startsAt || !m?.endsAt) return false;
    const date = new Date(val);
    const missionStart = new Date(m.startsAt);
    const missionEnd = new Date(m.endsAt);
    missionStart.setSeconds(0, 0);
    missionEnd.setSeconds(59, 999);
    return date < missionStart || date > missionEnd;
  }

  private dateConsistencyValidator(): ValidatorFn {
    return (group: AbstractControl): ValidationErrors | null => {
      const errors: ValidationErrors = {};
      const category = group.get('category')?.value as ExpenseCategory;
      const startsAt = group.get('startsAt')?.value as string | null;
      const endsAt = group.get('endsAt')?.value as string | null;

      if (this.isOutsideMission(startsAt)) {
        errors['startOutsideMission'] = true;
      }
      if (category === ExpenseCategory.TRANSPORT || category === ExpenseCategory.ACCOMMODATION) {
        if (this.isOutsideMission(endsAt)) {
          errors['endOutsideMission'] = true;
        }
        if (startsAt && endsAt && new Date(endsAt) <= new Date(startsAt)) {
          errors['endBeforeStart'] = true;
        }
      }
      return Object.keys(errors).length > 0 ? errors : null;
    };
  }

  saveItemChanges(): void {
    const current = this.selectedItem();
    const refundId = this.refundId();
    if (!current || !refundId || this.editForm.invalid || this.isSaving() || !this.isDraft()) {
      this.editForm.markAllAsTouched();
      return;
    }

    const v = this.editForm.value;
    const cat = v.category as ExpenseCategory;
    const startsAt = this.formatToIso(v.startsAt);
    const endsAt = cat === ExpenseCategory.TRANSPORT || cat === ExpenseCategory.ACCOMMODATION ? this.formatToIso(v.endsAt) : null;

    const payload: RefundItemUpdatePayload = {
      category: cat,
      subtype: cat === ExpenseCategory.OTHER ? null : v.subtype,
      itineraryFrom: cat === ExpenseCategory.TRANSPORT ? v.itineraryFrom?.trim() || null : null,
      itineraryTo: cat === ExpenseCategory.TRANSPORT ? v.itineraryTo?.trim() || null : null,
      startsAt: startsAt ?? undefined,
      endsAt,
      requestedAmount: Number(v.requestedAmount),
      isTraceable: Boolean(v.isTraceable),
      description: String(v.description).trim(),
    };

    this.isSaving.set(true);

    const execute = () => {
      this.refundService.updateRefundItem(refundId, current.id, payload).subscribe({
        next: (updatedItem) => {
          this.items.update((list) => list.map((it) => (it.id === updatedItem.id ? updatedItem : it)));
          this.loadFilteredItems();
          this.toastService.showSuccess('Expense item updated successfully.', 'Saved');
          this.closeItemModal();
        },
        error: (err) => {
          this.isSaving.set(false);
          this.toastService.showError(err?.error?.message ?? 'Could not save expense item changes.', 'Save Error');
        },
      });
    };

    const newReceipt = this.replacementFile();
    if (newReceipt) {
      this.refundService.uploadReceipt(refundId, newReceipt).subscribe({
        next: (up) => { payload.receiptFilePath = up.receiptFilePath; payload.receiptOriginalFilename = up.receiptOriginalFilename; execute(); },
        error: () => { this.isSaving.set(false); this.toastService.showError('Could not upload the new receipt file.', 'Upload Error'); },
      });
    } else {
      execute();
    }
  }

  closeItemModal(): void {
    this.selectedItem.set(null);
    this.isReceiptLoading.set(false);
    this.isSaving.set(false);
    this.receiptError.set(false);
    this.replacementFile.set(null);
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

  openConfirmSubmit(): void {
    if (!this.isMissionEnded() || this.items().length === 0 || this.isSubmitting() || !this.isDraft()) {
      return;
    }
    this.confirmSubmitOpen.set(true);
  }

  submitRefund(): void {
    this.confirmSubmitOpen.set(false);
    const ref = this.refund();
    if (!ref || !this.isMissionEnded() || this.items().length === 0 || this.isSubmitting() || !this.isDraft() || this.hasItemsPendingReview()) {
      return;
    }
    this.isSubmitting.set(true);
    this.refundService.submitRefundRequest(ref.id).subscribe({
      next: (updatedRefund) => {
        this.isSubmitting.set(false);
        this.refund.set(updatedRefund);
        this.toastService.showSuccess('Refund request submitted successfully.', 'Submitted');
        this.router.navigate(['/missionreview'], { queryParams: { view: 'requester' } });
      },
      error: (err) => {
        this.isSubmitting.set(false);
        this.toastService.showError(
          err?.error?.message ?? 'Failed to submit refund request.',
          'Error'
        );
      },
    });
  }

  deleteItem(item: RefundItemDTO, event: Event): void {
    event.stopPropagation();
    const id = this.refundId();
    if (!id || !this.isDraft()) return;
    this.refundService.deleteRefundItem(id, item.id).subscribe({
      next: () => {
        this.items.update((list) => list.filter((it) => it.id !== item.id));
        if (this.selectedItem()?.id === item.id) this.closeItemModal();
        this.loadFilteredItems();
        this.toastService.showSuccess('Expense item removed.', 'Deleted');
      },
      error: () => this.toastService.showError('Could not delete expense item.', 'Delete Error'),
    });
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

  openBatchModal(): void { this.isBatchModalOpen.set(true); }
  closeBatchModal(): void { this.isBatchModalOpen.set(false); }
  onBatchItemsAdded(newItems: RefundItemDTO[]): void {
    this.items.update((current) => [...current, ...newItems]);
    this.closeBatchModal();
    this.loadFilteredItems(true);
  }

  formatCategory(cat: ExpenseCategory): string {
    const labels: Record<ExpenseCategory, string> = {
      [ExpenseCategory.TRANSPORT]: 'Transport', [ExpenseCategory.ACCOMMODATION]: 'Accommodation',
      [ExpenseCategory.MEALS]: 'Meals', [ExpenseCategory.OTHER]: 'Other',
    };
    return labels[cat] ?? cat;
  }
}
