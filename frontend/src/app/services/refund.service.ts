import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_CONFIG } from '../core/config/api.config';
import { Page } from '../core/models/page';
import {
  BoundingBoxDTO,
  CurrencyConversionDTO,
  MissionCurrencyProfileDTO,
  ReceiptAutocompleteDTO,
  ReceiptDetectionResponseDTO,
  RefundApprovePayload,
  RefundItemCreatePayload,
  RefundItemDTO,
  RefundItemFilterPayload,
  RefundItemUpdatePayload,
  RefundNotificationDTO,
  RefundReceiptUploadDTO,
  RefundRequestCreatePayload,
  RefundRequestDTO,
  RefundReviewDTO,
  RefundFilterPayload,
  RefundOverviewDTO,
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

  submitRefundRequest(refundId: string): Observable<RefundRequestDTO> {
    return this.http.patch<RefundRequestDTO>(
      API_CONFIG.endpoints.refunds.submit(refundId),
      {},
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

  extractReceipt(refundId: string, file: File): Observable<ReceiptAutocompleteDTO> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<ReceiptAutocompleteDTO>(
      API_CONFIG.endpoints.refunds.extractReceipt(refundId),
      formData,
      { withCredentials: true }
    );
  }

  detectReceipts(refundId: string, file: File): Observable<ReceiptDetectionResponseDTO> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<ReceiptDetectionResponseDTO>(
      API_CONFIG.endpoints.refunds.detectReceipts(refundId),
      formData,
      { withCredentials: true }
    );
  }

  batchProcessReceipts(
    refundId: string,
    file: File,
    boxes: BoundingBoxDTO[]
  ): Observable<RefundItemDTO[]> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('boxes', JSON.stringify(boxes));
    return this.http.post<RefundItemDTO[]>(
      API_CONFIG.endpoints.refunds.batchProcessReceipts(refundId),
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

  updateRefundItem(
    refundId: string,
    itemId: string,
    payload: RefundItemUpdatePayload
  ): Observable<RefundItemDTO> {
    return this.http.patch<RefundItemDTO>(
      API_CONFIG.endpoints.refunds.item(refundId, itemId),
      payload,
      { withCredentials: true }
    );
  }

  filterRefunds(payload: RefundFilterPayload): Observable<RefundOverviewDTO[]> {
    return this.http.post<RefundOverviewDTO[]>(
      API_CONFIG.endpoints.refunds.filter,
      payload,
      { withCredentials: true }
    );
  }

  getMyNotifications(): Observable<RefundNotificationDTO[]> {
    return this.http.get<RefundNotificationDTO[]>(
      API_CONFIG.endpoints.refunds.myNotifications,
      { withCredentials: true }
    );
  }

  markNotificationsSeen(refundIds: string[]): Observable<void> {
    return this.http.patch<void>(
      API_CONFIG.endpoints.refunds.markNotificationsSeen,
      { refundIds },
      { withCredentials: true }
    );
  }

  deleteRefundItem(refundId: string, itemId: string): Observable<void> {
    return this.http.delete<void>(API_CONFIG.endpoints.refunds.item(refundId, itemId), { withCredentials: true });
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

  convertCurrencyToEur(amount: number, currency: string): Observable<CurrencyConversionDTO> {
    return this.http.get<CurrencyConversionDTO>(API_CONFIG.endpoints.refunds.convertCurrency, {
      params: { amount: amount.toString(), currency },
      withCredentials: true,
    });
  }

  getCurrencyProfile(refundId: string): Observable<MissionCurrencyProfileDTO> {
    return this.http.get<MissionCurrencyProfileDTO>(
      API_CONFIG.endpoints.refunds.currencyProfile(refundId),
      { withCredentials: true }
    );
  }
}
