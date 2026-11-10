import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';

import { NewMissionComponent } from './new-mission';
import { API_CONFIG } from '../../core/config/api.config';
import { EmploymentLevel, User } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { ToastService } from '../../services/toast.service';

const dateFromToday = (days: number): string => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-');
};

const makeUser = (id: string, surname: string, department: string): User => ({
  id, email: `${surname}@example.com`, name: 'Simone', surname, fiscalCode: `FC-${surname}`,
  department, employmentLevel: EmploymentLevel.RICERCATORE,
});

describe('NewMissionComponent fund manager selection', () => {
  let component: NewMissionComponent;
  let fixture: ComponentFixture<NewMissionComponent>;
  let httpMock: HttpTestingController;
  const me = makeUser('me-id', 'Leoni', 'Informatica');
  const other = makeUser('other-id', 'Leone', 'Matematica');

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewMissionComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    vi.spyOn(TestBed.inject(AuthService), 'getUser').mockReturnValue(me);
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    fixture = TestBed.createComponent(NewMissionComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  function loadManagers(): void {
    component.setFundSource('other');
    httpMock.expectOne(API_CONFIG.endpoints.users.fundManagers).flush([me, other]);
  }

  it('should list the other fund managers with their department only', () => {
    loadManagers();
    expect(component.managerOptions()).toEqual([
      { id: 'other-id', name: 'Simone Leone', department: 'Matematica' },
    ]);
  });

  it('should filter by name or department while typing and select one', () => {
    loadManagers();
    component.onManagerQueryInput('mate');
    expect(component.filteredManagers().map((m) => m.id)).toEqual(['other-id']);
    component.onManagerQueryInput('nothing');
    expect(component.filteredManagers()).toEqual([]);

    component.onManagerQueryInput('leone');
    component.selectManager(component.filteredManagers()[0]);
    expect(component.missionForm.get('fundManagerId')?.value).toBe('other-id');
    expect(component.managerQuery()).toBe('Simone Leone — Matematica');

    component.onManagerQueryInput('Simone Leon');
    expect(component.missionForm.get('fundManagerId')?.value).toBe('');
  });

  it('should require a manager only when another manager is chosen', () => {
    loadManagers();
    expect(component.missionForm.get('fundManagerId')?.hasError('required')).toBe(true);
    component.setFundSource('self');
    expect(component.missionForm.get('fundManagerId')?.valid).toBe(true);
  });

  it('should send the chosen manager as fund manager', () => {
    loadManagers();
    component.selectManager(component.managerOptions()[0]);
    component.missionForm.patchValue({
      subject: 'Conference', destination: 'Rome', startDate: dateFromToday(30), endDate: dateFromToday(32),
      estimatedCost: 300,
    });
    component.confirmSubmit();

    const req = httpMock.expectOne(API_CONFIG.endpoints.missions.create);
    expect(req.request.body.fundManagerId).toBe('other-id');
  });

  function loadOwnFunds(): void {
    httpMock.expectOne((req) => req.url === API_CONFIG.endpoints.funds.base).flush({
      content: [
        { id: 'taken', name: 'Preso', amount: '10', responsibleFc: me.fiscalCode, lockedByMissionId: 'm1' },
        { id: 'mine', name: 'Mio', amount: '500', responsibleFc: me.fiscalCode, lockedByMissionId: null },
      ],
      totalElements: 2, number: 0, size: 100,
    });
  }

  it('should load the own funds and require one when managing the mission yourself', () => {
    loadOwnFunds();
    expect(component.myFunds().map((f) => f.id)).toEqual(['taken', 'mine']);
    expect(component.missionForm.get('fundId')?.hasError('required')).toBe(true);

    component.selectOwnFund(component.myFunds()[0]);
    expect(component.missionForm.get('fundId')?.value).toBe('');
    component.selectOwnFund(component.myFunds()[1]);
    expect(component.missionForm.get('fundId')?.value).toBe('mine');
    expect(component.ownFundQuery()).toBe('Mio');
  });

  it('should send yourself as manager together with the chosen fund', () => {
    loadOwnFunds();
    component.selectOwnFund(component.myFunds()[1]);
    component.missionForm.patchValue({
      subject: 'Conference', destination: 'Rome', startDate: dateFromToday(30), endDate: dateFromToday(32),
      estimatedCost: 300,
    });
    component.confirmSubmit();

    const req = httpMock.expectOne(API_CONFIG.endpoints.missions.create);
    expect(req.request.body.fundManagerId).toBe('me-id');
    expect(req.request.body.fundId).toBe('mine');

    req.flush({ id: 'mission-id', status: 'ACCEPTED' });
    expect(TestBed.inject(ToastService).toasts()[0]).toMatchObject({ type: 'success', title: 'Mission Approved' });
  });

  it('should reject a departure today or in the past and accept one from tomorrow', () => {
    const form = component.missionForm;
    form.patchValue({ startDate: dateFromToday(-1), endDate: dateFromToday(2) });
    expect(form.hasError('pastStart')).toBe(true);

    form.patchValue({ startDate: dateFromToday(0), startTime: '23:59' });
    expect(form.hasError('pastStart')).toBe(true);

    form.patchValue({ startDate: dateFromToday(1), startTime: '' });
    expect(form.hasError('pastStart')).toBe(false);
    expect(form.hasError('invalidPeriod')).toBe(false);
  });

  it('should not treat a year with more than 4 digits as a past date', () => {
    const form = component.missionForm;
    form.patchValue({ startDate: '202027-01-01' });
    expect(form.getError('pastStart')).toBe('Please enter a valid departure date.');

    form.patchValue({ startDate: dateFromToday(3), endDate: '202027-01-01' });
    expect(form.getError('invalidPeriod')).toBe('Please enter a valid return date.');

    form.patchValue({ endDate: dateFromToday(4) });
    expect(form.errors).toBeNull();
  });

  it('should let the date pickers start from tomorrow', () => {
    const start: HTMLInputElement = fixture.nativeElement.querySelector('#startDate');
    const end: HTMLInputElement = fixture.nativeElement.querySelector('#endDate');
    expect(component.firstAvailableDate).toBe(dateFromToday(1));
    expect(start.min).toBe(dateFromToday(1));
    expect(end.min).toBe(dateFromToday(1));

    component.missionForm.patchValue({ startDate: dateFromToday(5) });
    fixture.detectChanges();
    expect(end.min).toBe(dateFromToday(5));
  });

  it('should open a popup with the date error first when submitting a past departure', () => {
    component.missionForm.patchValue({ startDate: dateFromToday(-1), endDate: dateFromToday(2) });
    component.onSubmit();
    fixture.detectChanges();

    expect(component.showSummaryModal()).toBe(false);
    expect(component.formErrors()[0]).toBe('Departure date must be after today.');
    const popup: HTMLElement = fixture.nativeElement.querySelector('.error-modal');
    expect(popup.textContent).toContain('Invalid Mission Request');
    expect(popup.querySelectorAll('li')[0].textContent).toContain('Departure date must be after today.');
  });

  it('should list the missing fields in the popup and close it', () => {
    component.missionForm.patchValue({ startDate: dateFromToday(3), endDate: dateFromToday(4) });
    component.onSubmit();

    expect(component.formErrors()).toContain('Subject / Purpose Details is required.');
    expect(component.formErrors()).toContain('Location is required.');
    expect(component.formErrors()).not.toContain('Departure Date is required.');

    component.closeFormErrors();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.error-modal')).toBeNull();
  });

  it('should clear the date error when a past departure is changed to a future one', () => {
    const form = component.missionForm;
    form.patchValue({ startDate: dateFromToday(-1), endDate: dateFromToday(5) });
    component.onSubmit();
    expect(form.hasError('pastStart')).toBe(true);

    fixture.detectChanges();
    const startField = (): HTMLElement => fixture.nativeElement.querySelector('#startDate').parentElement;
    expect(startField().textContent).toContain('Departure date must be after today.');

    form.patchValue({ startDate: dateFromToday(3) });
    fixture.detectChanges();
    expect(form.hasError('pastStart')).toBe(false);
    expect(component.pastStartError()).toBeNull();
    expect(startField().textContent).not.toContain('Departure date must be after today.');
    expect(fixture.nativeElement.querySelector('#startDate').classList).not.toContain('is-invalid');
  });
});
