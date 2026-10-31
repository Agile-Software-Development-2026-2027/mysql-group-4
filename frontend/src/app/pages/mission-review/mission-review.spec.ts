import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { MissionReview } from './mission-review';

describe('MissionReview', () => {
  let component: MissionReview;
  let fixture: ComponentFixture<MissionReview>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MissionReview],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    })
      .compileComponents();

    fixture = TestBed.createComponent(MissionReview);
    component = fixture.componentInstance;

    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
