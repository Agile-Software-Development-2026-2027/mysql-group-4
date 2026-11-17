import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnInit,
  Output,
  SimpleChanges,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  AbstractControl,
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { map, of, switchMap } from 'rxjs';

import {
  CurrencyConversionDTO,
  ExpenseCategory,
  ExpenseSubtype,
  MissionDTO,
  ReceiptAutocompleteDTO,
  RefundItemCreatePayload,
  RefundItemDTO,
  RefundReceiptUploadDTO,
} from '../../../../core/models';
import { MissionService } from '../../../../services/mission.service';
import { RefundService } from '../../../../services/refund.service';
import { ToastService } from '../../../../services/toast.service';

interface SubtypeOption {
  value: ExpenseSubtype;
  label: string;
}

function noWhitespaceValidator(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = control.value;
    if (typeof value === 'string' && value.length > 0 && value.trim().length === 0) {
      return { whitespace: true };
    }
    return null;
  };
}

@Component({
  selector: 'app-add-refund-item-modal',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './add-refund-item-modal.html',
  styleUrl: './add-refund-item-modal.scss',
})
export class AddRefundItemModal implements OnInit, OnChanges {
  @Input({ required: true }) refundId!: string;
  @Input() missionStartsAt: string | null = null;
  @Input() missionEndsAt: string | null = null;
  @Output() itemCreated = new EventEmitter<RefundItemDTO>();
  @Output() closed = new EventEmitter<void>();

  private fb = inject(FormBuilder);
  private refundService = inject(RefundService);
  private missionService = inject(MissionService);
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
  private rawPdfUrl: string | null = null;
  isPdf = signal(false);
  isDragging = signal(false);
  isSubmitting = signal(false);

  isConvertingCurrency = signal(false);
  conversionInfo = signal<CurrencyConversionDTO | null>(null);
  foreignCurrency = signal<string>('EUR');
  readonly availableCurrencies = ['EUR', 'USD', 'GBP', 'CHF', 'RUB', 'CNY', 'TWD', 'JPY', 'AED', 'CAD', 'AUD'];
  isOcrPrefilled = signal(false);
  isExtractingOcr = signal(false);
  ocrRawText = signal<string | null>(null);
  minDateTime = signal<string | null>(null);
  maxDateTime = signal<string | null>(null);
  missionPeriodLabel = signal<string>('');
  form!: FormGroup;

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
    this.updateMissionBounds();
    this.initForm();
    this.setupCategoryChangeListener();
    this.loadMissionBounds();
    this.loadMissionCurrencyProfile();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['missionStartsAt'] || changes['missionEndsAt']) {
      this.updateMissionBounds();
      this.form?.updateValueAndValidity();
    }
  }

  private loadMissionBounds(): void {
    if (this.missionStartsAt && this.missionEndsAt) {
      this.updateMissionBounds();
      return;
    }
    if (!this.refundId) {
      return;
    }
    this.refundService
      .getById(this.refundId)
      .pipe(
        switchMap((refund) => {
          if (!refund?.missionId) {
            return of(null);
          }
          return this.missionService.getMySentMissions({}, 100).pipe(
            map((page) => {
              const missions: MissionDTO[] =
                (page as { items?: MissionDTO[]; content?: MissionDTO[] })?.items ??
                (page as { items?: MissionDTO[]; content?: MissionDTO[] })?.content ??
                [];
              return missions.find((m) => m.id === refund.missionId) ?? null;
            })
          );
        })
      )
      .subscribe({
        next: (mission) => {
          if (mission?.startsAt && mission?.endsAt) {
            this.missionStartsAt = mission.startsAt;
            this.missionEndsAt = mission.endsAt;
            this.updateMissionBounds();
            this.form?.updateValueAndValidity();
          }
        },
        error: (err) => {
          console.error('Failed to load mission dates:', err);
        },
      });
  }

  private updateMissionBounds(): void {
    if (!this.missionStartsAt || !this.missionEndsAt) {
      this.minDateTime.set(null);
      this.maxDateTime.set(null);
      this.missionPeriodLabel.set('');
      return;
    }
    const start = new Date(this.missionStartsAt);
    const end = new Date(this.missionEndsAt);
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      this.minDateTime.set(null);
      this.maxDateTime.set(null);
      this.missionPeriodLabel.set('');
      return;
    }
    this.minDateTime.set(this.toDateTimeLocalString(start));
    this.maxDateTime.set(this.toDateTimeLocalString(end));
    const startStr = start.toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
    const endStr = end.toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
    this.missionPeriodLabel.set(`${startStr} – ${endStr}`);
  }

  private toDateTimeLocalString(date: Date): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  private initForm(): void {
    this.form = this.fb.group(
      {
        category: [ExpenseCategory.TRANSPORT, Validators.required],
        subtype: [ExpenseSubtype.TRAIN, Validators.required],
        itineraryFrom: ['', [Validators.required, noWhitespaceValidator(), Validators.maxLength(255)]],
        itineraryTo: ['', [Validators.required, noWhitespaceValidator(), Validators.maxLength(255)]],
        startsAt: ['', Validators.required],
        endsAt: ['', Validators.required],
        requestedAmount: [
          null,
          [Validators.required, Validators.min(0.01), Validators.max(10000.0)],
        ],
        currency: ['EUR', [Validators.required, Validators.minLength(3), Validators.maxLength(3)]],
        isTraceable: [true],
        description: ['', [Validators.required, noWhitespaceValidator(), Validators.maxLength(255)]],
      },
      { validators: [this.crossFieldConsistencyValidator()] }
    );
  }

  private crossFieldConsistencyValidator(): ValidatorFn {
    return (group: AbstractControl): ValidationErrors | null => {
      const errors: ValidationErrors = {};
      const now = new Date();
      const category = group.get('category')?.value as ExpenseCategory;
      const startsAt = group.get('startsAt')?.value as string;
      const endsAt = group.get('endsAt')?.value as string;
      const from = (group.get('itineraryFrom')?.value as string | null)?.trim().toLowerCase();
      const to = (group.get('itineraryTo')?.value as string | null)?.trim().toLowerCase();
      const startDate = startsAt ? new Date(startsAt) : null;
      const endDate = endsAt ? new Date(endsAt) : null;
      let missionStart: Date | null = null;
      let missionEnd: Date | null = null;
      if (this.missionStartsAt && this.missionEndsAt) {
        const parsedStart = new Date(this.missionStartsAt);
        const parsedEnd = new Date(this.missionEndsAt);
        if (!isNaN(parsedStart.getTime()) && !isNaN(parsedEnd.getTime())) {
          parsedStart.setSeconds(0, 0);
          parsedEnd.setSeconds(59, 999);
          missionStart = parsedStart;
          missionEnd = parsedEnd;
        }
      }
      if (startDate && !isNaN(startDate.getTime())) {
        if (startDate > now) {
          errors['startInFuture'] = true;
        }
        if (missionStart && missionEnd && (startDate < missionStart || startDate > missionEnd)) {
          errors['startOutsideMission'] = true;
        }
      }
      if (
        (category === ExpenseCategory.TRANSPORT || category === ExpenseCategory.ACCOMMODATION) &&
        endDate &&
        !isNaN(endDate.getTime())
      ) {
        if (endDate > now) {
          errors['endInFuture'] = true;
        }
        if (missionStart && missionEnd && (endDate < missionStart || endDate > missionEnd)) {
          errors['endOutsideMission'] = true;
        }
        if (startDate && !isNaN(startDate.getTime()) && endDate <= startDate) {
          errors['endBeforeStart'] = true;
        }
      }
      if (category === ExpenseCategory.TRANSPORT && from && to && from === to) {
        errors['sameLocation'] = true;
      }
      return Object.keys(errors).length > 0 ? errors : null;
    };
  }

  populateFromOcr(data: Partial<RefundItemCreatePayload>): void {
    if (data.category) {
      this.form.get('category')?.setValue(data.category);
    }
    this.form.patchValue({
      subtype: data.subtype ?? this.form.get('subtype')?.value,
      itineraryFrom: data.itineraryFrom ?? '',
      itineraryTo: data.itineraryTo ?? '',
      startsAt: data.startsAt ?? '',
      endsAt: data.endsAt ?? '',
      requestedAmount: data.requestedAmount ?? null,
      currency: data.currency ?? 'EUR',
      isTraceable: data.isTraceable ?? true,
      description: data.description ?? '',
    });
    this.isOcrPrefilled.set(true);
    this.form.markAllAsTouched();
    this.form.updateValueAndValidity();
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

      fromCtrl.setValidators([Validators.required, noWhitespaceValidator(), Validators.maxLength(255)]);
      toCtrl.setValidators([Validators.required, noWhitespaceValidator(), Validators.maxLength(255)]);

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
    this.form.updateValueAndValidity();
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

  private static readonly MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFileSelected(input.files[0]);
      input.value = '';
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

    if (file.size > AddRefundItemModal.MAX_FILE_SIZE_BYTES) {
      this.uploadError.set('File size exceeds the 10MB limit.');
      this.toastService.showError(this.uploadError()!, 'File Too Large');
      return;
    }

    this.cleanPreviews();
    this.selectedFile.set(file);
    this.uploadError.set(null);

    const isPdfFile = fileName.endsWith('.pdf');
    this.isPdf.set(isPdfFile);

    const localUrl = URL.createObjectURL(file);
    if (isPdfFile) {
      this.rawPdfUrl = localUrl;
      this.safePdfUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(localUrl));
    } else {
      this.previewUrl.set(localUrl);
    }

    this.uploadToMinio(file);
    this.triggerOcrExtraction(file);
  }

  private loadMissionCurrencyProfile(): void {
    if (!this.refundId) {
      return;
    }
    this.refundService.getCurrencyProfile(this.refundId).subscribe({
      next: (profile) => {
        if (profile?.defaultCurrency) {
          this.foreignCurrency.set(profile.defaultCurrency);
        }
      },
      error: (err) => {
        console.warn('Could not load mission currency profile:', err);
      },
    });
  }

  onForeignCurrencyChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.foreignCurrency.set(select.value || 'EUR');
  }

  convertToEur(): void {
    const rawAmount = Number(this.form.get('requestedAmount')?.value);
    const curr = this.foreignCurrency();
    if (!rawAmount || rawAmount <= 0) {
      this.toastService.showError('Enter a valid amount to convert.', 'Invalid Amount');
      return;
    }
    if (curr === 'EUR') {
      return;
    }

    this.isConvertingCurrency.set(true);
    this.refundService.convertCurrencyToEur(rawAmount, curr).subscribe({
      next: (res) => {
        this.isConvertingCurrency.set(false);
        this.conversionInfo.set(res);
        this.form.patchValue({
          requestedAmount: res.convertedAmount,
          currency: 'EUR',
        });
        const currentDesc = (this.form.get('description')?.value || '').trim();
        const note = `[Converted from ${res.originalAmount} ${res.originalCurrency} @ ${res.rate}]`;
        if (!currentDesc.includes(note)) {
          const nextDesc = currentDesc ? `${currentDesc} ${note}` : note;
          this.form.patchValue({ description: nextDesc.slice(0, 255) });
        }
        this.toastService.showSuccess(
          `${res.originalAmount} ${res.originalCurrency} converted to €${res.convertedAmount}`,
          'Currency Converted'
        );
      },
      error: (err) => {
        this.isConvertingCurrency.set(false);
        const msg = err?.error?.detail ?? 'Unable to convert currency right now.';
        this.toastService.showError(msg, 'Conversion Failed');
      },
    });
  }

  private triggerOcrExtraction(file: File): void {
    if (!this.refundId) {
      return;
    }
    this.isExtractingOcr.set(true);
    this.refundService.extractReceipt(this.refundId, file).subscribe({
      next: (dto: ReceiptAutocompleteDTO) => {
        this.isExtractingOcr.set(false);
        if (dto.rawText) {
          this.ocrRawText.set(dto.rawText);
        }

        const patch: Partial<RefundItemCreatePayload> = {};
        if (dto.category) {
          patch.category = dto.category;
        }
        if (dto.subtype) {
          patch.subtype = dto.subtype;
        }
        if (dto.amount != null) {
          patch.requestedAmount = dto.convertedAmountEur ?? dto.amount;
        }
        if (dto.startsAt) {
          patch.startsAt = dto.startsAt;
        }
        if (dto.endsAt) {
          patch.endsAt = dto.endsAt;
        }
        if (dto.itineraryFrom) {
          patch.itineraryFrom = dto.itineraryFrom;
        }
        if (dto.itineraryTo) {
          patch.itineraryTo = dto.itineraryTo;
        }
        if (dto.description || dto.merchant) {
          const parts = [dto.merchant, dto.description].filter(Boolean);
          patch.description = parts.join(' - ').slice(0, 255);
        }

        if (dto.convertedAmountEur && dto.currency && dto.currency !== 'EUR' && dto.exchangeRate) {
          this.conversionInfo.set({
            originalCurrency: dto.currency,
            originalAmount: dto.amount ?? 0,
            convertedAmount: dto.convertedAmountEur,
            rate: dto.exchangeRate,
            date: dto.rateDate ?? '',
            provider: 'AI Auto-Conversion',
          });
        }

        const hasExtractedFields = Boolean(
          dto.category ||
          dto.amount != null ||
          dto.startsAt ||
          dto.merchant ||
          dto.description ||
          dto.itineraryFrom ||
          dto.itineraryTo
        );

        if (!hasExtractedFields) {
          if (dto.warnings?.length) {
            console.warn('AI receipt extraction returned warnings:', dto.warnings);
          }
          this.toastService.showWarning(
            'Failed to extract data from the receipt. Please fill the fields manually.',
            'AI Auto-Fill'
          );
          return;
        }

        this.populateFromOcr(patch);
        this.toastService.showSuccess(
          'Receipt analyzed with AI. Fields have been pre-filled.',
          'AI Auto-Fill'
        );
      },
      error: (err) => {
        this.isExtractingOcr.set(false);
        console.warn('AI receipt extraction skipped/failed:', err);
        this.toastService.showWarning(
          'Failed to extract data from the receipt. Please fill the fields manually.',
          'AI Auto-Fill'
        );
      },
    });
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
    this.isOcrPrefilled.set(false);
    this.isExtractingOcr.set(false);
    this.ocrRawText.set(null);
    this.isConvertingCurrency.set(false);
    this.conversionInfo.set(null);
  }


  private cleanPreviews(): void {
    if (this.previewUrl()) {
      URL.revokeObjectURL(this.previewUrl()!);
    }
    if (this.rawPdfUrl) {
      URL.revokeObjectURL(this.rawPdfUrl);
      this.rawPdfUrl = null;
    }
    this.previewUrl.set(null);
    this.safePdfUrl.set(null);
    this.isPdf.set(false);
  }

  // --- Form Submission ---

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.toastService.showError('Please fix the highlighted errors before saving.', 'Invalid Form');
      return;
    }

    if (!this.uploadedReceipt()) {
      this.toastService.showError('Please upload a valid receipt before saving.', 'Missing Receipt');
      return;
    }

    const val = this.form.value;

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
