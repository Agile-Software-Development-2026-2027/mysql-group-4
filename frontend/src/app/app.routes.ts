import { Routes } from '@angular/router';
import { Homepage } from './pages/homepage/homepage';
import { Landingpage } from './pages/landingpage/landingpage';

export const routes: Routes = [
  { path: '', component: Landingpage },
  { path: 'home', component: Homepage },
  { path: '**', redirectTo: '' },
];
