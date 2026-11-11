import {
  Component,
  EventEmitter,
  Input,
  OnInit,
  Output,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import {
  ExpenseCategory,
  ExpenseSubtype,
  RefundItemCreatePayload,
  RefundItemDTO,
  RefundReceiptUploadDTO,
} from '../../../../core/models';
import { RefundService } from '../../../../services/refund.service';
import { ToastService } from '../../../../services/toast.service';

interface SubtypeOption {
  value: ExpenseSubtype;
  label: string;
}

@Component({
  selector: 'app-add-refund-item-modal',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './add-refund-item-modal.html',
  styleUrl: './add-refund-item-modal.scss',
})
export class AddRefundItemModal implements OnInit {
  @Input({ required: true }) refundId!: string;
  @Output() itemCreated = new EventEmitter<RefundItemDTO>();
  @Output() closed = new EventEmitter<void>();

  private fb = inject(FormBuilder);
  private refundService = inject(RefundService);
  private toastService = inject(ToastService);
  private sanitizer = inject(DomSanitizer);

  ExpenseCategory = ExpenseCategory;
  ExpenseSubtype = ExpenseSubtype;

  // Stato upload e preview
  selectedFile = signal<File | null>(null);
  isUploading = signal(false);
  uploadError = signal<string | null>(null);
  uploadedReceipt = signal<RefundReceiptUploadDTO | null>(null);
  previewUrl = signal<string | null>(null);
  safePdfUrl = signal<SafeResourceUrl | null>(null);
  isPdf = signal(false);
  isDragging = signal(false);
  isSubmitting = signal(false);

  // Form reattivo
  form!: FormGroup;

  // Subtype mappings per category
  readonly transportSubtypes: SubtypeOption[] = [
    { value: ExpenseSubtype.TRAIN, label: 'Train' },
    { value: ExpenseSubtype.PLANE, label: 'Plane' },
    { value: ExpenseSubtype.SHIP, label: 'Ship / Ferry' },
    { value: ExpenseSubtype.PUBLIC_TRANSPORT, label: 'Public Transit' },
    { value: ExpenseSubtype.TAXI_RENTAL, label: 'Taxi / Car Rental' },
    { value: ExpenseSubtype.OWN_VEHICLE, label: 'Personal Vehicle' },
  ];

  readonly accommodationSubtypes: SubtypeOption[] = [
    { value: ExpenseSubtype.ACCOMMODATION_EXPENSE, label: 'Accommodation Expense' },
    { value: ExpenseSubtype.OTHER_ACCOMMODATION_EXPENSE, label: 'Other Accommodation Expense' },
  ];

  readonly mealsSubtypes: SubtypeOption[] = [
    { value: ExpenseSubtype.MEALS_EXPENSE, label: 'Meal' },
    { value: ExpenseSubtype.OTHER_MEALS_EXPENSE, label: 'Other Meals' },
  ];

  currentSubtypes = signal<SubtypeOption[]>(this.transportSubtypes);

  ngOnInit(): void {
    this.initForm();
    this.setupCategoryChangeListener();
  }

  private initForm(): void {
    this.form = this.fb.group({
      category: [ExpenseCategory.TRANSPORT, Validators.required],
      subtype: [ExpenseSubtype.TRAIN, Validators.required],
      itineraryFrom: ['', [Validators.required, Validators.maxLength(255)]],
      itineraryTo: ['', [Validators.required, Validators.maxLength(255)]],
      startsAt: ['', Validators.required],
      endsAt: ['', Validators.required],
      requestedAmount: [
        null,
        [Validators.required, Validators.min(0.01), Validators.max(10000.0)],
      ],
      currency: ['EUR', [Validators.required, Validators.minLength(3), Validators.maxLength(3)]],
      isTraceable: [true],
      description: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(255)]],
    });
  }

  private setupCategoryChangeListener(): void {
    this.form.get('category')?.valueChanges.subscribe((category: ExpenseCategory) => {
      this.updateCategoryValidators(category);
    });
  }

  private updateCategoryValidators(category: ExpenseCategory): void {
    const subtypeCtrl = this.form.get('subtype')!;
    const fromCtrl = this.form.get('itineraryFrom')!;
    const toCtrl = this.form.get('itineraryTo')!;
    const endsAtCtrl = this.form.get('endsAt')!;

    if (category === ExpenseCategory.TRANSPORT) {
      this.currentSubtypes.set(this.transportSubtypes);
      subtypeCtrl.setValidators([Validators.required]);
      subtypeCtrl.setValue(ExpenseSubtype.TRAIN);

      fromCtrl.setValidators([Validators.required, Validators.maxLength(255)]);
      toCtrl.setValidators([Validators.required, Validators.maxLength(255)]);

      endsAtCtrl.setValidators([Validators.required]);
    } else if (category === ExpenseCategory.ACCOMMODATION) {
      this.currentSubtypes.set(this.accommodationSubtypes);
      subtypeCtrl.setValidators([Validators.required]);
      subtypeCtrl.setValue(ExpenseSubtype.ACCOMMODATION_EXPENSE);

      fromCtrl.clearValidators();
      fromCtrl.setValue('');
      toCtrl.clearValidators();
      toCtrl.setValue('');

      endsAtCtrl.setValidators([Validators.required]);
    } else if (category === ExpenseCategory.MEALS) {
      this.currentSubtypes.set(this.mealsSubtypes);
      subtypeCtrl.setValidators([Validators.required]);
      subtypeCtrl.setValue(ExpenseSubtype.MEALS_EXPENSE);

      fromCtrl.clearValidators();
      fromCtrl.setValue('');
      toCtrl.clearValidators();
      toCtrl.setValue('');

      endsAtCtrl.clearValidators();
      endsAtCtrl.setValue('');
    } else if (category === ExpenseCategory.OTHER) {
      this.currentSubtypes.set([]);
      subtypeCtrl.clearValidators();
      subtypeCtrl.setValue(null);

      fromCtrl.clearValidators();
      fromCtrl.setValue('');
      toCtrl.clearValidators();
      toCtrl.setValue('');

      endsAtCtrl.clearValidators();
      endsAtCtrl.setValue('');
    }

    subtypeCtrl.updateValueAndValidity();
    fromCtrl.updateValueAndValidity();
    toCtrl.updateValueAndValidity();
    endsAtCtrl.updateValueAndValidity();
  }

  //Gestione Drag & Drop e Upload File

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);

    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFileSelected(files[0]);
    }
  }

  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFileSelected(input.files[0]);
    }
  }

  private handleFileSelected(file: File): void {
    const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.webp'];
    const fileName = file.name.toLowerCase();
    const isAllowed = allowedExtensions.some((ext) => fileName.endsWith(ext));

    if (!isAllowed) {
      this.uploadError.set('Unsupported file format. Only PDF, JPG, PNG, or WEBP files are allowed.');
      this.toastService.showError(this.uploadError()!, 'Invalid File');
      return;
    }

    if (file.size === 0) {
      this.uploadError.set('The selected file is empty.');
      this.toastService.showError(this.uploadError()!, 'Empty File');
      return;
    }

    // Clean previous preview
    this.cleanPreviews();

    this.selectedFile.set(file);
    this.uploadError.set(null);

    // Create immediate local preview
    const isPdfFile = fileName.endsWith('.pdf');
    this.isPdf.set(isPdfFile);

    const localUrl = URL.createObjectURL(file);
    if (isPdfFile) {
      this.safePdfUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(localUrl));
    } else {
      this.previewUrl.set(localUrl);
    }

    // Upload to MinIO
    this.uploadToMinio(file);
  }

  private uploadToMinio(file: File): void {
    this.isUploading.set(true);
    this.refundService.uploadReceipt(this.refundId, file).subscribe({
      next: (uploadDto) => {
        this.uploadedReceipt.set(uploadDto);
        this.isUploading.set(false);
        this.toastService.showSuccess('Receipt uploaded successfully.', 'Upload Completed');
      },
      error: (err) => {
        this.isUploading.set(false);
        const errMsg = err?.error?.message ?? 'Failed to upload receipt to MinIO.';
        this.uploadError.set(errMsg);
        this.toastService.showError(errMsg, 'Upload Failed');
      },
    });
  }

  removeReceipt(): void {
    this.cleanPreviews();
    this.selectedFile.set(null);
    this.uploadedReceipt.set(null);
    this.uploadError.set(null);
  }

  private cleanPreviews(): void {
    this.previewUrl.set(null);
    this.safePdfUrl.set(null);
    this.isPdf.set(false);
  }

  // --- Form Submission ---

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.toastService.showError('Please fill in all required fields.', 'Missing Fields');
      return;
    }

    if (!this.uploadedReceipt()) {
      this.toastService.showError('Please upload a valid receipt before saving.', 'Missing Receipt');
      return;
    }

    const val = this.form.value;

    // Date consistency check for TRANSPORT and ACCOMMODATION
    if (
      (val.category === ExpenseCategory.TRANSPORT || val.category === ExpenseCategory.ACCOMMODATION) &&
      val.startsAt &&
      val.endsAt
    ) {
      const start = new Date(val.startsAt);
      const end = new Date(val.endsAt);
      if (end < start) {
        this.toastService.showError(
          val.category === ExpenseCategory.TRANSPORT
            ? 'Arrival time must be after departure time.'
            : 'Check-out date must be after check-in date.',
          'Invalid Dates'
        );
        return;
      }
    }

    const payload: RefundItemCreatePayload = {
      category: val.category,
      subtype: val.category === ExpenseCategory.OTHER ? null : val.subtype,
      itineraryFrom: val.category === ExpenseCategory.TRANSPORT ? val.itineraryFrom.trim() : null,
      itineraryTo: val.category === ExpenseCategory.TRANSPORT ? val.itineraryTo.trim() : null,
      startsAt: val.startsAt,
      endsAt:
        val.category === ExpenseCategory.TRANSPORT || val.category === ExpenseCategory.ACCOMMODATION
          ? val.endsAt
          : null,
      requestedAmount: Number(val.requestedAmount),
      currency: val.currency || 'EUR',
      isTraceable: !!val.isTraceable,
      receiptFilePath: this.uploadedReceipt()!.receiptFilePath,
      receiptOriginalFilename: this.uploadedReceipt()!.receiptOriginalFilename,
      description: val.description.trim(),
    };

    this.isSubmitting.set(true);
    this.refundService.createRefundItem(this.refundId, payload).subscribe({
      next: (createdItem) => {
        this.isSubmitting.set(false);
        this.toastService.showSuccess('Expense item added successfully.', 'Item Added');
        this.itemCreated.emit(createdItem);
        this.close();
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const errMsg = err?.error?.message ?? 'Failed to create expense item.';
        this.toastService.showError(errMsg, 'Error');
      },
    });
  }

  close(): void {
    this.cleanPreviews();
    this.closed.emit();
  }
}
