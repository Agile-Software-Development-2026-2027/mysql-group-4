import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { EmploymentLevel } from '../../core/models';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-auth',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './auth.html',
  styleUrl: './auth.scss',
})
export class AuthComponent implements OnInit {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  siteName = 'MYSOL';
  readonly isLoginMode = signal(true);
  readonly isSubmitting = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);

  employmentLevels = [
    { value: EmploymentLevel.RICERCATORE, label: 'Researcher (Ricercatore)' },
    { value: EmploymentLevel.PROFESSORE_ASSOCIATO, label: 'Associate Professor (Prof. Associato)' },
    { value: EmploymentLevel.PROFESSORE_ORDINARIO, label: 'Full Professor (Prof. Ordinario)' },
  ];

  private fiscalCodePattern = /^[A-Za-z]{6}[0-9]{2}[A-Za-z][0-9]{2}[A-Za-z][0-9]{3}[A-Za-z]$/;

  loginForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  registerForm = this.fb.group({
    name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
    surname: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    fiscalCode: ['', [Validators.required, Validators.pattern(this.fiscalCodePattern)]],
    department: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
    employmentLevel: [EmploymentLevel.RICERCATORE, [Validators.required]],
  });

  ngOnInit(): void {
    this.route.url.subscribe((segments) => {
      const path = segments[0]?.path;
      this.isLoginMode.set(path !== 'register');
    });
  }

  switchMode(login: boolean): void {
    this.isLoginMode.set(login);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.router.navigate([login ? '/login' : '/register']);
  }

  onLoginSubmit(): void {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    const { email, password } = this.loginForm.getRawValue();

    this.authService.login({ email: email!, password: password! }).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.router.navigate(['/home']);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        if (err.status === 400) {
          this.errorMessage.set('Invalid email or password. Please try again.');
        } else {
          this.errorMessage.set('An unexpected error occurred. Please try again later.');
        }
      },
    });
  }

  onRegisterSubmit(): void {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set(null);

    const formValue = this.registerForm.getRawValue();
    const payload = {
      name: formValue.name!.trim(),
      surname: formValue.surname!.trim(),
      email: formValue.email!.trim().toLowerCase(),
      password: formValue.password!,
      fiscalCode: formValue.fiscalCode!.trim().toUpperCase(),
      department: formValue.department!.trim(),
      employmentLevel: formValue.employmentLevel!,
    };

    this.authService.register(payload).subscribe({
      next: () => {
        this.authService
          .login({ email: payload.email, password: payload.password })
          .subscribe({
            next: () => {
              this.isSubmitting.set(false);
              this.router.navigate(['/home']);
            },
            error: () => {
              this.isSubmitting.set(false);
              this.isLoginMode.set(true);
              this.successMessage.set('Registration successful! Please sign in with your credentials.');
              this.router.navigate(['/login']);
            },
          });
      },
      error: (err) => {
        this.isSubmitting.set(false);
        if (err.status === 400) {
          const detail = err.error?.detail;
          if (detail === 'REGISTER_USER_ALREADY_EXISTS') {
            this.errorMessage.set('A user with this email already exists.');
          } else if (detail === 'REGISTER_FISCAL_CODE_ALREADY_EXISTS') {
            this.errorMessage.set('A user with this fiscal code already exists.');
          } else if (typeof detail === 'string') {
            this.errorMessage.set(detail);
          } else {
            this.errorMessage.set('Registration failed. Please check the provided information.');
          }
        } else {
          this.errorMessage.set('An error occurred during registration. Please try again later.');
        }
      },
    });
  }

  isFieldInvalid(form: 'login' | 'register', fieldName: string): boolean {
    const control =
      form === 'login' ? this.loginForm.get(fieldName) : this.registerForm.get(fieldName);
    return !!(control && control.invalid && (control.dirty || control.touched));
  }
}
