import { Component, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';

import { ToastService } from '../../core/services/toast.service';
import { MissionService } from '../../services/mission.service';
import { AuthService } from '../../services/auth.service';
import { MissionCreatePayload, MissionType } from '../../core/models';

@Component({
  selector: 'app-new-mission',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, Topbar],
  templateUrl: './new-mission.html',
  styleUrl: './new-mission.scss',
})
export class NewMissionComponent {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private toastService = inject(ToastService);
  private missionService = inject(MissionService);
  private authService = inject(AuthService);

  siteName = 'MYSOL';
  isSubmitted = signal(false);
  isSubmitting = signal(false);
  showSummaryModal = signal(false);

  currentUser = this.authService.currentUser;

  missionTypes = [
    { value: MissionType.RESEARCH, label: 'Research (Ricerca)' },
    { value: MissionType.TRAINING, label: 'Training (Formazione)' },
    { value: MissionType.TEACHING, label: 'Teaching (Didattica)' },
  ];

  fundSource = signal<'self' | 'other'>('self');

  showMapPanel = signal(false);

  missionForm: FormGroup = this.fb.group(
    {
      subject: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(250)]],
      missionType: [MissionType.RESEARCH, [Validators.required]],
      destination: ['', [Validators.required, Validators.minLength(2)]],
      startDate: ['', [Validators.required]],
      startTime: [''],
      endDate: ['', [Validators.required]],
      endTime: [''],
      estimatedCost: [null, [Validators.required, Validators.min(0)]],
      fundManagerInput: [''],
    },
    { validators: [this.datePeriodValidator.bind(this)] }
  );

  setFundSource(source: 'self' | 'other'): void {
    this.fundSource.set(source);
    if (source === 'self') {
      this.missionForm.get('fundManagerInput')?.setValue('');
    }
  }

  openMapPanel(): void {
    this.showMapPanel.set(true);
  }

  closeMapPanel(): void {
    this.showMapPanel.set(false);
  }

  datePeriodValidator(control: AbstractControl): ValidationErrors | null {
    const startDateVal = control.get('startDate')?.value;
    const endDateVal = control.get('endDate')?.value;
    const startTimeVal = control.get('startTime')?.value || '08:00';
    const endTimeVal = control.get('endTime')?.value || '20:00';

    if (!startDateVal || !endDateVal) {
      return null;
    }

    const start = new Date(`${startDateVal}T${this.normalizeTime(startTimeVal)}`);
    const end = new Date(`${endDateVal}T${this.normalizeTime(endTimeVal)}`);

    if (end <= start) {
      return { invalidPeriod: 'End date and time must be after the start date and time.' };
    }
    return null;
  }

  private normalizeTime(timeVal?: string): string {
    if (!timeVal) return '00:00:00';
    const parts = timeVal.split(':');
    const hh = parts[0].padStart(2, '0');
    const mm = (parts[1] || '00').padStart(2, '0');
    const ss = (parts[2] || '00').padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.missionForm.get(fieldName);
    return !!(field && field.invalid && (field.touched || this.isSubmitted()));
  }

  formatEmploymentLevel(level?: string | null): string {
    if (!level) return 'Not specified';
    const map: Record<string, string> = {
      ricercatore: 'Researcher (Ricercatore)',
      professore_associato: 'Associate Professor (Professore Associato)',
      professore_ordinario: 'Full Professor (Professore Ordinario)',
    };
    return map[level] || level;
  }

  getMissionTypeLabel(): string {
    const val = this.missionForm.get('missionType')?.value;
    const found = this.missionTypes.find((t) => t.value === val);
    return found ? found.label : val;
  }

  onSubmit(): void {
    this.isSubmitted.set(true);

    if (this.missionForm.invalid) {
      this.missionForm.markAllAsTouched();
      return;
    }

    const user = this.authService.getUser();
    if (!user) {
      this.toastService.showError(
        'You must be logged in to create a mission.',
        'Authentication Required'
      );
      return;
    }

    // Apre il riepilogo in rilievo prima dell'invio definitivo
    this.showSummaryModal.set(true);
  }

  closeSummary(): void {
    this.showSummaryModal.set(false);
  }

  confirmSubmit(): void {
    const currentUser = this.authService.getUser();
    if (!currentUser) {
      this.toastService.showError(
        'You must be logged in to create a mission.',
        'Authentication Required'
      );
      return;
    }

    const formValues = this.missionForm.value;

    const startTime = formValues.startTime || '08:00';
    const endTime = formValues.endTime || '20:00';
    const startsAt = `${formValues.startDate}T${this.normalizeTime(startTime)}`;
    const endsAt = `${formValues.endDate}T${this.normalizeTime(endTime)}`;

    // Distinzione gestore fondi: 'self' (utente corrente) vs 'other' (placeholder)
    let fundManagerId: string;
    if (this.fundSource() === 'self') {
      fundManagerId = currentUser.id;
    } else {
      const inputVal = formValues.fundManagerInput?.trim();
      fundManagerId = inputVal || '00000000-0000-0000-0000-000000000002';
    }

    const payload: MissionCreatePayload = {
      missionType: formValues.missionType,
      subject: formValues.subject.trim(),
      destination: formValues.destination.trim(),
      estimatedCost: Math.round(Number(formValues.estimatedCost) * 100) / 100,
      startsAt,
      endsAt,
      fundManagerId,
    };

    this.isSubmitting.set(true);

    this.missionService.createMission(payload).subscribe({
      next: (_mission) => {
        this.isSubmitting.set(false);
        this.showSummaryModal.set(false);
        this.toastService.showSuccess(
          'Mission request created successfully!',
          'Mission Submitted'
        );
        this.resetForm();
        this.closeMapPanel();
        this.router.navigate(['/home']);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        let errorDetail = 'Failed to create mission. Please try again.';
        if (err?.status === 0) {
          errorDetail = 'Cannot reach backend server. Please check your connection.';
        } else if (typeof err?.error?.detail === 'string') {
          errorDetail = err.error.detail;
        } else if (Array.isArray(err?.error?.detail) && err.error.detail.length > 0) {
          errorDetail = err.error.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
        } else if (err?.error?.message) {
          errorDetail = err.error.message;
        }

        this.toastService.showError(errorDetail, 'Submission Error');
        console.error('[NewMission] Backend submission error:', err);
      },
    });
  }

  resetForm(): void {
    this.missionForm.reset({
      subject: '',
      missionType: MissionType.RESEARCH,
      destination: '',
      startDate: '',
      startTime: '',
      endDate: '',
      endTime: '',
      estimatedCost: null,
      fundManagerInput: '',
    });
    this.isSubmitted.set(false);
    this.fundSource.set('self');
  }
}
