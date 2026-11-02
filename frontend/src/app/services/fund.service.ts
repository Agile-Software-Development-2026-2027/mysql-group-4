import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_CONFIG } from '../core/config/api.config';
import { FundCreatePayload, FundDTO, User } from '../core/models';

@Injectable({
  providedIn: 'root',
})
export class FundService {
  private http = inject(HttpClient);

  createFund(payload: FundCreatePayload): Observable<FundDTO> {
    return this.http.post<FundDTO>(API_CONFIG.endpoints.funds.base, payload, {
      withCredentials: true,
    });
  }

  getFundManagers(): Observable<User[]> {
    return this.http.get<User[]>(API_CONFIG.endpoints.users.fundManagers, {
      withCredentials: true,
    });
  }
}
