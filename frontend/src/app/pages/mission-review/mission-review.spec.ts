import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { MissionReview } from './mission-review';
import { API_CONFIG } from '../../core/config/api.config';
import { EmploymentLevel, MissionDTO, MissionStatus, User } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { ToastService } from '../../services/toast.service';

describe('MissionReview', () => {
  let component: MissionReview;
  let fixture: ComponentFixture<MissionReview>;
  let httpMock: HttpTestingController;
  const manager: User = {
    id: 'manager-id', email: 'm@example.com', name: 'Simone', surname: 'Leone',
    fiscalCode: 'LNESMN04L09C352U', department: 'Informatica', employmentLevel: EmploymentLevel.RICERCATORE,
  };
  const mission = {
    id: 'mission-id', status: MissionStatus.PENDING, fundManagerId: manager.id,
  } as MissionDTO;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MissionReview],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([])
      ]
    })
      .compileComponents();

    vi.spyOn(TestBed.inject(AuthService), 'getUser').mockReturnValue(manager);
    fixture = TestBed.createComponent(MissionReview);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);

    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  function loadFunds() {
    component.openDetail(mission);
    httpMock.expectOne((req) => req.url === API_CONFIG.endpoints.funds.base).flush({
      content: [
        { id: 'taken', name: 'Preso', amount: '10', responsibleFc: manager.fiscalCode, lockedByMissionId: 'm2' },
        { id: 'free', name: 'Libero', amount: '10', responsibleFc: manager.fiscalCode, lockedByMissionId: null },
      ],
      totalElements: 2, number: 0, size: 100,
    });
  }

  it('should show all the manager funds but let choose only the free ones', () => {
    loadFunds();
    expect(component.myFunds().map((f) => f.id)).toEqual(['taken', 'free']);
    expect(component.hasFreeFunds()).toBe(true);

    component.selectFund(component.myFunds()[0]);
    expect(component.selectedFundId()).toBe('');

    component.selectFund(component.myFunds()[1]);
    expect(component.selectedFundId()).toBe('free');
    expect(component.fundQuery()).toBe('Libero');
  });

  it('should skip assigned funds with the keyboard and filter while typing', () => {
    loadFunds();
    component.onFundKeydown(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
    expect(component.activeSuggestion()).toBe(1);
    component.onFundKeydown(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(component.selectedFundId()).toBe('free');

    component.onFundQueryInput('pres');
    expect(component.filteredFunds().map((f) => f.id)).toEqual(['taken']);
    expect(component.selectedFundId()).toBe('');
  });

  it('should not approve without choosing a fund', () => {
    const toast = TestBed.inject(ToastService);
    component.accept(mission.id, '');
    httpMock.expectNone(`${API_CONFIG.baseUrl}/api/v1/missions/${mission.id}/accept`);
    expect(toast.toasts()[0]).toMatchObject({ type: 'error', title: 'Missing Fund' });
  });

  it('should send the chosen fund when approving', () => {
    component.selectedFundId.set('free');
    component.accept(mission.id, 'Ok');
    const req = httpMock.expectOne(`${API_CONFIG.baseUrl}/api/v1/missions/${mission.id}/accept`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ fundId: 'free', response: 'Ok' });
  });
});
