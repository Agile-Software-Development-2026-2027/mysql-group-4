import { Component, ChangeDetectorRef, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

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
}
