import { Component, ChangeDetectorRef, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { API_CONFIG } from '../../core/config/api.config';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../services/auth.service';

interface MenuItem {
  label: string;
  link: string;
}

@Component({
  selector: 'app-homepage',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './homepage.html',
  styleUrl: './homepage.scss',
})
export class Homepage implements OnInit {
  private http = inject(HttpClient);
  private cdr = inject(ChangeDetectorRef);
  private authService = inject(AuthService);

  siteName = 'MYSOL';
  menuOpen = false;

  menuItems: MenuItem[] = [
    { label: 'Home', link: '/home' },
    { label: 'New Mission', link: '/mission/new' },
    { label: 'My Mission', link: '/mission' },
    { label: 'Approve Missions', link: '/mission/approve' },
    { label: 'Logout', link: '/logout' },
  ];
  missionsToApprove = signal(0);
  bellOpen = signal(false);


  toggleMenu(): void {
    this.menuOpen = !this.menuOpen;
    this.cdr.markForCheck();
  }

  closeMenu(): void {
    this.menuOpen = false;
    this.cdr.markForCheck();
  }

  onMenuClick(item: MenuItem, event: Event): void {
    if (item.link === '/logout') {
      event.preventDefault();
      this.closeMenu();
      this.authService.logout().subscribe();
      return;
    }
    this.closeMenu();
  }

  ngOnInit(): void {
    this.http
      .post<{ totalElements: number }>(API_CONFIG.endpoints.missions.toApprove, {}, {
        params: { page: 0, size: 1 },
        withCredentials: true,
      })
      .subscribe({
        next: (page) => this.missionsToApprove.set(page.totalElements),
        error: () => this.missionsToApprove.set(0),
      });
  }

  toggleBell(): void {
    this.bellOpen.update((open) => !open);
  }
}
