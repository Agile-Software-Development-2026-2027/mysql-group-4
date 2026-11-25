import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { Topbar } from './topbar';

describe('Topbar', () => {
  let component: Topbar;
  let fixture: ComponentFixture<Topbar>;
  let element: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Topbar],
      providers: [
        provideHttpClient(),
        provideRouter([
          { path: 'home', component: Topbar },
          { path: 'missionreview', component: Topbar },
          { path: 'fund', component: Topbar },
          { path: 'refundoverview', component: Topbar },
          { path: 'settings', component: Topbar },
        ])
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Topbar);
    component = fixture.componentInstance;
    element = fixture.nativeElement;
    await fixture.whenStable();
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should show the site name in the top bar', () => {
    const brand = element.querySelector('.topbar__brand');
    expect(brand?.textContent).toContain(component.siteName);
  });

  it('should render the home, user, and hamburger buttons', () => {
    expect(element.querySelector('.home-btn')).toBeTruthy();
    expect(element.querySelector('.user-btn')).toBeTruthy();
    expect(element.querySelector('.hamburger')).toBeTruthy();
  });

  it('should have the side menu closed initially', () => {
    expect(component.menuOpen).toBe(false);
    expect(element.querySelector('.side-menu')?.classList).not.toContain('is-open');
  });

  it('should open the side menu when the hamburger is clicked', () => {
    const hamburger = element.querySelector('.hamburger') as HTMLButtonElement;
    hamburger.click();
    fixture.detectChanges();

    expect(component.menuOpen).toBe(true);
    expect(element.querySelector('.side-menu')?.classList).toContain('is-open');
    expect(hamburger.classList).toContain('is-open');
  });

  it('should close the side menu when the overlay is clicked', () => {
    component.toggleMenu();
    fixture.detectChanges();

    (element.querySelector('.overlay') as HTMLElement).click();
    fixture.detectChanges();

    expect(component.menuOpen).toBe(false);
    expect(element.querySelector('.side-menu')?.classList).not.toContain('is-open');
  });

  it('should render primary nav links and mobile menu links', () => {
    const desktopLinks = element.querySelectorAll('.topbar__nav a');
    const mobileLinks = element.querySelectorAll('.side-menu a');
    expect(desktopLinks.length).toBe(component.navItems().length);
    expect(mobileLinks.length).toBe(component.mobileMenuItems().length);
  });

  it('should close the menu after clicking a menu link', async () => {
    component.toggleMenu();
    fixture.detectChanges();

    const firstLink = element.querySelector('.side-menu a') as HTMLAnchorElement;
    firstLink.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(component.menuOpen).toBe(false);
  });
});
