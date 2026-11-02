import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';

import { AddFund } from './add-fund';
import { API_CONFIG } from '../../core/config/api.config';
import { ToastService } from '../../services/toast.service';

describe('AddFund', () => {
  let component: AddFund;
  let fixture: ComponentFixture<AddFund>;
  let httpMock: HttpTestingController;
  let toastService: ToastService;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AddFund],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(AddFund);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    toastService = TestBed.inject(ToastService);
    router = TestBed.inject(Router);
    vi.spyOn(router, 'navigate').mockResolvedValue(true);
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should not submit an invalid form', () => {
    component.onSubmit();
    httpMock.expectNone(API_CONFIG.endpoints.funds.base);
    expect(component.isFieldInvalid('name')).toBe(true);
    expect(component.isFieldInvalid('amount')).toBe(true);
  });

  it('should reject a negative amount', () => {
    component.fundForm.setValue({ name: 'Fund', description: '', amount: -5 });
    expect(component.fundForm.get('amount')?.hasError('min')).toBe(true);
  });

  it('should post the fund without the responsible, show a toast and go home', () => {
    component.fundForm.setValue({ name: '  PRIN 2026 ', description: '', amount: 1500.5 });
    component.onSubmit();

    const req = httpMock.expectOne(API_CONFIG.endpoints.funds.base);
    expect(req.request.method).toBe('POST');
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.body).toEqual({ name: 'PRIN 2026', description: null, amount: 1500.5 });

    req.flush({ id: '1', name: 'PRIN 2026', amount: '1500.50', responsibleFc: 'RSSMRA80A01H501U' });
    expect(toastService.toasts()[0]).toMatchObject({ type: 'success', title: 'Fund Created' });
    expect(router.navigate).toHaveBeenCalledWith(['/home']);
    expect(component.isSaving()).toBe(false);
  });

  it('should show the backend error in a toast and stay on the page', () => {
    component.fundForm.setValue({ name: 'Fund', description: '', amount: 10 });
    component.onSubmit();

    httpMock
      .expectOne(API_CONFIG.endpoints.funds.base)
      .flush({ message: 'User is inactive' }, { status: 403, statusText: 'Forbidden' });
    expect(toastService.toasts()[0]).toMatchObject({ type: 'error', message: 'User is inactive' });
    expect(router.navigate).not.toHaveBeenCalled();
  });
});
