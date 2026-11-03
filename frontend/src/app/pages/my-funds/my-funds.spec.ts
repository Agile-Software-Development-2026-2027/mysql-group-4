import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { MyFunds } from './my-funds';
import { API_CONFIG } from '../../core/config/api.config';
import { FundDTO, User } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { ToastService } from '../../services/toast.service';

const MY_FC = 'RSSMRA80A01H501U';
const freeFund: FundDTO = { id: 'f1', name: 'PRIN', amount: '200.00', responsibleFc: MY_FC, lockedByMissionId: null };
const lockedFund: FundDTO = {
  id: 'f2', name: 'Erasmus', amount: '200.00', responsibleFc: MY_FC, lockedByMissionId: 'm1',
  missionSubject: 'Convegno', requestedAmount: '150.00', requesterName: 'Luigi Verdi',
};
const otherFund: FundDTO = { id: 'f3', name: 'Altro', amount: '10.00', responsibleFc: 'VRDLGI85B02F205X' };

describe('MyFunds', () => {
  let component: MyFunds;
  let fixture: ComponentFixture<MyFunds>;
  let httpMock: HttpTestingController;
  let toastService: ToastService;

  const fundUrl = (id: string) => `${API_CONFIG.endpoints.funds.base}/${id}`;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MyFunds],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    vi.spyOn(TestBed.inject(AuthService), 'getUser').mockReturnValue({ fiscalCode: MY_FC } as User);
    fixture = TestBed.createComponent(MyFunds);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    toastService = TestBed.inject(ToastService);
    fixture.detectChanges();

    httpMock
      .expectOne((req) => req.url === API_CONFIG.endpoints.funds.base)
      .flush({ content: [freeFund, lockedFund, otherFund] });
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.match((req) => req.url.includes('/missions/'));
    httpMock.verify();
  });

  it('shows only my funds, with available over total and the requester on assigned ones', () => {
    const tiles: HTMLElement[] = Array.from(fixture.nativeElement.querySelectorAll('.fund-tile'));
    expect(tiles.length).toBe(2);
    expect(tiles[0].classList).not.toContain('is-locked');
    expect(tiles[0].textContent).toContain('200.00');
    expect(tiles[1].classList).toContain('is-locked');
    expect(tiles[1].textContent).toContain('50.00');
    expect(tiles[1].textContent).toContain('Luigi Verdi');
  });

  it('deletes a free fund without asking', () => {
    component.openDetail(freeFund);
    component.requestDelete(freeFund);

    const req = httpMock.expectOne((r) => r.url === fundUrl('f1'));
    expect(req.request.method).toBe('DELETE');
    expect(req.request.params.has('force')).toBe(false);
    req.flush(null);

    expect(component.funds().map((f) => f.id)).toEqual(['f2']);
    expect(component.selectedFund()).toBeNull();
    expect(toastService.toasts()[0]).toMatchObject({ type: 'success', title: 'Fund Deleted' });
  });

  it('asks for confirmation before deleting an assigned fund', () => {
    component.openDetail(lockedFund);
    component.requestDelete(lockedFund);
    fixture.detectChanges();

    httpMock.expectNone((r) => r.url === fundUrl('f2'));
    expect(fixture.nativeElement.querySelector('.confirm-modal').textContent).toContain('Luigi Verdi');

    component.cancelDelete();
    expect(component.confirmingDelete()).toBe(false);

    component.requestDelete(lockedFund);
    component.deleteFund(lockedFund, true);
    const req = httpMock.expectOne((r) => r.url === fundUrl('f2'));
    expect(req.request.params.get('force')).toBe('true');
    req.flush(null);
    expect(component.funds().map((f) => f.id)).toEqual(['f1']);
  });

  it('asks for confirmation if the fund was taken in the meantime', () => {
    component.openDetail(freeFund);
    component.requestDelete(freeFund);
    httpMock.expectOne((r) => r.url === fundUrl('f1')).flush({}, { status: 409, statusText: 'Conflict' });

    httpMock.expectOne((r) => r.url === API_CONFIG.endpoints.funds.base).flush({
      content: [{ ...freeFund, lockedByMissionId: 'm2', requesterName: 'Anna Bianchi' }],
    });
    expect(component.confirmingDelete()).toBe(true);
    expect(component.selectedFund()?.requesterName).toBe('Anna Bianchi');
  });
});
