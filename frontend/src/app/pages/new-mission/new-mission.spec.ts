import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';

import { NewMissionComponent } from './new-mission';
import { API_CONFIG } from '../../core/config/api.config';
import { EmploymentLevel, User } from '../../core/models';
import { AuthService } from '../../services/auth.service';

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
      subject: 'Conference', destination: 'Rome', startDate: '2026-12-01', endDate: '2026-12-03',
      estimatedCost: 300,
    });
    component.confirmSubmit();

    const req = httpMock.expectOne(API_CONFIG.endpoints.missions.create);
    expect(req.request.body.fundManagerId).toBe('other-id');
  });
});
