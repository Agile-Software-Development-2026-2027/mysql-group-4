import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Topbar } from '../../components/topbar/topbar';

import { ToastService } from '../../services/toast.service';
import { MissionService } from '../../services/mission.service';
import { AuthService } from '../../services/auth.service';
import { FundService } from '../../services/fund.service';
import { MissionCreatePayload, MissionType } from '../../core/models';

interface ManagerOption {
  id: string;
  name: string;
  department: string;
}

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
  private fundService = inject(FundService);

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

  managerOptions = signal<ManagerOption[]>([]);
  isLoadingManagers = signal(false);

  managerQuery = signal('');
  showManagerSuggestions = signal(false);
  activeSuggestion = signal(0);
  filteredManagers = computed(() => {
    const query = this.managerQuery().trim().toLowerCase();
    return this.managerOptions().filter((option) =>
      `${option.name} ${option.department}`.toLowerCase().includes(query)
    );
  });

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
      fundManagerId: [''],
    },
    { validators: [this.datePeriodValidator.bind(this)] }
  );

  setFundSource(source: 'self' | 'other'): void {
    this.fundSource.set(source);
    const managerControl = this.missionForm.get('fundManagerId');
    if (source === 'self') {
      managerControl?.setValue('');
      managerControl?.clearValidators();
      this.managerQuery.set('');
      this.showManagerSuggestions.set(false);
    } else {
      managerControl?.setValidators(Validators.required);
      this.loadManagerOptions();
    }
    managerControl?.updateValueAndValidity();
  }

  selectedManager(): ManagerOption | undefined {
    const managerId = this.missionForm.get('fundManagerId')?.value;
    return this.managerOptions().find((option) => option.id === managerId);
  }

  managerLabel(option: ManagerOption): string {
    return `${option.name} — ${option.department}`;
  }

  onManagerQueryInput(value: string): void {
    this.managerQuery.set(value);
    // Se l'utente riscrive, la scelta precedente non vale più.
    this.missionForm.get('fundManagerId')?.setValue('');
    this.activeSuggestion.set(0);
    this.showManagerSuggestions.set(true);
  }

  selectManager(option: ManagerOption): void {
    this.missionForm.get('fundManagerId')?.setValue(option.id);
    this.managerQuery.set(this.managerLabel(option));
    this.showManagerSuggestions.set(false);
  }

  onManagerKeydown(event: KeyboardEvent): void {
    const options = this.filteredManagers();
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      this.showManagerSuggestions.set(true);
      const step = event.key === 'ArrowDown' ? 1 : -1;
      this.activeSuggestion.update((i) => (i + step + options.length) % Math.max(options.length, 1));
    } else if (event.key === 'Enter' && this.showManagerSuggestions() && options.length > 0) {
      event.preventDefault();
      this.selectManager(options[this.activeSuggestion()] ?? options[0]);
    } else if (event.key === 'Escape') {
      this.showManagerSuggestions.set(false);
    }
  }

  closeManagerSuggestions(): void {
    this.showManagerSuggestions.set(false);
    this.missionForm.get('fundManagerId')?.markAsTouched();
  }

  // Responsabili che hanno almeno un fondo ancora libero: il fondo lo sceglie lui in approvazione.
  private loadManagerOptions(): void {
    this.isLoadingManagers.set(true);
    this.fundService.getFundManagers().subscribe({
      next: (managers) => {
        const myId = this.authService.getUser()?.id;
        this.managerOptions.set(
          managers
            .filter((manager) => manager.id !== myId)
            .map((manager) => ({
              id: manager.id,
              name: `${manager.name} ${manager.surname}`,
              department: manager.department,
            }))
        );
        this.isLoadingManagers.set(false);
      },
      error: () => {
        this.isLoadingManagers.set(false);
        this.toastService.showError('Unable to load the fund managers.', 'Fund Managers');
      },
    });
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

    // Distinzione gestore fondi: 'self' (utente corrente) vs 'other' (responsabile scelto)
    let fundManagerId: string;
    if (this.fundSource() === 'self') {
      fundManagerId = currentUser.id;
    } else {
      const manager = this.selectedManager();
      if (!manager) {
        this.toastService.showError('Select the fund manager for this mission.', 'Missing Manager');
        return;
      }
      fundManagerId = manager.id;
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
      fundManagerId: '',
    });
    this.isSubmitted.set(false);
    this.setFundSource('self');
  }
}
