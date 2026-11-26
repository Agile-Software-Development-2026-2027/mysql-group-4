import {
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  OnDestroy,
  Output,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';

import { BoundingBoxDTO, ReceiptPageDTO, RefundItemDTO } from '../../../../core/models';
import { RefundService } from '../../../../services/refund.service';
import { ToastService } from '../../../../services/toast.service';

interface EditableBox extends BoundingBoxDTO {
  uid: number;
}

type DragMode = 'move' | 'draw' | 'nw' | 'ne' | 'sw' | 'se';

interface DragState {
  mode: DragMode;
  boxUid: number | null;
  startX: number;
  startY: number;
  originBox?: EditableBox;
}

@Component({
  selector: 'app-add-multiple-receipts-model',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './add-multiple-receipts-model.html',
  styleUrl: './add-multiple-receipts-model.scss',
})
export class AddMultipleReceiptsModel implements OnDestroy {
  @Input({ required: true }) refundId!: string;
  @Output() itemsCreated = new EventEmitter<RefundItemDTO[]>();
  @Output() closed = new EventEmitter<void>();

  @ViewChild('overlaySvg') overlaySvgRef?: ElementRef<SVGSVGElement>;

  private refundService = inject(RefundService);
  private toastService = inject(ToastService);

  private static readonly MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
  private nextUid = 1;
  private dragState: DragState | null = null;

  selectedFile = signal<File | null>(null);
  previewUrl = signal<string | null>(null);
  isDraggingFile = signal(false);
  isDraggingBox = signal(false);
  isDetecting = signal(false);
  isProcessing = signal(false);
  errorMessage = signal<string | null>(null);

  pages = signal<ReceiptPageDTO[]>([]);
  currentPage = signal(0);
  imageWidth = signal(0);
  imageHeight = signal(0);
  boxes = signal<EditableBox[]>([]);
  selectedBoxUid = signal<number | null>(null);

  visibleBoxes = computed(() =>
    this.boxes().filter((b) => (b.page ?? 0) === this.currentPage())
  );

  ngOnDestroy(): void {
    this.dragState = null;
    this.isDraggingBox.set(false);
    this.revokePreviewUrl();
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDraggingFile.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDraggingFile.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDraggingFile.set(false);
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
    const allowed = ['.jpg', '.jpeg', '.png', '.webp', '.pdf'];
    const lower = file.name.toLowerCase();
    if (!allowed.some((ext) => lower.endsWith(ext))) {
      const msg = 'Unsupported file format. Only JPG, PNG, WEBP, or PDF files are supported.';
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
    if (file.size > AddMultipleReceiptsModel.MAX_FILE_SIZE_BYTES) {
      const msg = 'File size exceeds the 10MB limit.';
      this.errorMessage.set(msg);
      this.toastService.showError(msg, 'File Too Large');
      return;
    }

    this.revokePreviewUrl();
    this.selectedFile.set(file);
    const isPdf = lower.endsWith('.pdf') || file.type === 'application/pdf';
    this.previewUrl.set(isPdf ? null : URL.createObjectURL(file));
    this.errorMessage.set(null);
    this.pages.set([]);
    this.currentPage.set(0);
    this.boxes.set([]);
    this.selectedBoxUid.set(null);
    this.detectBoxes(file);
  }

  private extractErrorMessage(err: unknown, fallback: string): string {
    const anyErr = err as { error?: { detail?: unknown; message?: unknown } } | null | undefined;
    const detail = anyErr?.error?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const parts = detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object' && 'msg' in item && typeof (item as { msg?: unknown }).msg === 'string') {
            return (item as { msg: string }).msg;
          }
          return null;
        })
        .filter((v): v is string => Boolean(v));
      if (parts.length > 0) {
        return parts.join('; ');
      }
    }
    const message = anyErr?.error?.message;
    if (typeof message === 'string' && message.trim()) {
      return message;
    }
    return fallback;
  }

  private detectBoxes(file: File): void {
    this.isDetecting.set(true);
    this.refundService.detectReceipts(this.refundId, file).subscribe({
      next: (res) => {
        this.isDetecting.set(false);
        const mapped: EditableBox[] = (res.boxes ?? []).map((b) => ({
          ...b,
          page: b.page ?? 0,
          uid: this.nextUid++,
        }));
        this.boxes.set(mapped);

        if (res.pages && res.pages.length > 0) {
          this.pages.set(res.pages);
          this.goToPage(0);
        } else {
          this.pages.set([]);
          this.currentPage.set(0);
          this.imageWidth.set(res.imageWidth);
          this.imageHeight.set(res.imageHeight);
          this.selectedBoxUid.set(mapped[0]?.uid ?? null);
        }
      },
      error: (err) => {
        this.isDetecting.set(false);
        const msg = this.extractErrorMessage(err, 'Could not detect receipts in the file.');
        this.errorMessage.set(msg);
        this.toastService.showError(msg, 'Detection Error');
      },
    });
  }

  goToPage(pageIndex: number): void {
    const allPages = this.pages();
    if (pageIndex < 0 || pageIndex >= allPages.length) return;
    this.finishDrag();
    const target = allPages[pageIndex];
    this.currentPage.set(pageIndex);
    this.imageWidth.set(target.imageWidth);
    this.imageHeight.set(target.imageHeight);
    this.previewUrl.set(target.imageDataUrl);
    const firstOnPage = this.boxes().find((b) => (b.page ?? 0) === pageIndex);
    this.selectedBoxUid.set(firstOnPage?.uid ?? null);
  }

  getBoxIndex(uid: number): number {
    return this.boxes().findIndex((b) => b.uid === uid);
  }

  resetFile(): void {
    this.finishDrag();
    this.revokePreviewUrl();
    this.selectedFile.set(null);
    this.pages.set([]);
    this.currentPage.set(0);
    this.boxes.set([]);
    this.selectedBoxUid.set(null);
    this.imageWidth.set(0);
    this.imageHeight.set(0);
    this.errorMessage.set(null);
  }

  addManualBox(): void {
    const imgW = this.imageWidth();
    const imgH = this.imageHeight();
    if (!imgW || !imgH) return;
    const width = Math.max(40, Math.round(imgW * 0.3));
    const height = Math.max(40, Math.round(imgH * 0.3));
    const x = Math.round((imgW - width) / 2);
    const y = Math.round((imgH - height) / 2);
    const created: EditableBox = {
      uid: this.nextUid++,
      x,
      y,
      width,
      height,
      page: this.currentPage(),
    };
    this.boxes.update((list) => [...list, created]);
    this.selectedBoxUid.set(created.uid);
  }

  selectBox(uid: number): void {
    const found = this.boxes().find((b) => b.uid === uid);
    if (found && this.pages().length > 0 && (found.page ?? 0) !== this.currentPage()) {
      this.goToPage(found.page ?? 0);
    }
    this.selectedBoxUid.set(uid);
  }

  removeBox(uid: number, event?: Event): void {
    event?.stopPropagation();
    this.boxes.update((list) => list.filter((b) => b.uid !== uid));
    if (this.selectedBoxUid() === uid) {
      const onCurrent = this.visibleBoxes()[0]?.uid ?? this.boxes()[0]?.uid ?? null;
      this.selectedBoxUid.set(onCurrent);
    }
  }

  handleRadius(): number {
    const base = Math.max(this.imageWidth(), this.imageHeight());
    return Math.max(6, Math.round(base * 0.009));
  }

  strokeWidth(): number {
    const base = Math.max(this.imageWidth(), this.imageHeight());
    return Math.max(2, Math.round(base * 0.003));
  }

  labelFontSize(): number {
    const base = Math.max(this.imageWidth(), this.imageHeight());
    return Math.max(14, Math.round(base * 0.022));
  }

  private getSvgPoint(event: PointerEvent): { x: number; y: number } {
    const svg = this.overlaySvgRef?.nativeElement;
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    if (!rect.width || !rect.height) return { x: 0, y: 0 };
    const scaleX = this.imageWidth() / rect.width;
    const scaleY = this.imageHeight() / rect.height;
    return {
      x: Math.max(0, Math.min(this.imageWidth(), (event.clientX - rect.left) * scaleX)),
      y: Math.max(0, Math.min(this.imageHeight(), (event.clientY - rect.top) * scaleY)),
    };
  }

  onSvgPointerDown(event: PointerEvent): void {
    if (event.button !== 0 || this.isProcessing()) return;
    event.preventDefault();
    const pt = this.getSvgPoint(event);
    const created: EditableBox = {
      uid: this.nextUid++,
      x: Math.round(pt.x),
      y: Math.round(pt.y),
      width: 1,
      height: 1,
      page: this.currentPage(),
    };
    this.boxes.update((list) => [...list, created]);
    this.selectedBoxUid.set(created.uid);
    this.dragState = {
      mode: 'draw',
      boxUid: created.uid,
      startX: pt.x,
      startY: pt.y,
    };
    this.isDraggingBox.set(true);
  }

  onBoxPointerDown(box: EditableBox, event: PointerEvent): void {
    event.stopPropagation();
    if (event.button !== 0 || this.isProcessing()) return;
    event.preventDefault();
    this.selectedBoxUid.set(box.uid);
    const pt = this.getSvgPoint(event);
    this.dragState = {
      mode: 'move',
      boxUid: box.uid,
      startX: pt.x,
      startY: pt.y,
      originBox: { ...box },
    };
    this.isDraggingBox.set(true);
  }

  onHandlePointerDown(box: EditableBox, handle: 'nw' | 'ne' | 'sw' | 'se', event: PointerEvent): void {
    event.stopPropagation();
    if (event.button !== 0 || this.isProcessing()) return;
    event.preventDefault();
    this.selectedBoxUid.set(box.uid);
    const pt = this.getSvgPoint(event);
    this.dragState = {
      mode: handle,
      boxUid: box.uid,
      startX: pt.x,
      startY: pt.y,
      originBox: { ...box },
    };
    this.isDraggingBox.set(true);
  }

  @HostListener('window:pointermove', ['$event'])
  onWindowPointerMove(event: PointerEvent): void {
    if (!this.dragState || this.dragState.boxUid === null) return;

    if (event.buttons === 0) {
      this.finishDrag();
      return;
    }

    const pt = this.getSvgPoint(event);
    const imgW = this.imageWidth();
    const imgH = this.imageHeight();
    const minSize = 20;
    const state = this.dragState;

    this.boxes.update((list) =>
      list.map((b) => {
        if (b.uid !== state.boxUid) return b;

        if (state.mode === 'draw') {
          const x = Math.round(Math.min(state.startX, pt.x));
          const y = Math.round(Math.min(state.startY, pt.y));
          const width = Math.max(1, Math.round(Math.abs(pt.x - state.startX)));
          const height = Math.max(1, Math.round(Math.abs(pt.y - state.startY)));
          return { ...b, x, y, width, height };
        }

        const orig = state.originBox!;
        const dx = pt.x - state.startX;
        const dy = pt.y - state.startY;

        if (state.mode === 'move') {
          const x = Math.round(Math.max(0, Math.min(imgW - orig.width, orig.x + dx)));
          const y = Math.round(Math.max(0, Math.min(imgH - orig.height, orig.y + dy)));
          return { ...b, x, y };
        }

        let left = orig.x;
        let top = orig.y;
        let right = orig.x + orig.width;
        let bottom = orig.y + orig.height;

        if (state.mode === 'nw' || state.mode === 'sw') {
          left = Math.max(0, Math.min(right - minSize, orig.x + dx));
        }
        if (state.mode === 'ne' || state.mode === 'se') {
          right = Math.min(imgW, Math.max(left + minSize, orig.x + orig.width + dx));
        }
        if (state.mode === 'nw' || state.mode === 'ne') {
          top = Math.max(0, Math.min(bottom - minSize, orig.y + dy));
        }
        if (state.mode === 'sw' || state.mode === 'se') {
          bottom = Math.min(imgH, Math.max(top + minSize, orig.y + orig.height + dy));
        }

        return {
          ...b,
          x: Math.round(left),
          y: Math.round(top),
          width: Math.round(right - left),
          height: Math.round(bottom - top),
        };
      })
    );
  }

  @HostListener('window:pointerup')
  @HostListener('window:pointercancel')
  @HostListener('window:blur')
  onWindowPointerUp(): void {
    this.finishDrag();
  }

  private finishDrag(): void {
    if (!this.dragState) return;
    const state = this.dragState;
    this.dragState = null;
    this.isDraggingBox.set(false);

    if (state.mode === 'draw' && state.boxUid !== null) {
      const drawn = this.boxes().find((b) => b.uid === state.boxUid);
      if (drawn && (drawn.width < 20 || drawn.height < 20)) {
        this.removeBox(state.boxUid);
      }
    }
  }

  confirmAndExtract(): void {
    const file = this.selectedFile();
    const currentBoxes = this.boxes();
    if (!file || currentBoxes.length === 0 || this.isProcessing()) return;

    const payload: BoundingBoxDTO[] = currentBoxes.map(({ x, y, width, height, page }) => ({
      x,
      y,
      width,
      height,
      page: page ?? 0,
    }));

    this.isProcessing.set(true);
    this.errorMessage.set(null);

    this.refundService.batchProcessReceipts(this.refundId, file, payload).subscribe({
      next: (createdItems) => {
        this.isProcessing.set(false);
        this.toastService.showSuccess(
          `${createdItems.length} receipt(s) extracted. Please review each item before submitting.`,
          'Batch Extraction Completed'
        );
        this.itemsCreated.emit(createdItems);
        this.close();
      },
      error: (err) => {
        this.isProcessing.set(false);
        const msg = this.extractErrorMessage(err, 'Failed to process batch receipts.');
        this.errorMessage.set(msg);
        this.toastService.showError(msg, 'Batch Processing Error');
      },
    });
  }

  close(): void {
    if (this.isProcessing()) return;
    this.finishDrag();
    this.revokePreviewUrl();
    this.closed.emit();
  }

  private revokePreviewUrl(): void {
    const url = this.previewUrl();
    if (url && url.startsWith('blob:')) {
      URL.revokeObjectURL(url);
    }
    this.previewUrl.set(null);
  }
}
