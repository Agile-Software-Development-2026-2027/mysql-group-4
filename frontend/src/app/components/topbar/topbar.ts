import { Component, ChangeDetectorRef, ElementRef, HostListener, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { API_CONFIG } from '../../core/config/api.config';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../services/auth.service';

interface NavItem {
  label: string;
  link: string;
  icon?: 'home' | 'missions' | 'approvals' | 'funds' | 'refunds';
  queryParams?: Record<string, string>;
  badge?: number;
}

@Component({
  selector: 'app-topbar',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './topbar.html',
  styleUrl: './topbar.scss',
})
export class Topbar implements OnInit {
  private http = inject(HttpClient);
  private cdr = inject(ChangeDetectorRef);
  private authService = inject(AuthService);
  private logoutDialog = viewChild<ElementRef<HTMLDialogElement>>('logoutDialog');

  siteName = 'MYSOL';
  menuOpen = false;
  missionsToApprove = signal(0);
  tooltipDismissed = signal(false);

  readonly isAdmin = this.authService.isAdmin;
  readonly homeLink = computed(() => this.authService.landingUrl());

  readonly navItems = computed<NavItem[]>(() =>
    this.isAdmin()
      ? [{ label: 'Refunds', link: '/refundoverview', icon: 'refunds' }]
      : [
          { label: 'Home', link: '/home', icon: 'home' },
          { label: 'My Missions', link: '/missionreview', icon: 'missions', queryParams: { view: 'requester' } },
          {
            label: 'Approve Missions',
            link: '/missionreview',
            icon: 'approvals',
            queryParams: { view: 'manager' },
            badge: this.missionsToApprove(),
          },
          { label: 'Funds', link: '/fund', icon: 'funds' },
        ]
  );

  readonly mobileMenuItems = signal<NavItem[]>([
    { label: 'Settings', link: '/settings' },
    { label: 'Logout', link: '/logout' },
  ]);

  toggleMenu(): void {
    this.menuOpen = !this.menuOpen;
    this.cdr.markForCheck();
  }

  closeMenu(): void {
    this.menuOpen = false;
    this.cdr.markForCheck();
  }

  logout(): void {
    this.closeMenu();
    const dialog = this.logoutDialog()?.nativeElement;
    if (dialog?.showModal) {
      dialog.showModal();
    } else {
      this.authService.logout().subscribe();
    }
  }

  onLogoutDialogClose(): void {
    const dialog = this.logoutDialog()?.nativeElement;
    if (!dialog) return;
    const confirmed = dialog.returnValue === 'confirm';
    dialog.returnValue = '';
    if (confirmed) this.authService.logout().subscribe();
  }

  onDialogBackdropClick(event: MouseEvent): void {
    const dialog = this.logoutDialog()?.nativeElement;
    if (!dialog || 'closedBy' in HTMLDialogElement.prototype || event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) {
      dialog.close();
    }
  }

  @HostListener('document:keydown.escape')
  onEscapeKey(): void {
    if (this.menuOpen) this.closeMenu();
    this.tooltipDismissed.set(true);
  }

  onMenuClick(item: NavItem, event: Event): void {
    if (item.link === '/logout') {
      event.preventDefault();
      this.logout();
      return;
    }
    this.closeMenu();
  }

  ngOnInit(): void {
    if (this.isAdmin()) return;
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
}
