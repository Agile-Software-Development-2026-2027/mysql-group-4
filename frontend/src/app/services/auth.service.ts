import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, of, switchMap, tap } from 'rxjs';

import { API_CONFIG } from '../core/config/api.config';
import { LoginRequest, User, UserCreate } from '../core/models';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  private _currentUser = signal<User | null>(null);
  private _isLoading = signal<boolean>(false);

  readonly currentUser = this._currentUser.asReadonly();
  readonly isLoading = this._isLoading.asReadonly();
  readonly isAuthenticated = computed(() => !!this._currentUser());

  getUser(): User | null {
    return this._currentUser();
  }

  checkSession(): Observable<User | null> {
    this._isLoading.set(true);
    return this.http
      .get<User>(API_CONFIG.endpoints.users.me, { withCredentials: true })
      .pipe(
        tap((user) => {
          this._currentUser.set(user);
        }),
        catchError(() => {
          this._currentUser.set(null);
          return of(null);
        }),
        finalize(() => {
          this._isLoading.set(false);
        })
      );
  }

  login(credentials: LoginRequest): Observable<User | null> {
    this._isLoading.set(true);

    const body = new HttpParams()
      .set('username', credentials.email)
      .set('password', credentials.password);

    const headers = new HttpHeaders({
      'Content-Type': 'application/x-www-form-urlencoded',
    });

    return this.http
      .post(API_CONFIG.endpoints.auth.login, body.toString(), {
        headers,
        withCredentials: true,
      })
      .pipe(
        switchMap(() => this.checkSession()),
        catchError((error) => {
          this._currentUser.set(null);
          throw error;
        }),
        finalize(() => {
          this._isLoading.set(false);
        })
      );
  }

  register(payload: UserCreate): Observable<User> {
    this._isLoading.set(true);

    return this.http
      .post<User>(API_CONFIG.endpoints.auth.register, payload, {
        withCredentials: true,
      })
      .pipe(
        finalize(() => {
          this._isLoading.set(false);
        })
      );
  }

  logout(): Observable<void> {
    this._isLoading.set(true);

    return this.http
      .post<void>(API_CONFIG.endpoints.auth.logout, {}, { withCredentials: true })
      .pipe(
        catchError(() => of(undefined as void)),
        finalize(() => {
          this._currentUser.set(null);
          this._isLoading.set(false);
          this.router.navigate(['/']);
        })
      );
  }
}
