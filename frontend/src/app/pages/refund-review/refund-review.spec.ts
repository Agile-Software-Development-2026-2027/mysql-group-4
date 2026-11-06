import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RefundReview } from './refund-review';

describe('RefundReview', () => {
  let component: RefundReview;
  let fixture: ComponentFixture<RefundReview>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RefundReview]
    })
    .compileComponents();

    fixture = TestBed.createComponent(RefundReview);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
