import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';
import { MissionDTO, MissionStatus } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { MissionService } from '../../services/mission.service';

function toNaiveIso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

@Component({
  selector: 'app-homepage',
  imports: [DatePipe, NgTemplateOutlet, RouterLink, Topbar],
  templateUrl: './homepage.html',
  styleUrl: './homepage.scss',
})
export class Homepage implements OnInit {
  private missionService = inject(MissionService);
  private authService = inject(AuthService);

  siteName = 'MYSOL';
  readonly user = this.authService.currentUser;

  missionsLoading = signal(true);
  currentMission = signal<MissionDTO | null>(null);
  nextMission = signal<MissionDTO | null>(null);

  ngOnInit(): void {
    const now = toNaiveIso(new Date());

    this.missionService
      .getMySentMissions({ status: MissionStatus.ACCEPTED, endsAtFrom: now })
      .subscribe({
        next: (page) => {
          const sorted = [...page.content].sort((a, b) => a.startsAt.localeCompare(b.startsAt));
          this.currentMission.set(sorted.find((m) => m.startsAt <= now) ?? null);
          this.nextMission.set(sorted.find((m) => m.startsAt > now) ?? null);
          this.missionsLoading.set(false);
        },
        error: () => {
          this.currentMission.set(null);
          this.nextMission.set(null);
          this.missionsLoading.set(false);
        },
      });
  }
}
