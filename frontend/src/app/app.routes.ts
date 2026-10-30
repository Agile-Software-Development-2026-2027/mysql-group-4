import { Routes } from '@angular/router';
import { Homepage } from './pages/homepage/homepage';
import { Landingpage } from './pages/landingpage/landingpage';
import { AuthComponent } from './pages/auth/auth';
import { authGuard, guestGuard } from './core/guards';
import {MissionReview} from './pages/mission-review/mission-review';

export const routes: Routes = [
  { path: '', component: Landingpage, canActivate: [guestGuard] },
  { path: 'login', component: AuthComponent, canActivate: [guestGuard] },
  { path: 'register', component: AuthComponent, canActivate: [guestGuard] },
  { path: 'home', component: Homepage, canActivate: [authGuard] },
  { path: 'missionreview', component: MissionReview },
  { path: '**', redirectTo: '' }
];
