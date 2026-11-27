import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnDestroy,
  Output,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { RefundItemDTO } from '../../../../core/models';
import { RefundService } from '../../../../services/refund.service';
import { ToastService } from '../../../../services/toast.service';

@Component({
  selector: 'app-quick-upload-receipt-modal',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './quick-upload-receipt-modal.html',
  styleUrl: './quick-upload-receipt-modal.scss',
})
export class QuickUploadReceiptModal implements AfterViewInit, OnDestroy {
  @Input({ required: true }) refundId!: string;
  @Input() missionSubject: string | null = null;
  @Output() itemCreated = new EventEmitter<RefundItemDTO>();
  @Output() closed = new EventEmitter<void>();

  @ViewChild('dialogEl') dialogRef?: ElementRef<HTMLDialogElement>;

  private refundService = inject(RefundService);
  private toastService = inject(ToastService);
  private sanitizer = inject(DomSanitizer);

  private static readonly MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
  private static readonly ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.webp'];

  selectedFile = signal<File | null>(null);
  previewUrl = signal<string | null>(null);
  safePdfUrl = signal<SafeResourceUrl | null>(null);
  isPdf = signal(false);
  isDragging = signal(false);
  isProcessing = signal(false);
  errorMessage = signal<string | null>(null);

  private rawPdfUrl: string | null = null;
  private pressedOutside = false;
  private removeFallbackListeners: (() => void) | null = null;

  ngAfterViewInit(): void {
    const dialog = this.dialogRef?.nativeElement;
    if (!dialog || typeof HTMLDialogElement === 'undefined') return;

    if (!dialog.open) {
      dialog.showModal();
    }

    // Fallback light-dismiss for browsers without native closedby support (e.g. Safari)
    if (!('closedBy' in HTMLDialogElement.prototype)) {
      const isOutside = (e: PointerEvent): boolean => {
        const r = dialog.getBoundingClientRect();
        return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
      };
      const onPointerDown = (e: PointerEvent) => {
        this.pressedOutside = isOutside(e);
      };
      const onPointerUp = (e: PointerEvent) => {
        if (!this.isProcessing() && this.pressedOutside && isOutside(e)) {
          dialog.close();
        }
        this.pressedOutside = false;
      };
      dialog.addEventListener('pointerdown', onPointerDown);
      dialog.addEventListener('pointerup', onPointerUp);
      this.removeFallbackListeners = () => {
        dialog.removeEventListener('pointerdown', onPointerDown);
        dialog.removeEventListener('pointerup', onPointerUp);
      };
    }
  }

  ngOnDestroy(): void {
    this.removeFallbackListeners?.();
    this.removeFallbackListeners = null;
    this.cleanPreviews();
    const dialog = this.dialogRef?.nativeElement;
    if (dialog?.open) {
      dialog.close();
    }
  }

  onDialogCancel(event: Event): void {
    if (this.isProcessing()) {
      event.preventDefault();
    }
  }

  onDialogClose(): void {
    const dialog = this.dialogRef?.nativeElement;
    if (dialog) {
      dialog.returnValue = '';
    }
    this.cleanPreviews();
    this.closed.emit();
  }

  requestClose(): void {
    if (this.isProcessing()) return;
    const dialog = this.dialogRef?.nativeElement;
    if (dialog?.open) {
      dialog.close();
    } else {
      this.cleanPreviews();
      this.closed.emit();
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    if (!this.isProcessing()) {
      this.isDragging.set(true);
    }
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
    if (this.isProcessing()) return;
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFileSelected(files[0]);
    }
  }

  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFileSelected(input.files[0]);
      input.value = '';
    }
  }

  private handleFileSelected(file: File): void {
    const lowerName = file.name.toLowerCase();
    const isAllowed = QuickUploadReceiptModal.ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));

    if (!isAllowed) {
      const msg = 'Unsupported file format. Only PDF, JPG, PNG, or WEBP files are allowed.';
      this.errorMessage.set(msg);
      this.toastService.showError(msg, 'Invalid File');
      return;
    }

    if (file.size === 0) {
      const msg = 'The selected file is empty.';
      this.errorMessage.set(msg);
      this.toastService.showError(msg, 'Empty File');
      return;
    }

    if (file.size > QuickUploadReceiptModal.MAX_FILE_SIZE_BYTES) {
      const msg = 'File size exceeds the 10MB limit.';
      this.errorMessage.set(msg);
      this.toastService.showError(msg, 'File Too Large');
      return;
    }

    this.cleanPreviews();
    this.selectedFile.set(file);
    this.errorMessage.set(null);

    const isPdfFile = lowerName.endsWith('.pdf') || file.type === 'application/pdf';
    this.isPdf.set(isPdfFile);

    const localUrl = URL.createObjectURL(file);
    if (isPdfFile) {
      this.rawPdfUrl = localUrl;
      this.safePdfUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(localUrl));
    } else {
      this.previewUrl.set(localUrl);
    }
  }

  removeReceipt(): void {
    if (this.isProcessing()) return;
    this.cleanPreviews();
    this.selectedFile.set(null);
    this.errorMessage.set(null);
  }

  uploadAndProcess(): void {
    const file = this.selectedFile();
    if (!file || this.isProcessing()) return;

    this.isProcessing.set(true);
    this.errorMessage.set(null);

    this.refundService.quickUploadReceipt(this.refundId, file).subscribe({
      next: (createdItem) => {
        this.isProcessing.set(false);
        this.toastService.showSuccess(
          'Receipt uploaded and processed. Review it in your refund request before submitting.',
          'Receipt Added'
        );
        this.itemCreated.emit(createdItem);
        this.requestClose();
      },
      error: (err) => {
        this.isProcessing.set(false);
        const msg = this.extractErrorMessage(err, 'Failed to upload and process receipt.');
        this.errorMessage.set(msg);
        this.toastService.showError(msg, 'Upload Failed');
      },
    });
  }

  private extractErrorMessage(err: unknown, fallback: string): string {
    const anyErr = err as { error?: { detail?: unknown; message?: unknown } } | null | undefined;
    if (typeof anyErr?.error?.message === 'string' && anyErr.error.message.trim()) {
      return anyErr.error.message;
    }
    if (typeof anyErr?.error?.detail === 'string' && anyErr.error.detail.trim()) {
      return anyErr.error.detail;
    }
    return fallback;
  }

  private cleanPreviews(): void {
    const imgUrl = this.previewUrl();
    if (imgUrl) {
      URL.revokeObjectURL(imgUrl);
    }
    if (this.rawPdfUrl) {
      URL.revokeObjectURL(this.rawPdfUrl);
      this.rawPdfUrl = null;
    }
    this.previewUrl.set(null);
    this.safePdfUrl.set(null);
    this.isPdf.set(false);
  }
}
