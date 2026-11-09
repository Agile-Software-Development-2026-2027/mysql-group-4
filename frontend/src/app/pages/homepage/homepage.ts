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
  activeFunds = signal<number | null>(null);
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
        const free = mine.filter((fund) => !fund.lockedByMissionId);
        this.totalFunds.set(mine.length);
        this.activeFunds.set(free.length);
        this.availableAmount.set(free.reduce((sum, fund) => sum + Number(fund.amount), 0));
      },
      error: () => this.activeFunds.set(0),
    });
  }

  isInProgress(mission: MissionDTO): boolean {
    return mission.startsAt <= toNaiveIso(new Date());
  }
}
