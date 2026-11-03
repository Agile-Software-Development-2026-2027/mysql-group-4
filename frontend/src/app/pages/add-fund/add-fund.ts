import { Component, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { Topbar } from '../../components/topbar/topbar';
import { AuthService } from '../../services/auth.service';
import { FundService } from '../../services/fund.service';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-add-fund',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, Topbar],
  templateUrl: './add-fund.html',
  styleUrl: './add-fund.scss',
})
export class AddFund {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private fundService = inject(FundService);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);

  readonly currentUser = this.authService.currentUser;

  isSubmitted = signal(false);
  isSaving = signal(false);

  fundForm: FormGroup = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(100)]],
    description: ['', [Validators.maxLength(500)]],
    amount: [null, [Validators.required, Validators.min(0), Validators.pattern(/^\d+(\.\d{1,2})?$/)]],
  });

  isFieldInvalid(fieldName: string): boolean {
    const field = this.fundForm.get(fieldName);
    return !!(field && field.invalid && (field.touched || this.isSubmitted()));
  }

  onSubmit(): void {
    this.isSubmitted.set(true);

    if (this.fundForm.invalid) {
      this.fundForm.markAllAsTouched();
      return;
    }

    const { name, description, amount } = this.fundForm.value;
    this.isSaving.set(true);

    // Il responsabile non viene inviato: il backend lo ricava dall'utente autenticato.
    this.fundService
      .createFund({
        name: name.trim(),
        description: description?.trim() || null,
        amount: Number(amount),
      })
      .pipe(finalize(() => this.isSaving.set(false)))
      .subscribe({
        next: (fund) => {
          this.toastService.showSuccess(
            `Fund "${fund.name}" created with a budget of € ${fund.amount}.`,
            'Fund Created'
          );
          this.resetForm();
          this.router.navigate(['/home']);
        },
        error: (err: HttpErrorResponse) => {
          this.toastService.showError(this.errorMessage(err), 'Submission Error');
        },
      });
  }

  resetForm(): void {
    this.fundForm.reset({ name: '', description: '', amount: null });
    this.isSubmitted.set(false);
  }

  private errorMessage(err: HttpErrorResponse): string {
    if (err.status === 0) {
      return 'Cannot reach backend server. Please check your connection.';
    }
    if (typeof err.error?.detail === 'string') {
      return err.error.detail;
    }
    if (Array.isArray(err.error?.detail) && err.error.detail.length > 0) {
      return err.error.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
    }
    return err.error?.message ?? 'Unable to create the fund. Please try again.';
  }
}
