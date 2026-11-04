import { Component, computed, inject, signal, OnDestroy } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { forkJoin, Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged, switchMap } from 'rxjs/operators';
import * as L from 'leaflet';

import { Topbar } from '../../components/topbar/topbar';
import { ToastService } from '../../services/toast.service';
import { MissionService } from '../../services/mission.service';
import { LocationService, LocationResponse } from '../../services/location.service';
import { AuthService } from '../../services/auth.service';
import { FundService } from '../../services/fund.service';
import { FundDTO, MissionCreatePayload, MissionStatus, MissionType } from '../../core/models';

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
export class NewMissionComponent implements OnDestroy {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private toastService = inject(ToastService);
  private missionService = inject(MissionService);
  private locationService = inject(LocationService);
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

  myFunds = signal<FundDTO[]>([]);
  hasFreeFunds = computed(() => this.myFunds().some((fund) => this.isFundFree(fund)));
  ownFundQuery = signal('');
  showOwnFundSuggestions = signal(false);
  activeOwnFund = signal(-1);
  filteredOwnFunds = computed(() => {
    const query = this.ownFundQuery().trim().toLowerCase();
    return this.myFunds().filter((fund) => fund.name.toLowerCase().includes(query));
  });

  showMapPanel = signal(false);
  locationSuggestions = signal<LocationResponse[]>([]);
  isSearchingLocation = signal(false);
  private searchSubject = new Subject<string>();
  private searchSub?: Subscription;
  private map?: L.Map;
  private marker?: L.Marker;
  private lastSelectedLocation?: { lat: number; lon: number; label: string };

  // Allegati PDF
  selectedFiles: File[] = [];

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
      fundId: [''],
      documentFile: [null, [Validators.required]],
    },
    { validators: [this.datePeriodValidator.bind(this)] }
  );

  constructor() {
    this.setFundSource('self');

    this.searchSub = this.searchSubject
      .pipe(
        debounceTime(350),
        distinctUntilChanged(),
        switchMap((query: string) => {
          if (!query || query.trim().length < 3) {
            this.isSearchingLocation.set(false);
            return [];
          }
          this.isSearchingLocation.set(true);
          return this.locationService.autocomplete(query);
        })
      )
      .subscribe((results: LocationResponse[]) => {
        this.locationSuggestions.set(results);
        this.isSearchingLocation.set(false);
      });
  }

  ngOnDestroy(): void {
    this.searchSub?.unsubscribe();
    this.destroyMap();
  }

  get selectedFile(): File | null {
    return this.missionForm.get('documentFile')?.value || null;
  }

  // --- Logica Gestione Fondi & Manager ---
  setFundSource(source: 'self' | 'other'): void {
    this.fundSource.set(source);
    const managerControl = this.missionForm.get('fundManagerId');
    const fundControl = this.missionForm.get('fundId');
    if (source === 'self') {
      managerControl?.setValue('');
      managerControl?.clearValidators();
      this.managerQuery.set('');
      this.showManagerSuggestions.set(false);
      fundControl?.setValidators(Validators.required);
      this.loadMyFunds();
    } else {
      managerControl?.setValidators(Validators.required);
      fundControl?.setValue('');
      fundControl?.clearValidators();
      this.ownFundQuery.set('');
      this.showOwnFundSuggestions.set(false);
      this.loadManagerOptions();
    }
    managerControl?.updateValueAndValidity();
    fundControl?.updateValueAndValidity();
  }

  isFundFree(fund: FundDTO): boolean {
    return !fund.lockedByMissionId;
  }

  selectedOwnFund(): FundDTO | undefined {
    const fundId = this.missionForm.get('fundId')?.value;
    return this.myFunds().find((fund) => fund.id === fundId);
  }

  onOwnFundQueryInput(value: string): void {
    this.ownFundQuery.set(value);
    // Se l'utente riscrive, la scelta precedente non vale più.
    this.missionForm.get('fundId')?.setValue('');
    this.activeOwnFund.set(-1);
    this.showOwnFundSuggestions.set(true);
  }

  selectOwnFund(fund: FundDTO): void {
    if (!this.isFundFree(fund)) {
      return;
    }
    this.missionForm.get('fundId')?.setValue(fund.id);
    this.ownFundQuery.set(fund.name);
    this.showOwnFundSuggestions.set(false);
  }

  onOwnFundKeydown(event: KeyboardEvent): void {
    const funds = this.filteredOwnFunds();
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      this.showOwnFundSuggestions.set(true);
      // Le frecce saltano i fondi già assegnati.
      const step = event.key === 'ArrowDown' ? 1 : -1;
      let index = this.activeOwnFund();
      for (let i = 0; i < funds.length; i++) {
        index = (index + step + funds.length) % funds.length;
        if (this.isFundFree(funds[index])) {
          this.activeOwnFund.set(index);
          return;
        }
      }
    } else if (event.key === 'Enter' && this.showOwnFundSuggestions()) {
      event.preventDefault();
      const fund = funds[this.activeOwnFund()] ?? funds.find((f) => this.isFundFree(f));
      if (fund) {
        this.selectOwnFund(fund);
      }
    } else if (event.key === 'Escape') {
      this.showOwnFundSuggestions.set(false);
    }
  }

  closeOwnFundSuggestions(): void {
    this.showOwnFundSuggestions.set(false);
    this.missionForm.get('fundId')?.markAsTouched();
  }

  private loadMyFunds(): void {
    this.fundService.getMyFunds().subscribe({
      next: (page) => {
        const myFiscalCode = this.authService.getUser()?.fiscalCode;
        this.myFunds.set(page.content.filter((fund) => fund.responsibleFc === myFiscalCode));
      },
      error: () => this.toastService.showError('Unable to load your funds.', 'Funds'),
    });
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

  // --- Logica Mappa Leaflet & Autocomplete ---
  onDestinationInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.searchSubject.next(value);
  }

  selectLocation(location: LocationResponse): void {
    this.missionForm.patchValue({ destination: location.display_name });
    this.locationSuggestions.set([]);

    const lat = parseFloat(location.lat);
    const lon = parseFloat(location.lon);
    this.lastSelectedLocation = { lat, lon, label: location.display_name };

    this.openMapPanel();
  }

  openMapPanel(): void {
    this.showMapPanel.set(true);
    setTimeout(() => this.initMapIfNeeded(), 100);
  }

  closeMapPanel(): void {
    this.showMapPanel.set(false);
    this.destroyMap();
  }

  private destroyMap(): void {
    if (this.map) {
      this.map.remove();
      this.map = undefined;
      this.marker = undefined;
    }
  }

  private initMapIfNeeded(): void {
    const mapElement = document.getElementById('map-container');
    if (!mapElement) return;

    this.destroyMap();

    const defaultIcon = L.icon({
      iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      iconSize: [25, 41],
      iconAnchor: [12, 41],
      popupAnchor: [1, -34],
    });
    L.Marker.prototype.options.icon = defaultIcon;

    this.map = L.map('map-container').setView([39.3621, 16.2255], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors',
    }).addTo(this.map);

    if (this.lastSelectedLocation) {
      this.updateMapLocation(
        this.lastSelectedLocation.lat,
        this.lastSelectedLocation.lon,
        this.lastSelectedLocation.label
      );
    }
  }

  private updateMapLocation(lat: number, lon: number, label: string): void {
    if (!this.map) return;

    this.map.setView([lat, lon], 15);

    if (this.marker) {
      this.marker.setLatLng([lat, lon]);
    } else {
      this.marker = L.marker([lat, lon]).addTo(this.map);
    }
    this.marker.bindPopup(`<b>${label}</b>`).openPopup();
  }

  // --- Logica Allegati Multipli ---
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const files = Array.from(input.files);
      const validPdfs = files.filter(f => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));

      if (validPdfs.length !== files.length) {
        this.toastService.showError('Only PDFs accepted.', 'Invalid File');
      }
      this.selectedFiles = [...this.selectedFiles, ...validPdfs];
      this.missionForm.patchValue({ documentFile: this.selectedFiles.length > 0 ? this.selectedFiles : null });
      this.missionForm.get('documentFile')?.markAsTouched();
      input.value = '';
    }
  }

  removeFile(index: number): void {
    this.selectedFiles.splice(index, 1);
    this.missionForm.patchValue({ documentFile: this.selectedFiles.length > 0 ? this.selectedFiles : null });
  }

  // --- Validazioni & Form Helpers ---
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
    let fundId: string | undefined;
    if (this.fundSource() === 'self') {
      const fund = this.selectedOwnFund();
      if (!fund) {
        this.toastService.showError('Select one of your funds for this mission.', 'Missing Fund');
        return;
      }
      fundManagerId = currentUser.id;
      fundId = fund.id;
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
      fundId,
    };

    this.isSubmitting.set(true);

    this.missionService.createMission(payload).subscribe({
      next: (createdMission) => {
        if (this.selectedFiles && this.selectedFiles.length > 0 && createdMission?.id) {
          const uploadRequests = this.selectedFiles.map((file) =>
            this.missionService.uploadDocument(createdMission.id, file)
          );

          forkJoin(uploadRequests).subscribe({
            next: () => {
              this.handleSubmissionSuccess(createdMission);
            },
            error: (err: any) => {
              this.isSubmitting.set(false);
              this.toastService.showError(
                'Mission created, but document upload failed. Please try re-uploading from mission details.',
                'Upload Error'
              );
              console.error('[NewMission] MinIO upload error:', err);
            },
          });
        } else {
          this.handleSubmissionSuccess(createdMission);
        }
      },
      error: (err: any) => {
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

        // Il fondo scelto è stato appena assegnato ad altro: aggiorno l'elenco e annullo la scelta.
        if (err?.status === 409 && this.fundSource() === 'self') {
          this.showSummaryModal.set(false);
          this.missionForm.get('fundId')?.setValue('');
          this.ownFundQuery.set('');
          this.loadMyFunds();
        }
      },
    });
  }

  private handleSubmissionSuccess(mission: any): void {
    this.isSubmitting.set(false);
    this.showSummaryModal.set(false);
    if (mission.status === MissionStatus.ACCEPTED) {
      this.toastService.showSuccess(
        'You manage the fund yourself, so the mission was approved automatically.',
        'Mission Approved'
      );
    } else {
      this.toastService.showSuccess(
        'Mission request created successfully!',
        'Mission Submitted'
      );
    }
    this.resetForm();
    this.closeMapPanel();
    this.router.navigate(['/home']);
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
      fundId: '',
      documentFile: null,
    });
    this.selectedFiles = [];
    this.locationSuggestions.set([]);
    this.lastSelectedLocation = undefined;
    this.isSubmitted.set(false);
    this.setFundSource('self');
  }
}