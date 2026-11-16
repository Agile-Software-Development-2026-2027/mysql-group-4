import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';
import { MissionDTO, MissionStatus } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { FundService } from '../../services/fund.service';
import { MissionService } from '../../services/mission.service';

function toNaiveIso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

@Component({
  selector: 'app-homepage',
  imports: [DatePipe, DecimalPipe, RouterLink, Topbar],
  templateUrl: './homepage.html',
  styleUrl: './homepage.scss',
})
export class Homepage implements OnInit {
  private missionService = inject(MissionService);
  private fundService = inject(FundService);
  private authService = inject(AuthService);

  siteName = 'MYSOL';

  nextMission = signal<MissionDTO | null | undefined>(undefined);
  availableFunds = signal<number | null>(null);
  activeFunds = signal(0);
  totalFunds = signal(0);
  availableAmount = signal(0);
  completedMissions = signal<number | null>(null);

  ngOnInit(): void {
    const now = toNaiveIso(new Date());

    this.missionService
      .getMySentMissions({ status: MissionStatus.ACCEPTED, endsAtFrom: now })
      .subscribe({
        next: (page) => {
          const sorted = [...page.content].sort((a, b) => a.startsAt.localeCompare(b.startsAt));
          this.nextMission.set(sorted[0] ?? null);
        },
        error: () => this.nextMission.set(null),
      });

    this.missionService
      .getMySentMissions({ status: MissionStatus.COMPLETED, endsAtTo: now }, 1)
      .subscribe({
        next: (page) => this.completedMissions.set(page.totalElements),
        error: () => this.completedMissions.set(0),
      });

    this.fundService.getMyFunds().subscribe({
      next: (page) => {
        const myFiscalCode = this.authService.getUser()?.fiscalCode;
        const mine = page.content.filter((fund) => fund.responsibleFc === myFiscalCode);
        const usable = mine.filter((fund) => Number(fund.remainingAmount) > 0);
        this.totalFunds.set(mine.length);
        this.availableFunds.set(usable.length);
        this.activeFunds.set(mine.filter((fund) => fund.missions.length > 0).length);
        this.availableAmount.set(usable.reduce((sum, fund) => sum + Number(fund.remainingAmount), 0));
      },
      error: () => this.availableFunds.set(0),
    });
  }

  isInProgress(mission: MissionDTO): boolean {
    return mission.startsAt <= toNaiveIso(new Date());
  }
}
