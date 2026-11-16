import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe, TitleCasePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { Topbar } from '../../components/topbar/topbar';
import { FundDTO } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { FundService } from '../../services/fund.service';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-my-funds',
  standalone: true,
  imports: [DatePipe, DecimalPipe, RouterLink, TitleCasePipe, Topbar],
  templateUrl: './my-funds.html',
  styleUrl: './my-funds.scss',
})
export class MyFunds implements OnInit {
  private fundService = inject(FundService);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  readonly currentUser = this.authService.currentUser;

  funds = signal<FundDTO[]>([]);
  isLoading = signal(true);
  // Il fondo aperto è nell'URL, così tornando indietro da una missione si riapre il suo dettaglio.
  private selectedFundId = signal<string | null>(null);
  selectedFund = computed(() => this.funds().find((fund) => fund.id === this.selectedFundId()) ?? null);
  confirmingDelete = signal(false);
  isDeleting = signal(false);

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((params) => this.selectedFundId.set(params.get('fundId')));
    this.loadFunds();
  }

  loadFunds(): void {
    const myFiscalCode = this.authService.getUser()?.fiscalCode;
    this.isLoading.set(true);
    this.fundService
      .getMyFunds()
      .pipe(finalize(() => this.isLoading.set(false)))
      .subscribe({
        next: (page) => {
          const mine = page.content.filter((fund) => fund.responsibleFc === myFiscalCode);
          this.funds.set(mine);
        },
        error: () => this.toastService.showError('Unable to load your funds.', 'Funds'),
      });
  }

  isInUse(fund: FundDTO): boolean {
    return fund.missions.length > 0;
  }

  isExhausted(fund: FundDTO): boolean {
    return this.available(fund) <= 0;
  }

  available(fund: FundDTO): number {
    return Number(fund.remainingAmount);
  }

  openMission(missionId: string): void {
    this.router.navigate(['/missionreview'], {
      queryParams: { missionId, fundId: this.selectedFundId() },
    });
  }

  openDetail(fund: FundDTO): void {
    this.router.navigate([], { relativeTo: this.route, queryParams: { fundId: fund.id } });
  }

  closeDetail(): void {
    this.confirmingDelete.set(false);
    this.router.navigate([], { relativeTo: this.route, queryParams: {} });
  }

  requestDelete(fund: FundDTO): void {
    if (this.isInUse(fund)) {
      this.confirmingDelete.set(true);
    } else {
      this.deleteFund(fund, false);
    }
  }

  cancelDelete(): void {
    this.confirmingDelete.set(false);
  }

  deleteFund(fund: FundDTO, force: boolean): void {
    this.isDeleting.set(true);
    this.fundService
      .deleteFund(fund.id, force)
      .pipe(finalize(() => this.isDeleting.set(false)))
      .subscribe({
        next: () => {
          this.funds.update((funds) => funds.filter((f) => f.id !== fund.id));
          this.closeDetail();
          this.toastService.showSuccess(`Fund "${fund.name}" deleted.`, 'Fund Deleted');
        },
        error: (err: HttpErrorResponse) => {
          if (err.status === 409) {
            this.loadFunds();
            this.confirmingDelete.set(true);
            return;
          }
          this.confirmingDelete.set(false);
          this.toastService.showError(err.error?.detail ?? 'Unable to delete the fund.', 'Delete Error');
        },
      });
  }
}
