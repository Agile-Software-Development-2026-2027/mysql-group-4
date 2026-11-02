import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MissionService } from '../../services/mission';
import { MissionDTO } from '../../core/models/mission-dto';

@Component({
  selector: 'app-mission-review',
  standalone: true,
  imports: [CommonModule],
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

  constructor(
    private missionService: MissionService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.loadAllMissions();
  }

  loadAllMissions() {
    this.missionService.getPendingMissions().subscribe(page => {
      this.pendingMissions = page.content || [];
      this.cdr.detectChanges();
    });
    this.missionService.getAcceptedMissions().subscribe(page => {
      this.approvedMissions = page.content || [];
      this.cdr.detectChanges();
    });
    this.missionService.getRejectedMissions().subscribe(page => {
      this.rejectedMissions = page.content || [];
      this.cdr.detectChanges();
    });
  }

  toggleSection(section: string) {
    this.activeSection = this.activeSection === section ? '' : section;
  }

  openDetail(mission: MissionDTO) {
    this.selectedMission = mission;
    this.isDetailView = true;
  }

  closeDetail() {
    this.isDetailView = false;
    this.selectedMission = null;
  }

  accept(id: string, note: string) {
    this.missionService.acceptMission(id, note).subscribe({
      next: () => {
        this.loadAllMissions();
        this.closeDetail();
      },
      error: (err) => console.error('Errore durante approvazione:', err)
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
