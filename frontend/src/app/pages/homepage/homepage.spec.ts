import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting, TestRequest } from '@angular/common/http/testing';
import { Homepage } from './homepage';
import { API_CONFIG } from '../../core/config/api.config';
import { FundDTO, MissionDTO, MissionStatus, User } from '../../core/models';
import { AuthService } from '../../services/auth.service';

const MY_FC = 'RSSMRA80A01H501U';

function mission(id: string, startsAt: string, endsAt: string): MissionDTO {
  return {
    id, missionType: 'RESEARCH', status: MissionStatus.ACCEPTED, subject: `Mission ${id}`,
    destination: 'Roma', estimatedCost: '100.00', startsAt, endsAt,
    requesterId: 'u1', fundManagerId: 'u1', createdAt: '', updatedAt: '',
  };
}

describe('Homepage', () => {
  let fixture: ComponentFixture<Homepage>;
  let component: Homepage;
  let element: HTMLElement;
  let httpMock: HttpTestingController;

  const sentRequests = (): TestRequest[] => httpMock.match((req) => req.url.endsWith('/missions/sent/filter'));
  const fundsRequest = () => httpMock.expectOne((req) => req.url === API_CONFIG.endpoints.funds.base);

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Homepage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([
          { path: 'home', component: Homepage },
          { path: '**', component: Homepage }
        ])
      ],
    }).compileComponents();

    vi.spyOn(TestBed.inject(AuthService), 'getUser').mockReturnValue({ fiscalCode: MY_FC } as User);
    fixture = TestBed.createComponent(Homepage);
    component = fixture.componentInstance;
    element = fixture.nativeElement;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    // La topbar conta le missioni da approvare: non riguarda questa pagina.
    httpMock.match((req) => req.url.includes('/to-approve/'));
    httpMock.verify();
  });

  function flushAll(upcoming: MissionDTO[], completed: number, funds: FundDTO[]) {
    const [next, done] = sentRequests();
    expect(next.request.body).toMatchObject({ status: MissionStatus.ACCEPTED, endsAtFrom: expect.any(String) });
    expect(done.request.body).toMatchObject({ status: MissionStatus.ACCEPTED, endsAtTo: expect.any(String) });
    next.flush({ content: upcoming, totalElements: upcoming.length });
    done.flush({ content: [], totalElements: completed });
    fundsRequest().flush({ content: funds });
    fixture.detectChanges();
  }

  it('should render the topbar component', () => {
    flushAll([], 0, []);
    expect(element.querySelector('app-topbar')).toBeTruthy();
  });

  it('should show the site name', () => {
    flushAll([], 0, []);
    expect(element.querySelector('h1')?.textContent).toContain(component.siteName);
  });

  it('should render the overview cards and the shortcut cards', () => {
    flushAll([], 0, []);
    expect(element.querySelectorAll('.overview-grid .card').length).toBe(2);
    expect(element.querySelectorAll('.cards-grid .card').length).toBe(3);
  });

  it('should show the earliest upcoming mission', () => {
    flushAll([
      mission('later', '2099-06-01T08:00:00', '2099-06-02T20:00:00'),
      mission('sooner', '2099-01-10T08:00:00', '2099-01-12T20:00:00'),
    ], 0, []);
    const card = element.querySelector('.next-mission')!;
    expect(card.textContent).toContain('Mission sooner');
    expect(card.textContent).toContain('10/01/2099');
    expect(card.querySelector('.badge')).toBeNull();
  });

  it('should say when there are no upcoming missions', () => {
    flushAll([], 0, []);
    expect(element.querySelector('.overview-card')?.textContent).toContain('No upcoming missions.');
  });

  it('should count my free funds and the completed missions', () => {
    flushAll([], 4, [
      { id: 'f1', name: 'A', amount: '200.00', responsibleFc: MY_FC, lockedByMissionId: null },
      { id: 'f2', name: 'B', amount: '50.50', responsibleFc: MY_FC, lockedByMissionId: null },
      { id: 'f3', name: 'C', amount: '999.00', responsibleFc: MY_FC, lockedByMissionId: 'm1' },
      { id: 'f4', name: 'D', amount: '10.00', responsibleFc: 'VRDLGI85B02F205X' },
    ]);
    expect(component.activeFunds()).toBe(2);
    expect(component.totalFunds()).toBe(3);
    const stats = element.querySelectorAll('.stat');
    expect(stats[0].textContent).toContain('250.50');
    expect(stats[1].querySelector('.stat__value')?.textContent).toContain('4');
  });
});
