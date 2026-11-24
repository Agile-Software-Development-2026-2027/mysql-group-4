import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { EmploymentLevel } from '../../core/models';
import { AuthService } from '../../services/auth.service';
import { ToastService } from '../../services/toast.service';

export type AuthMode = 'login' | 'register' | 'forgot-password' | 'reset-password';

@Component({
  selector: 'app-auth',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './auth.html',
  styleUrl: './auth.scss',
})
export class AuthComponent implements OnInit {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private toastService = inject(ToastService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  siteName = 'MYSOL';
  readonly authMode = signal<AuthMode>('login');
  readonly isLoginMode = computed(() => this.authMode() === 'login');
  readonly isSubmitting = signal(false);
  readonly resetToken = signal<string | null>(null);
  readonly tokenError = signal<string | null>(null);
  readonly showPassword = signal(false);
  readonly showConfirmPassword = signal(false);

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

  private passwordMatchValidator = (group: AbstractControl): ValidationErrors | null => {
    const password = group.get('password')?.value;
    const confirmPassword = group.get('confirmPassword')?.value;
    return password === confirmPassword ? null : { passwordMismatch: true };
  };

  registerForm = this.fb.group(
    {
      name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
      surname: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', [Validators.required]],
      fiscalCode: ['', [Validators.required, Validators.pattern(this.fiscalCodePattern)]],
      department: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(50)]],
      employmentLevel: [EmploymentLevel.RICERCATORE, [Validators.required]],
    },
    { validators: this.passwordMatchValidator }
  );

  forgotPasswordForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
  });

  resetPasswordForm = this.fb.group(
    {
      password: ['', [Validators.required, Validators.minLength(8)]],
      confirmPassword: ['', [Validators.required]],
    },
    { validators: this.passwordMatchValidator }
  );

  isRegisterConfirmMismatch(): boolean {
    const ctrl = this.registerForm.get('confirmPassword');
    return !!(this.registerForm.hasError('passwordMismatch') && ctrl && (ctrl.dirty || ctrl.touched));
  }

  isRegisterPasswordsMatched(): boolean {
    const pwd = this.registerForm.get('password');
    const confirm = this.registerForm.get('confirmPassword');
    return !!(pwd?.valid && confirm?.value && !this.registerForm.hasError('passwordMismatch'));
  }

  ngOnInit(): void {
    this.route.url.subscribe((segments) => {
      const path = segments[0]?.path;
      if (path === 'register') {
        this.authMode.set('register');
      } else if (path === 'forgot-password') {
        this.authMode.set('forgot-password');
      } else if (path === 'reset-password') {
        this.authMode.set('reset-password');
      } else {
        this.authMode.set('login');
      }
      this.showPassword.set(false);
      this.showConfirmPassword.set(false);
    });

    this.route.queryParamMap.subscribe((params) => {
      const token = params.get('token');
      this.resetToken.set(token);
      if (this.authMode() === 'reset-password' && !token) {
        this.tokenError.set('No reset token provided. Please request a new password reset link.');
      } else {
        this.tokenError.set(null);
      }
    });
  }

  switchMode(mode: AuthMode | boolean): void {
    const targetMode: AuthMode = typeof mode === 'boolean' ? (mode ? 'login' : 'register') : mode;
    this.authMode.set(targetMode);
    this.showPassword.set(false);
    this.showConfirmPassword.set(false);
    this.router.navigate([`/${targetMode}`]);
  }

  onLoginSubmit(): void {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
    const { email, password } = this.loginForm.getRawValue();

    this.authService.login({ email: email!, password: password! }).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.toastService.showSuccess('Signed in successfully.', 'Welcome back');
        this.router.navigateByUrl(this.authService.landingUrl());
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const msg =
          err.status === 400
            ? 'Invalid email or password. Please try again.'
            : 'An unexpected error occurred. Please try again later.';
        this.toastService.showError(msg, 'Sign In Failed');
      },
    });
  }

  onRegisterSubmit(): void {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
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
              this.toastService.showSuccess('Account created successfully. Welcome to MySOL!', 'Account Created');
              this.router.navigateByUrl(this.authService.landingUrl());
            },
            error: () => {
              this.isSubmitting.set(false);
              this.toastService.showSuccess('Registration successful! Please sign in with your credentials.', 'Account Created');
              this.router.navigate(['/login']);
            },
          });
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const detail = err.error?.detail;
        let msg = 'An error occurred during registration. Please try again later.';
        if (err.status === 400) {
          if (detail === 'REGISTER_USER_ALREADY_EXISTS') msg = 'A user with this email already exists.';
          else if (detail === 'REGISTER_FISCAL_CODE_ALREADY_EXISTS') msg = 'A user with this fiscal code already exists.';
          else if (typeof detail === 'string') msg = detail;
          else msg = 'Registration failed. Please check the provided information.';
        }
        this.toastService.showError(msg, 'Registration Failed');
      },
    });
  }

  onForgotPasswordSubmit(): void {
    if (this.forgotPasswordForm.invalid) {
      this.forgotPasswordForm.markAllAsTouched();
      return;
    }

    const email = this.forgotPasswordForm.get('email')?.value?.trim().toLowerCase();
    if (!email) return;
    this.isSubmitting.set(true);

    this.authService.forgotPassword({ email }).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.toastService.showSuccess(
          'If this email is registered in our system, you will receive reset instructions shortly.',
          'Reset Requested'
        );
        this.forgotPasswordForm.reset();
      },
      error: () => {
        this.isSubmitting.set(false);
        this.toastService.showError('An unexpected error occurred. Please try again later.', 'Error');
      },
    });
  }

  onResetPasswordSubmit(): void {
    if (this.resetPasswordForm.invalid) {
      this.resetPasswordForm.markAllAsTouched();
      return;
    }

    const token = this.resetToken();
    if (!token) {
      this.tokenError.set('No reset token provided. Please request a new password reset link.');
      return;
    }

    this.isSubmitting.set(true);
    const password = this.resetPasswordForm.get('password')?.value!;

    this.authService.resetPassword({ token, password }).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.toastService.showSuccess(
          'Your password has been reset successfully! You can now sign in.',
          'Password Updated'
        );
        this.resetPasswordForm.reset();
        this.router.navigate(['/login']);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const detail = err.error?.detail;
        let msg = 'An unexpected error occurred. Please try again later.';
        if (err.status === 400) {
          if (detail === 'RESET_PASSWORD_BAD_TOKEN') {
            msg = 'The reset link is invalid or has expired. Please request a new password reset.';
          } else if (detail === 'RESET_PASSWORD_INVALID_PASSWORD') {
            msg = 'The new password must be at least 8 characters long.';
          } else if (typeof detail === 'string') {
            msg = detail;
          } else {
            msg = 'Failed to reset password. Please try again.';
          }
        }
        this.toastService.showError(msg, 'Reset Failed');
      },
    });
  }

  isFieldInvalid(
    form: 'login' | 'register' | 'forgot' | 'reset',
    fieldName: string
  ): boolean {
    let control;
    switch (form) {
      case 'login':
        control = this.loginForm.get(fieldName);
        break;
      case 'register':
        control = this.registerForm.get(fieldName);
        break;
      case 'forgot':
        control = this.forgotPasswordForm.get(fieldName);
        break;
      case 'reset':
        control = this.resetPasswordForm.get(fieldName);
        break;
    }
    return !!(control && control.invalid && (control.dirty || control.touched));
  }
}
