import { Routes } from '@angular/router';
import { Homepage } from './pages/homepage/homepage';
import { Landingpage } from './pages/landingpage/landingpage';
import { AuthComponent } from './pages/auth/auth';
import { NewMissionComponent } from './pages/new-mission/new-mission';
import { authGuard, guestGuard } from './core/guards';
import { MissionReview } from './pages/mission-review/mission-review';
import { SettingsComponent } from './pages/settings/settings';
import { AddFund } from './pages/add-fund/add-fund';
import { MyFunds } from './pages/my-funds/my-funds';
import { RefundReview } from './pages/refund-review/refund-review';
import { RefundRequestComponent } from './pages/refund-request/refund-request';

export const routes: Routes = [
  { path: '', component: Landingpage, canActivate: [guestGuard] },
  { path: 'login', component: AuthComponent, canActivate: [guestGuard] },
  { path: 'register', component: AuthComponent, canActivate: [guestGuard] },
  { path: 'forgot-password', component: AuthComponent, canActivate: [guestGuard] },
  { path: 'reset-password', component: AuthComponent },
  { path: 'home', component: Homepage, canActivate: [authGuard] },
  { path: 'mission/new', component: NewMissionComponent, canActivate: [authGuard] },
  { path: 'settings', component: SettingsComponent, canActivate: [authGuard] },
  { path: 'missionreview', component: MissionReview, canActivate: [authGuard] },
  { path: 'fund', component: MyFunds, canActivate: [authGuard] },
  { path: 'fund/add', component: AddFund, canActivate: [authGuard] },
  { path: 'refund/:id', component: RefundRequestComponent, canActivate: [authGuard] },
  { path: 'refundreview/:id', component: RefundReview, canActivate: [authGuard] },
  { path: '**', redirectTo: '' }
];
