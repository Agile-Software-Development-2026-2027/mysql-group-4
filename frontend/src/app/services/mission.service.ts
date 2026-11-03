import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_CONFIG } from '../core/config/api.config';
import { MissionCreatePayload, MissionDTO, MissionStatus, Page } from '../core/models';

@Injectable({
  providedIn: 'root',
})
export class MissionService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${API_CONFIG.baseUrl}/api/v1/missions`;

  createMission(payload: MissionCreatePayload): Observable<MissionDTO> {
    return this.http.post<MissionDTO>(
      API_CONFIG.endpoints.missions.create,
      payload,
      { withCredentials: true }
    );
  }

  getPendingMissions(fundManagerId?: string): Observable<Page<MissionDTO>> {
    const filters = fundManagerId ? { fund_manager_id: fundManagerId } : {};
    return this.http.post<Page<MissionDTO>>(
      `${this.baseUrl}/pending/filter`,
      filters,
      { withCredentials: true }
    );
  }

  getAcceptedMissions(fundManagerId?: string): Observable<Page<MissionDTO>> {
    const filters: Record<string, unknown> = { status: MissionStatus.ACCEPTED };
    if (fundManagerId) {
      filters['fund_manager_id'] = fundManagerId;
    }
    return this.http.post<Page<MissionDTO>>(
      `${this.baseUrl}/filter`,
      filters,
      { withCredentials: true }
    );
  }

  getRejectedMissions(fundManagerId?: string): Observable<Page<MissionDTO>> {
    const filters = fundManagerId ? { fund_manager_id: fundManagerId } : {};
    return this.http.post<Page<MissionDTO>>(
      `${this.baseUrl}/rejected/filter`,
      filters,
      { withCredentials: true }
    );
  }

  acceptMission(missionId: string, responseNote?: string): Observable<MissionDTO> {
    const body = responseNote ? { response: responseNote } : {};
    return this.http.patch<MissionDTO>(
      `${this.baseUrl}/${missionId}/accept`,
      body,
      { withCredentials: true }
    );
  }

  rejectMission(missionId: string, responseNote?: string): Observable<MissionDTO> {
    const body = responseNote ? { response: responseNote } : {};
    return this.http.patch<MissionDTO>(
      `${this.baseUrl}/${missionId}/reject`,
      body,
      { withCredentials: true }
    );
  }

  uploadDocument(missionId: string, file: File): Observable<any> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<any>(
      `${this.baseUrl}/${missionId}/documents`,
      formData,
      { withCredentials: true }
    );
  }

  getDocuments(missionId: string): Observable<any[]> {
    return this.http.get<any[]>(
      `${this.baseUrl}/${missionId}/documents`,
      { withCredentials: true }
    );
  }
}
