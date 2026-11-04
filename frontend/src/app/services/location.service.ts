import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { API_CONFIG } from '../core/config/api.config';

export interface LocationResponse {
  display_name: string;
  lat: string;
  lon: string;
  type?: string;
  address?: Record<string, any>;
}

@Injectable({
  providedIn: 'root',
})
export class LocationService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${API_CONFIG.baseUrl}/api/v1/locations`;

  autocomplete(query: string): Observable<LocationResponse[]> {
    if (!query || query.trim().length < 3) {
      return of([]);
    }
    return this.http
      .get<LocationResponse[]>(`${this.baseUrl}/autocomplete`, {
        params: { q: query.trim() },
        withCredentials: true,
      })
      .pipe(catchError(() => of([])));
  }
}