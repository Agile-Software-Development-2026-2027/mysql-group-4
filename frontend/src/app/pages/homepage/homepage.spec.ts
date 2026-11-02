import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Homepage } from './homepage';
import { Topbar } from '../../components/topbar/topbar';
import { provideHttpClient } from '@angular/common/http';

describe('Homepage', () => {
  let fixture: ComponentFixture<Homepage>;
  let component: Homepage;
  let element: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Homepage],
      providers: [
        provideHttpClient(),
        provideRouter([
          { path: 'home', component: Homepage },
          { path: '**', component: Homepage }
        ])
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Homepage);
    component = fixture.componentInstance;
    element = fixture.nativeElement;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render the topbar component', () => {
    expect(element.querySelector('app-topbar')).toBeTruthy();
  });

  it('should show the site name', () => {
    expect(element.querySelector('h1')?.textContent).toContain(component.siteName);
  });

  it('should render the cards grid', () => {
    const cards = element.querySelectorAll('.card');
    expect(cards.length).toBe(3);
  });
});
