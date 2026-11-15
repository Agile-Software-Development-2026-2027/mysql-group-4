import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_CONFIG } from '../core/config/api.config';
import { Page } from '../core/models/page';
import {
  RefundApprovePayload,
  RefundItemCreatePayload,
  RefundItemDTO,
  RefundItemFilterPayload,
  RefundReceiptUploadDTO,
  RefundRequestCreatePayload,
  RefundRequestDTO,
  RefundReviewDTO,
} from '../core/models';

@Injectable({
  providedIn: 'root',
})
export class RefundService {
  private http = inject(HttpClient);

  createRefundRequest(missionId: string): Observable<RefundRequestDTO> {
    const payload: RefundRequestCreatePayload = { missionId };
    return this.http.post<RefundRequestDTO>(
      API_CONFIG.endpoints.refunds.base,
      payload,
      { withCredentials: true }
    );
  }

  getByMissionId(missionId: string): Observable<RefundRequestDTO | null> {
    return this.http.get<RefundRequestDTO | null>(
      API_CONFIG.endpoints.refunds.byMission(missionId),
      { withCredentials: true }
    );
  }

  getById(refundId: string): Observable<RefundRequestDTO> {
    return this.http.get<RefundRequestDTO>(
      API_CONFIG.endpoints.refunds.byId(refundId),
      { withCredentials: true }
    );
  }

  getReview(refundId: string): Observable<RefundReviewDTO> {
    return this.http.get<RefundReviewDTO>(
      API_CONFIG.endpoints.refunds.review(refundId),
      { withCredentials: true }
    );
  }

  approve(refundId: string, payload: RefundApprovePayload): Observable<RefundReviewDTO> {
    return this.http.patch<RefundReviewDTO>(
      API_CONFIG.endpoints.refunds.approve(refundId),
      payload,
      { withCredentials: true }
    );
  }

  downloadReceipt(refundId: string, itemId: string): Observable<Blob> {
    return this.http.get(API_CONFIG.endpoints.refunds.receipt(refundId, itemId), {
      responseType: 'blob',
      withCredentials: true,
    });
  }
  uploadReceipt(refundId: string, file: File): Observable<RefundReceiptUploadDTO> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<RefundReceiptUploadDTO>(
      API_CONFIG.endpoints.refunds.receipts(refundId),
      formData,
      { withCredentials: true }
    );
  }

  createRefundItem(refundId: string, payload: RefundItemCreatePayload): Observable<RefundItemDTO> {
    return this.http.post<RefundItemDTO>(
      API_CONFIG.endpoints.refunds.items(refundId),
      payload,
      { withCredentials: true }
    );
  }

  filterItems(
    refundId: string,
    payload: RefundItemFilterPayload,
    page: number = 0,
    size: number = 5
  ): Observable<Page<RefundItemDTO>> {
    const params = new HttpParams().set('page', page).set('size', size);
    return this.http.post<Page<RefundItemDTO>>(
      API_CONFIG.endpoints.refunds.itemsFilter(refundId),
      payload,
      { params, withCredentials: true }
    );
  }
}
