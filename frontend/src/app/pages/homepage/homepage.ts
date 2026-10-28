import { Component, ChangeDetectorRef, inject } from '@angular/core';
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
export class Homepage {
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
}
