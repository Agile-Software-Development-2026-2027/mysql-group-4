import { Component, OnInit, ChangeDetectorRef, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { RouterLink, ActivatedRoute, Router } from '@angular/router';
import { MissionService } from '../../services/mission.service';
import { FundService } from '../../services/fund.service';
import { RefundService } from '../../services/refund.service';
import { AuthService } from '../../services/auth.service';
import { ToastService } from '../../services/toast.service';
import { FundDTO, MissionDTO, RefundRequestDTO, RefundStatus } from '../../core/models';
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
  refundReviewMissions: MissionDTO[] = [];
  completedMissions: MissionDTO[] = [];
  rejectedMissions: MissionDTO[] = [];

  private fundService = inject(FundService);
  private refundService = inject(RefundService);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  associatedRefund = signal<RefundRequestDTO | null>(null);
  isCreatingRefund = signal<boolean>(false);

  documents = signal<any[]>([]);
  isLoadingDocuments = signal(false);

  myFunds = signal<FundDTO[]>([]);
  selectedFundId = signal('');

  fundQuery = signal('');
  showFundSuggestions = signal(false);
  activeSuggestion = signal(-1);
  filteredFunds = computed(() => {
    const query = this.fundQuery().trim().toLowerCase();
    return this.myFunds().filter((fund) => fund.name.toLowerCase().includes(query));
  });

  associatedFundName = signal<string | null>(null);
  // Fondo da cui si è arrivati (My Funds): "Go back" torna lì invece che all'elenco missioni.
  private returnToFundId: string | null = null;

  viewMode: 'manager' | 'requester' = 'manager';
  pageTitle: string = 'Mission Funds Management';

  get canManageDecisions(): boolean {
    return this.viewMode === 'manager';
  }

  constructor(
    private missionService: MissionService,
    private cdr: ChangeDetectorRef
  ) { }

  ngOnInit() {
    this.route.queryParams.subscribe(params => {
      this.viewMode = params['view'] === 'requester' ? 'requester' : 'manager';
      this.pageTitle = this.viewMode === 'manager'
        ? 'Mission Funds Management'
        : 'My Mission Requests';

      this.returnToFundId = params['fundId'] ?? null;
      this.loadAllMissions();
      if (params['missionId']) {
        this.openMissionById(params['missionId']);
      }
    });
  }

  // Usato dai link esterni (es. My Funds): carica la missione e ne apre subito il dettaglio.
  private openMissionById(missionId: string) {
    this.missionService.getMission(missionId).subscribe({
      next: (mission) => {
        this.openDetail(mission);
        this.cdr.detectChanges();
      },
      error: () => this.toastService.showError('Unable to load the mission.', 'Mission'),
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
      this.missionService.getCompletedMissions(myId).subscribe(page => {
        this.completedMissions = page.content || [];
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
        this.splitByRefundStatus(page.content || []);
      });
      this.missionService.getMyCompletedMissions().subscribe(page => {
        this.completedMissions = page.content || [];
        this.cdr.detectChanges();
      });
      this.missionService.getMyRejectedMissions().subscribe(page => {
        this.rejectedMissions = page.content || [];
        this.cdr.detectChanges();
      });
    }
  }

  // Le missioni terminate con un rimborso già inviato passano in "Refund Review" finché non viene approvato.
  private splitByRefundStatus(missions: MissionDTO[]) {
    const ended = missions.filter((mission) => this.isMissionEnded(mission));
    if (ended.length === 0) {
      this.approvedMissions = missions;
      this.refundReviewMissions = [];
      this.cdr.detectChanges();
      return;
    }

    forkJoin(
      ended.map((mission) =>
        this.refundService.getByMissionId(mission.id).pipe(catchError(() => of(null)))
      )
    ).subscribe((refunds) => {
      const inReview = new Set(
        refunds
          .filter((refund) => refund?.status === RefundStatus.SUBMITTED)
          .map((refund) => refund!.missionId)
      );
      this.approvedMissions = missions.filter((mission) => !inReview.has(mission.id));
      this.refundReviewMissions = missions.filter((mission) => inReview.has(mission.id));
      this.cdr.detectChanges();
    });
  }

  toggleSection(section: string) {
    this.activeSection = this.activeSection === section ? '' : section;
  }

  isMissionEnded(mission: MissionDTO | null): boolean {
    if (!mission) return false;
    return new Date(mission.endsAt) <= new Date();
  }

  openDetail(mission: MissionDTO) {
    this.selectedMission = mission;
    this.isDetailView = true;
    this.selectedFundId.set('');
    this.fundQuery.set('');
    this.showFundSuggestions.set(false);
    this.associatedFundName.set(null);
    this.associatedRefund.set(null);
    this.loadMissionDocuments(mission.id);

    if (mission.status === 'ACCEPTED' || mission.status === 'COMPLETED') {
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

      this.refundService.getByMissionId(mission.id).subscribe({
        next: (refund) => {
          this.associatedRefund.set(refund);
          this.cdr.detectChanges();
        },
        error: () => {
          this.associatedRefund.set(null);
          this.cdr.detectChanges();
        }
      });
    }

    if (this.canDecide(mission)) {
      this.loadMyFunds();
    }
  }

  private loadMissionDocuments(missionId: string) {
    this.isLoadingDocuments.set(true);
    this.missionService.getDocuments(missionId).subscribe({
      next: (docs) => {
        this.documents.set(docs || []);
        this.isLoadingDocuments.set(false);
      },
      error: () => {
        this.isLoadingDocuments.set(false);
        this.documents.set([]);
        this.toastService.showError('Unable to load attached documents.', 'Documents');
      }
    });
  }

  viewDocument(doc: any) {
    if (!this.selectedMission?.id) {
      this.toastService.showError('No mission selected.', 'View Error');
      return;
    }
    this.missionService.downloadDocument(this.selectedMission.id, doc.id).subscribe({
      next: (blob: Blob) => {
        const pdfBlob = new Blob([blob], { type: 'application/pdf' });
        const fileURL = URL.createObjectURL(pdfBlob);
        window.open(fileURL, '_blank');
      },
      error: () => {
        this.toastService.showError('Could not open the PDF document.', 'View Error');
      }
    });
  }

  canDecide(mission: MissionDTO): boolean {
    return this.canManageDecisions && mission.status === 'PENDING' && mission.fundManagerId === this.authService.getUser()?.id;
  }

  // Un fondo è selezionabile se il suo residuo copre il costo della missione da approvare.
  canCover(fund: FundDTO): boolean {
    const remaining = Number(fund.remainingAmount);
    return remaining > 0 && remaining >= Number(this.selectedMission?.estimatedCost ?? 0);
  }

  hasUsableFunds(): boolean {
    return this.myFunds().some((fund) => this.canCover(fund));
  }

  onFundQueryInput(value: string) {
    this.fundQuery.set(value);
    this.selectedFundId.set('');
    this.activeSuggestion.set(-1);
    this.showFundSuggestions.set(true);
  }

  selectFund(fund: FundDTO) {
    if (!this.canCover(fund)) {
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
        if (this.canCover(funds[index])) {
          this.activeSuggestion.set(index);
          return;
        }
      }
    } else if (event.key === 'Enter' && this.showFundSuggestions()) {
      event.preventDefault();
      const fund = funds[this.activeSuggestion()] ?? funds.find((f) => this.canCover(f));
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

  goBack() {
    if (this.returnToFundId) {
      this.router.navigate(['/fund'], { queryParams: { fundId: this.returnToFundId } });
      return;
    }
    this.closeDetail();
  }

  closeDetail() {
    this.isDetailView = false;
    this.selectedMission = null;
    this.associatedFundName.set(null);
    this.associatedRefund.set(null);
    this.documents.set([]);
    if (this.route.snapshot.queryParams['missionId']) {
      this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { view: this.viewMode },
      });
    }
  }

  createAndGoToRefund(missionId: string): void {
    this.isCreatingRefund.set(true);
    this.refundService.createRefundRequest(missionId).subscribe({
      next: (refund) => {
        this.isCreatingRefund.set(false);
        this.toastService.showSuccess('Refund request created successfully.', 'Refund Created');
        this.router.navigate(['/refund', refund.id]);
      },
      error: (err) => {
        this.isCreatingRefund.set(false);
        this.toastService.showError(err?.error?.message ?? 'Unable to create refund request.', 'Error');
      }
    });
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
