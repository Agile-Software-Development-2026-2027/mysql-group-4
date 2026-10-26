import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Homepage } from './homepage';

describe('Homepage', () => {
  let fixture: ComponentFixture<Homepage>;
  let component: Homepage;
  let element: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Homepage],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(Homepage);
    component = fixture.componentInstance;
    element = fixture.nativeElement;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should show the site name in the top bar', () => {
    const brand = element.querySelector('.topbar__brand');
    expect(brand?.textContent).toContain(component.siteName);
  });

  it('should render the user button and the hamburger button', () => {
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

  it('should render one link for each menu item', () => {
    const links = element.querySelectorAll('.side-menu a');
    expect(links.length).toBe(component.menuItems.length);
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