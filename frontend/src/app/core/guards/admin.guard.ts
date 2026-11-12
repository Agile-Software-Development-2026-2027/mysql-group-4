import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from '../../services/auth.service';

export const adminGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const allowOnlyAdmin = () => (authService.isAdmin() ? true : router.parseUrl('/home'));

  if (authService.isAuthenticated()) {
    return allowOnlyAdmin();
  }

  return authService.checkSession().pipe(map(() => allowOnlyAdmin()));
};
