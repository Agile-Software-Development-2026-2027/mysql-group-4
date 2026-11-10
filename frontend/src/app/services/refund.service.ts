import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_CONFIG } from '../core/config/api.config';
import { RefundRequestCreatePayload, RefundRequestDTO } from '../core/models';

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
}
