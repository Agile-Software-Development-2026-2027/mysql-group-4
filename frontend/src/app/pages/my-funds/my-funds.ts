import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { Topbar } from '../../components/topbar/topbar';
import { FundDTO } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { FundService } from '../../services/fund.service';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-my-funds',
  standalone: true,
  imports: [DecimalPipe, RouterLink, Topbar],
  templateUrl: './my-funds.html',
  styleUrl: './my-funds.scss',
})
export class MyFunds implements OnInit {
  private fundService = inject(FundService);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);

  readonly currentUser = this.authService.currentUser;

  funds = signal<FundDTO[]>([]);
  isLoading = signal(true);
  selectedFund = signal<FundDTO | null>(null);
  confirmingDelete = signal(false);
  isDeleting = signal(false);

  ngOnInit(): void {
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
          const selected = this.selectedFund();
          if (selected) {
            this.selectedFund.set(mine.find((fund) => fund.id === selected.id) ?? null);
          }
        },
        error: () => this.toastService.showError('Unable to load your funds.', 'Funds'),
      });
  }

  isLocked(fund: FundDTO): boolean {
    return !!fund.lockedByMissionId;
  }

  available(fund: FundDTO): number {
    return Math.max(0, Number(fund.amount) - Number(fund.requestedAmount ?? 0));
  }

  openDetail(fund: FundDTO): void {
    this.selectedFund.set(fund);
  }

  closeDetail(): void {
    this.selectedFund.set(null);
    this.confirmingDelete.set(false);
  }

  requestDelete(fund: FundDTO): void {
    if (this.isLocked(fund)) {
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
