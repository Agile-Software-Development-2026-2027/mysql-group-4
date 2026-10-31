import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_CONFIG } from '../core/config/api.config';
import { MissionCreatePayload, MissionDTO } from '../core/models/mission.model';

@Injectable({
  providedIn: 'root',
})
export class MissionService {
  private http = inject(HttpClient);

  createMission(payload: MissionCreatePayload): Observable<MissionDTO> {
    return this.http.post<MissionDTO>(
      API_CONFIG.endpoints.missions.create,
      payload,
      { withCredentials: true }
    );
  }
}
