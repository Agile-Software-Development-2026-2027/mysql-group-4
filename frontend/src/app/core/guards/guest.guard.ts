import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from '../../services/auth.service';

export const guestGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return router.parseUrl(authService.landingUrl())
  }

  return authService.checkSession().pipe(
    map((user) => {
      if (user) {
        return router.parseUrl(authService.landingUrl())
      }
      return true;
    })
  );
};
