import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../services/auth.service';
import { ToastService } from '../../services/toast.service';
import { Topbar } from '../../components/topbar/topbar';
import { UserUpdatePayload } from '../../core/models';

@Component({
  selector: 'app-settings',
  imports: [ReactiveFormsModule, Topbar, RouterLink],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
})
export class SettingsComponent implements OnInit {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);

  readonly currentUser = this.authService.currentUser;
  readonly isSaving = signal(false);
  readonly isSubmitted = signal(false);
  readonly isResettingPassword = signal(false);

  settingsForm: FormGroup = this.fb.group({
    name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
    surname: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
    department: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
  });

  hasChanges(): boolean {
    const user = this.authService.getUser();
    if (!user) return false;
    const v = this.settingsForm.value;
    return (
      (v.name?.trim() || '') !== user.name ||
      (v.surname?.trim() || '') !== user.surname ||
      (v.department?.trim() || '') !== user.department
    );
  }

  ngOnInit(): void {
    this.populateForm();
  }

  populateForm(): void {
    const user = this.authService.getUser();
    if (user) {
      this.settingsForm.patchValue({
        name: user.name,
        surname: user.surname,
        department: user.department,
      });
    }
  }

  formatEmploymentLevel(level?: string | null): string {
    if (!level) return 'Not specified';
    const map: Record<string, string> = {
      ricercatore: 'Researcher',
      professore_associato: 'Associate Professor',
      professore_ordinario: 'Full Professor',
    };
    return map[level] || level;
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.settingsForm.get(fieldName);
    return !!(field && field.invalid && (field.touched || this.isSubmitted()));
  }

  onSubmit(): void {
    this.isSubmitted.set(true);
    if (this.settingsForm.invalid || !this.hasChanges()) return;

    const val = this.settingsForm.value;
    const payload: UserUpdatePayload = {
      name: val.name?.trim(),
      surname: val.surname?.trim(),
      department: val.department?.trim(),
    };

    this.isSaving.set(true);
    this.authService.updateProfile(payload).subscribe({
      next: () => {
        this.isSaving.set(false);
        this.isSubmitted.set(false);
        this.populateForm();
        this.toastService.showSuccess('Profile updated successfully!', 'Settings');
      },
      error: () => {
        this.isSaving.set(false);
        this.toastService.showError('Failed to update profile.', 'Error');
      },
    });
  }

  onReset(): void {
    this.populateForm();
    this.isSubmitted.set(false);
  }

  onSendPasswordReset(): void {
    const user = this.currentUser();
    if (!user?.email) return;

    this.isResettingPassword.set(true);
    this.authService.forgotPassword({ email: user.email }).subscribe({
      next: () => {
        this.isResettingPassword.set(false);
        this.toastService.showSuccess(
          `Password reset link sent to ${user.email}`,
          'Password Reset'
        );
      },
      error: () => {
        this.isResettingPassword.set(false);
        this.toastService.showError('Failed to send password reset email.', 'Error');
      },
    });
  }
}
