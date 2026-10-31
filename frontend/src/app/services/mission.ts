import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { MissionDTO, MissionStatus } from '../core/models/mission-dto';
import { Page } from '../core/models/page';

@Injectable({
  providedIn: 'root',
})
export class MissionService {
  private readonly API_URL = 'http://localhost:8000/api/v1/missions';

  constructor(private http: HttpClient) {}

  getPendingMissions(fundManagerId?: string): Observable<Page<MissionDTO>> {
    const filters = fundManagerId ? { fund_manager_id: fundManagerId } : {};
    return this.http.post<Page<MissionDTO>>(
      `${this.API_URL}/pending/filter`,
      filters,
      { withCredentials: true }
    );
  }

  getAcceptedMissions(fundManagerId?: string): Observable<Page<MissionDTO>> {
    const filters: any = { status: MissionStatus.ACCEPTED };
    if (fundManagerId) {
      filters.fund_manager_id = fundManagerId;
    }
    return this.http.post<Page<MissionDTO>>(
      `${this.API_URL}/filter`,
      filters,
      { withCredentials: true }
    );
  }

  getRejectedMissions(fundManagerId?: string): Observable<Page<MissionDTO>> {
    const filters = fundManagerId ? { fund_manager_id: fundManagerId } : {};
    return this.http.post<Page<MissionDTO>>(
      `${this.API_URL}/rejected/filter`,
      filters,
      { withCredentials: true }
    );
  }

  acceptMission(missionId: string, responseNote?: string): Observable<MissionDTO> {
    const body = responseNote ? { response: responseNote } : {};
    return this.http.patch<MissionDTO>(
      `${this.API_URL}/${missionId}/accept`,
      body,
      { withCredentials: true }
    );
  }

  rejectMission(missionId: string, responseNote?: string): Observable<MissionDTO> {
    const body = responseNote ? { response: responseNote } : {};
    return this.http.patch<MissionDTO>(
      `${this.API_URL}/${missionId}/reject`,
      body,
      { withCredentials: true }
    );
  }
}
