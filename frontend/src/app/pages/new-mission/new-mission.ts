import { Component, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

export enum MissionType {
  RESEARCH = 'RESEARCH',
  TRAINING = 'TRAINING',
  TEACHING = 'TEACHING',
}

@Component({
  selector: 'app-new-mission',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './new-mission.html',
  styleUrl: './new-mission.scss',
})
export class NewMissionComponent {
  private fb = inject(FormBuilder);
  private router = inject(Router);

  siteName = 'MYSOL';
  isSubmitted = signal(false);
  successMessage = signal<string | null>(null);

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
    { validators: [this.datePeriodValidator] }
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
    const startTimeVal = control.get('startTime')?.value || '00:00';
    const endTimeVal = control.get('endTime')?.value || '23:59';

    if (!startDateVal || !endDateVal) {
      return null;
    }

    const start = new Date(`${startDateVal}T${startTimeVal}`);
    const end = new Date(`${endDateVal}T${endTimeVal}`);

    if (end <= start) {
      return { invalidPeriod: 'End date and time must be after the start date and time.' };
    }
    return null;
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.missionForm.get(fieldName);
    return !!(field && field.invalid && (field.touched || this.isSubmitted()));
  }

  onSubmit(): void {
    this.isSubmitted.set(true);

    if (this.missionForm.invalid) {
      this.missionForm.markAllAsTouched();
      return;
    }

    const formValues = this.missionForm.value;

    const startsAtIso = `${formValues.startDate}T${formValues.startTime || '08:00'}:00`;
    const endsAtIso = `${formValues.endDate}T${formValues.endTime || '20:00'}:00`;

    const mockMissionPayload = {
      missionType: formValues.missionType,
      subject: formValues.subject,
      destination: formValues.destination,
      estimatedCost: formValues.estimatedCost,
      startsAt: startsAtIso,
      endsAt: endsAtIso,
      fundManagerId:
        this.fundSource() === 'self'
          ? '00000000-0000-0000-0000-000000000001'
          : '00000000-0000-0000-0000-000000000002',
      fundSourceMode: this.fundSource(),
    };

    console.log('[NewMission] Form submitted successfully (Mock Frontend Mode):', mockMissionPayload);

    this.successMessage.set(
      'Mission request created successfully! (Frontend simulated submission)'
    );

    window.scrollTo({ top: 0, behavior: 'smooth' });
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
    this.successMessage.set(null);
    this.fundSource.set('self');
  }
}
