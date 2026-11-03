import { Component, OnInit, ChangeDetectorRef, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { MissionService } from '../../services/mission.service';
import { FundService } from '../../services/fund.service';
import { AuthService } from '../../services/auth.service';
import { ToastService } from '../../services/toast.service';
import { FundDTO, MissionDTO } from '../../core/models';
import { Topbar } from '../../components/topbar/topbar';

@Component({
  selector: 'app-mission-review',
  standalone: true,
  imports: [CommonModule, RouterLink, Topbar],
  templateUrl: './mission-review.html',
  styleUrls: ['./mission-review.scss']
})
export class MissionReview implements OnInit {
  isDetailView = false;
  activeSection = 'pending';
  selectedMission: MissionDTO | null = null;

  pendingMissions: MissionDTO[] = [];
  approvedMissions: MissionDTO[] = [];
  rejectedMissions: MissionDTO[] = [];

  private fundService = inject(FundService);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);
  private route = inject(ActivatedRoute);

  myFunds = signal<FundDTO[]>([]);
  selectedFundId = signal('');
  hasFreeFunds = computed(() => this.myFunds().some((fund) => this.isFundFree(fund)));

  fundQuery = signal('');
  showFundSuggestions = signal(false);
  activeSuggestion = signal(-1);
  filteredFunds = computed(() => {
    const query = this.fundQuery().trim().toLowerCase();
    return this.myFunds().filter((fund) => fund.name.toLowerCase().includes(query));
  });

  associatedFundName = signal<string | null>(null);

  viewMode: 'manager' | 'requester' = 'manager';
  pageTitle: string = 'Mission Funds Management';

  get canManageDecisions(): boolean {
    return this.viewMode === 'manager';
  }

  constructor(
    private missionService: MissionService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.route.queryParams.subscribe(params => {
      this.viewMode = params['view'] === 'requester' ? 'requester' : 'manager';
      this.pageTitle = this.viewMode === 'manager'
        ? 'Mission Funds Management'
        : 'My Mission Requests';

      this.loadAllMissions();
    });
  }

  loadAllMissions() {
    const myId = this.authService.getUser()?.id;

    if (this.viewMode === 'manager') {
      this.missionService.getPendingMissions(myId).subscribe(page => {
        this.pendingMissions = page.content || [];
        this.cdr.detectChanges();
      });
      this.missionService.getAcceptedMissions(myId).subscribe(page => {
        this.approvedMissions = page.content || [];
        this.cdr.detectChanges();
      });
      this.missionService.getRejectedMissions(myId).subscribe(page => {
        this.rejectedMissions = page.content || [];
        this.cdr.detectChanges();
      });
    } else {
      this.missionService.getMyPendingMissions().subscribe(page => {
        this.pendingMissions = page.content || [];
        this.cdr.detectChanges();
      });
      this.missionService.getMyAcceptedMissions().subscribe(page => {
        this.approvedMissions = page.content || [];
        this.cdr.detectChanges();
      });
      this.missionService.getMyRejectedMissions().subscribe(page => {
        this.rejectedMissions = page.content || [];
        this.cdr.detectChanges();
      });
    }
  }

  toggleSection(section: string) {
    this.activeSection = this.activeSection === section ? '' : section;
  }

  openDetail(mission: MissionDTO) {
    this.selectedMission = mission;
    this.isDetailView = true;
    this.selectedFundId.set('');
    this.fundQuery.set('');
    this.showFundSuggestions.set(false);
    this.associatedFundName.set(null);

    if (mission.status === 'ACCEPTED') {
      this.fundService.getByMissionId(mission.id).subscribe({
        next: (fund) => {
          if (fund) {
            this.associatedFundName.set(fund.name);
          }
        },
        error: () => {
          this.associatedFundName.set(null);
        }
      });
    }

    if (this.canDecide(mission)) {
      this.loadMyFunds();
    }
  }

  canDecide(mission: MissionDTO): boolean {
    return this.canManageDecisions && mission.status === 'PENDING' && mission.fundManagerId === this.authService.getUser()?.id;
  }

  isFundFree(fund: FundDTO): boolean {
    return !fund.lockedByMissionId;
  }

  onFundQueryInput(value: string) {
    this.fundQuery.set(value);
    this.selectedFundId.set('');
    this.activeSuggestion.set(-1);
    this.showFundSuggestions.set(true);
  }

  selectFund(fund: FundDTO) {
    if (!this.isFundFree(fund)) {
      return;
    }
    this.selectedFundId.set(fund.id);
    this.fundQuery.set(fund.name);
    this.showFundSuggestions.set(false);
  }

  onFundKeydown(event: KeyboardEvent) {
    const funds = this.filteredFunds();
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      this.showFundSuggestions.set(true);
      const step = event.key === 'ArrowDown' ? 1 : -1;
      let index = this.activeSuggestion();
      for (let i = 0; i < funds.length; i++) {
        index = (index + step + funds.length) % funds.length;
        if (this.isFundFree(funds[index])) {
          this.activeSuggestion.set(index);
          return;
        }
      }
    } else if (event.key === 'Enter' && this.showFundSuggestions()) {
      event.preventDefault();
      const fund = funds[this.activeSuggestion()] ?? funds.find((f) => this.isFundFree(f));
      if (fund) {
        this.selectFund(fund);
      }
    } else if (event.key === 'Escape') {
      this.showFundSuggestions.set(false);
    }
  }

  private loadMyFunds() {
    const myFiscalCode = this.authService.getUser()?.fiscalCode;
    this.fundService.getMyFunds().subscribe({
      next: (page) => this.myFunds.set(
        page.content.filter((fund) => fund.responsibleFc === myFiscalCode)
      ),
      error: () => this.toastService.showError('Unable to load your funds.', 'Funds'),
    });
  }

  closeDetail() {
    this.isDetailView = false;
    this.selectedMission = null;
    this.associatedFundName.set(null);
  }

  accept(id: string, note: string) {
    const fundId = this.selectedFundId();
    if (!fundId) {
      this.toastService.showError('Choose the fund to charge before approving.', 'Missing Fund');
      return;
    }
    this.missionService.acceptMission(id, fundId, note).subscribe({
      next: () => {
        this.toastService.showSuccess('Mission approved and fund assigned.', 'Mission Approved');
        this.loadAllMissions();
        this.closeDetail();
      },
      error: (err) => {
        console.error('Errore durante approvazione:', err);
        this.toastService.showError(err?.error?.message ?? 'Unable to approve the mission.', 'Approval Error');
        this.selectedFundId.set('');
        this.fundQuery.set('');
        this.loadMyFunds();
      }
    });
  }

  reject(id: string, note: string) {
    this.missionService.rejectMission(id, note).subscribe({
      next: () => {
        this.loadAllMissions();
        this.closeDetail();
      },
      error: (err) => console.error('Errore durante rifiuto:', err)
    });
  }
}
