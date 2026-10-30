import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MissionReview } from './mission-review';

describe('MissionReview', () => {
  let component: MissionReview;
  let fixture: ComponentFixture<MissionReview>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MissionReview]
    })
    .compileComponents();

    fixture = TestBed.createComponent(MissionReview);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
